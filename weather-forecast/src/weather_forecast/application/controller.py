"""Application workflow coordination."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from weather_forecast.application.ports import (
    Clock,
    LocationProvider,
    OperationId,
    RefreshScheduler,
    RequestHandle,
    StateListener,
    TimerHandle,
    WeatherProvider,
)
from weather_forecast.application.state import (
    ApplicationState,
    SearchResultState,
    WeatherLoading,
)
from weather_forecast.domain.failures import (
    ConnectionFailure,
    InvalidResponseFailure,
    ServiceFailure,
    UserFacingError,
)
from weather_forecast.domain.location import Location
from weather_forecast.domain.weather import LoadedWeather, WeatherPayload, WeatherReport


class ApplicationController:
    """Owns application state and coordinates framework-neutral workflows."""

    def __init__(
        self,
        location_provider: LocationProvider,
        listeners: Iterable[StateListener] = (),
        *,
        weather_provider: WeatherProvider | None = None,
        clock: Clock | None = None,
        refresh_scheduler: RefreshScheduler | None = None,
    ) -> None:
        self._location_provider = location_provider
        self._weather_provider = weather_provider
        self._clock = clock
        self._refresh_scheduler = refresh_scheduler
        self._listeners = list(listeners)
        self._state = ApplicationState()
        self._next_operation_value = 0
        self._current_search_operation_id: OperationId | None = None
        self._search_handle: RequestHandle | None = None
        self._current_weather_operation_id: OperationId | None = None
        self._weather_handle: RequestHandle | None = None
        self._refresh_timer: TimerHandle | None = None
        self._refresh_generation = 0
        self._closed = False

    @property
    def state(self) -> ApplicationState:
        return self._state

    @property
    def is_closed(self) -> bool:
        """Whether the controller has completed its shutdown lifecycle."""
        return self._closed

    def add_listener(self, listener: StateListener) -> None:
        if self._closed:
            return
        self._listeners.append(listener)

    def close(self) -> None:
        """Stop asynchronous work and disconnect all state consumers."""
        if self._closed:
            return
        self._closed = True
        self._current_search_operation_id = None
        self._current_weather_operation_id = None
        self._refresh_generation += 1

        search_handle = self._search_handle
        weather_handle = self._weather_handle
        self._search_handle = None
        self._weather_handle = None
        if search_handle is not None:
            search_handle.cancel()
        if weather_handle is not None:
            weather_handle.cancel()
        if self._refresh_timer is not None and self._refresh_scheduler is not None:
            self._refresh_scheduler.cancel(self._refresh_timer)
        self._refresh_timer = None
        self._listeners.clear()

    def update_search_input(self, text: str) -> None:
        if self._closed:
            return
        self._set_state(replace(self._state, search_input=text))

    def submit_search(self) -> None:
        if self._closed:
            return
        query = self._state.search_input.strip()
        if not query:
            return

        operation_id = self._new_operation_id()
        previous_handle = self._search_handle
        self._current_search_operation_id = operation_id
        self._search_handle = None
        if previous_handle is not None:
            previous_handle.cancel()

        self._set_state(
            replace(
                self._state,
                search_loading=True,
                search_error=None,
            )
        )

        handle = self._location_provider.search(
            query,
            operation_id,
            self._search_succeeded,
            self._search_failed,
        )
        if (
            self._current_search_operation_id == operation_id
            and self._state.search_loading
        ):
            self._search_handle = handle

    def select_location(self, location: Location) -> None:
        """Select a complete location and immediately request its weather."""
        if self._closed:
            return
        if self._weather_provider is None or self._clock is None:
            raise RuntimeError("weather workflow dependencies are not configured")

        self._cancel_refresh()
        operation_id = self._new_operation_id()
        previous_handle = self._weather_handle
        self._current_weather_operation_id = operation_id
        self._weather_handle = None
        if previous_handle is not None:
            previous_handle.cancel()

        self._set_state(
            replace(
                self._state,
                requested_location=location,
                weather_loading=WeatherLoading.LOCATION_LOAD,
                weather_error=None,
            )
        )

        handle = self._weather_provider.fetch(
            location,
            operation_id,
            self._weather_succeeded,
            self._weather_failed,
        )
        if (
            self._current_weather_operation_id == operation_id
            and self._state.weather_loading is WeatherLoading.LOCATION_LOAD
        ):
            self._weather_handle = handle

    def _new_operation_id(self) -> OperationId:
        self._next_operation_value += 1
        return OperationId(self._next_operation_value)

    def _search_succeeded(
        self,
        operation_id: OperationId,
        locations: tuple[Location, ...],
    ) -> None:
        if self._closed or operation_id != self._current_search_operation_id:
            return

        result_state = (
            SearchResultState.RESULTS
            if locations
            else SearchResultState.NO_RESULTS
        )
        self._current_search_operation_id = None
        self._search_handle = None
        self._set_state(
            replace(
                self._state,
                search_results=locations,
                search_result_state=result_state,
                search_loading=False,
                search_error=None,
            )
        )

    def _search_failed(
        self,
        operation_id: OperationId,
        failure: ServiceFailure,
    ) -> None:
        if self._closed or operation_id != self._current_search_operation_id:
            return

        error = (
            UserFacingError.LOCATION_CONNECTION
            if isinstance(failure, ConnectionFailure)
            else UserFacingError.LOCATION_SEARCH_FAILED
        )
        self._current_search_operation_id = None
        self._search_handle = None
        self._set_state(
            replace(
                self._state,
                search_loading=False,
                search_error=error,
            )
        )

    def _weather_succeeded(
        self,
        operation_id: OperationId,
        payload: WeatherPayload,
    ) -> None:
        if self._closed or operation_id != self._current_weather_operation_id:
            return

        try:
            location = self._weather_acceptance_location()
            loaded_weather = self._accept_weather(payload, location)
        except (TypeError, ValueError):
            self._weather_failed(operation_id, InvalidResponseFailure())
            return

        self._current_weather_operation_id = None
        self._weather_handle = None
        self._set_state(
            replace(
                self._state,
                loaded_weather=loaded_weather,
                weather_loading=None,
                weather_error=None,
            )
        )
        self._schedule_refresh()

    def _weather_acceptance_location(self) -> Location:
        if self._state.weather_loading is WeatherLoading.REFRESH:
            if self._state.loaded_weather is None:
                raise ValueError("refresh acceptance requires active weather")
            return self._state.loaded_weather.location
        if self._state.requested_location is None:
            raise ValueError("weather acceptance requires a requested location")
        return self._state.requested_location

    def _accept_weather(
        self,
        payload: WeatherPayload,
        location: Location,
    ) -> LoadedWeather:
        if not isinstance(payload, WeatherPayload):
            raise TypeError("payload must be a WeatherPayload")
        if self._clock is None:
            raise RuntimeError("weather workflow clock is not configured")

        acceptance_instant = self._clock.now()
        if not isinstance(acceptance_instant, datetime):
            raise TypeError("clock must return a datetime")
        if acceptance_instant.tzinfo is None or acceptance_instant.utcoffset() is None:
            raise ValueError("clock must return an aware datetime")

        local_acceptance = acceptance_instant.astimezone(ZoneInfo(payload.time_zone_id))
        acceptance_hour = local_acceptance.replace(minute=0, second=0, microsecond=0)
        hourly_start = next(
            (
                index
                for index, entry in enumerate(payload.hourly)
                if entry.local_time == acceptance_hour
            ),
            None,
        )
        daily_start = next(
            (
                index
                for index, entry in enumerate(payload.daily)
                if entry.local_date == local_acceptance.date()
            ),
            None,
        )
        if hourly_start is None or daily_start is None:
            raise ValueError("weather payload does not cover the acceptance period")

        report = WeatherReport(
            time_zone_id=payload.time_zone_id,
            current=payload.current,
            hourly=payload.hourly[hourly_start : hourly_start + 24],
            daily=payload.daily[daily_start : daily_start + 7],
        )
        return LoadedWeather(location, report, local_acceptance)

    def _weather_failed(
        self,
        operation_id: OperationId,
        failure: ServiceFailure,
    ) -> None:
        if self._closed or operation_id != self._current_weather_operation_id:
            return

        was_refresh = self._state.weather_loading is WeatherLoading.REFRESH
        self._current_weather_operation_id = None
        self._weather_handle = None
        self._set_state(
            replace(
                self._state,
                weather_loading=None,
                weather_error=UserFacingError.WEATHER_UPDATE_FAILED,
            )
        )
        if was_refresh:
            self._schedule_refresh()

    def _cancel_refresh(self) -> None:
        self._refresh_generation += 1
        if self._refresh_timer is not None and self._refresh_scheduler is not None:
            self._refresh_scheduler.cancel(self._refresh_timer)
        self._refresh_timer = None

    def _schedule_refresh(self) -> None:
        if self._closed or self._refresh_scheduler is None:
            return
        self._cancel_refresh()
        generation = self._refresh_generation
        self._refresh_timer = self._refresh_scheduler.schedule_once(
            timedelta(minutes=15),
            lambda: self._refresh_due(generation),
        )

    def _refresh_due(self, generation: int) -> None:
        if self._closed or generation != self._refresh_generation:
            return
        self._refresh_timer = None
        if self._state.weather_loading is not None:
            return
        if self._state.loaded_weather is None:
            return
        if self._weather_provider is None:
            raise RuntimeError("weather workflow dependencies are not configured")

        operation_id = self._new_operation_id()
        self._current_weather_operation_id = operation_id
        self._weather_handle = None
        self._set_state(
            replace(
                self._state,
                weather_loading=WeatherLoading.REFRESH,
                weather_error=None,
            )
        )
        handle = self._weather_provider.fetch(
            self._state.loaded_weather.location,
            operation_id,
            self._weather_succeeded,
            self._weather_failed,
        )
        if (
            self._current_weather_operation_id == operation_id
            and self._state.weather_loading is WeatherLoading.REFRESH
        ):
            self._weather_handle = handle

    def _set_state(self, state: ApplicationState) -> None:
        if self._closed:
            return
        self._state = state
        for listener in tuple(self._listeners):
            listener(state)
