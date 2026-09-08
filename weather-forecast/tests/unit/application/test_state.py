from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.application.ports import (  # noqa: E402
    Clock,
    LocationProvider,
    OperationId,
    RefreshScheduler,
    RequestHandle,
    StateListener,
    TimerHandle,
    WeatherProvider,
)
from weather_forecast.application.state import (  # noqa: E402
    ApplicationState,
    SearchResultState,
    WeatherLoading,
)
from weather_forecast.domain.failures import (  # noqa: E402
    ConnectionFailure,
    ServiceFailure,
    UserFacingError,
)
from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.domain.weather import (  # noqa: E402
    CurrentWeather,
    DailyForecastEntry,
    HourlyForecastEntry,
    LoadedWeather,
    WeatherCondition,
    WeatherPayload,
    WeatherReport,
)


BERLIN_ZONE = ZoneInfo("Europe/Berlin")
ACCEPTED_AT = datetime(2026, 8, 26, 14, 30, tzinfo=BERLIN_ZONE)


def make_current() -> CurrentWeather:
    return CurrentWeather(
        20.0,
        19.0,
        WeatherCondition.CLEAR,
        60.0,
        10.0,
        5.0,
        0.0,
    )


def make_hourly(count: int = 24) -> tuple[HourlyForecastEntry, ...]:
    start = ACCEPTED_AT.replace(minute=0)
    return tuple(
        HourlyForecastEntry(
            start + timedelta(hours=index),
            20.0,
            WeatherCondition.CLEAR,
            5.0,
        )
        for index in range(count)
    )


def make_daily(count: int = 7) -> tuple[DailyForecastEntry, ...]:
    return tuple(
        DailyForecastEntry(
            date(2026, 8, 26) + timedelta(days=index),
            10.0,
            22.0,
            WeatherCondition.CLEAR,
            5.0,
            0.0,
        )
        for index in range(count)
    )


def make_loaded(location: Location) -> LoadedWeather:
    report = WeatherReport(
        "Europe/Berlin", make_current(), make_hourly(), make_daily()
    )
    return LoadedWeather(location, report, ACCEPTED_AT)


class ApplicationStateTests(unittest.TestCase):
    def test_default_state_is_the_required_initial_snapshot(self) -> None:
        state = ApplicationState()

        self.assertEqual(state.search_input, "")
        self.assertEqual(state.search_results, ())
        self.assertIs(state.search_result_state, SearchResultState.INITIAL)
        self.assertFalse(state.search_loading)
        self.assertIsNone(state.search_error)
        self.assertIsNone(state.requested_location)
        self.assertIsNone(state.loaded_weather)
        self.assertIsNone(state.weather_loading)
        self.assertIsNone(state.weather_error)

    def test_represents_results_and_no_results_distinctly(self) -> None:
        berlin = Location(52.52, 13.405, "Berlin", "Germany")

        results = ApplicationState(
            search_results=(berlin,),
            search_result_state=SearchResultState.RESULTS,
        )
        no_results = ApplicationState(
            search_result_state=SearchResultState.NO_RESULTS
        )

        self.assertEqual(results.search_results, (berlin,))
        self.assertEqual(no_results.search_results, ())
        self.assertNotEqual(results.search_result_state, no_results.search_result_state)

    def test_rejects_inconsistent_search_result_states(self) -> None:
        berlin = Location(52.52, 13.405, "Berlin", "Germany")

        with self.assertRaises(ValueError):
            ApplicationState(search_result_state=SearchResultState.RESULTS)
        with self.assertRaises(ValueError):
            ApplicationState(
                search_results=(berlin,),
                search_result_state=SearchResultState.NO_RESULTS,
            )

    def test_represents_location_load_and_refresh_distinctly(self) -> None:
        location_load = ApplicationState(
            weather_loading=WeatherLoading.LOCATION_LOAD
        )
        refresh = ApplicationState(weather_loading=WeatherLoading.REFRESH)

        self.assertIs(location_load.weather_loading, WeatherLoading.LOCATION_LOAD)
        self.assertIs(refresh.weather_loading, WeatherLoading.REFRESH)

    def test_requested_and_active_locations_are_independent(self) -> None:
        active = Location(52.52, 13.405, "Berlin", "Germany")
        requested = Location(48.137, 11.575, "Munich", "Germany")
        loaded = make_loaded(active)

        state = ApplicationState(
            requested_location=requested,
            loaded_weather=loaded,
            weather_loading=WeatherLoading.LOCATION_LOAD,
            weather_error=UserFacingError.WEATHER_UPDATE_FAILED,
        )

        self.assertEqual(state.requested_location, requested)
        self.assertEqual(state.loaded_weather.location, active)
        self.assertNotEqual(state.requested_location, state.loaded_weather.location)

    def test_snapshot_and_results_are_immutable(self) -> None:
        berlin = Location(52.52, 13.405, "Berlin", "Germany")
        state = ApplicationState(
            search_results=(berlin,),
            search_result_state=SearchResultState.RESULTS,
        )

        with self.assertRaises(FrozenInstanceError):
            state.search_input = "Munich"  # type: ignore[misc]
        self.assertIsInstance(state.search_results, tuple)


class _Request:
    def cancel(self) -> None:
        pass


class _Timer:
    pass


class _LocationProvider:
    def search(self, query, operation_id, on_success, on_failure):
        on_success(operation_id, (Location(52.52, 13.405, "Berlin", "Germany"),))
        return _Request()


class _WeatherProvider:
    def fetch(self, location, operation_id, on_success, on_failure):
        payload = WeatherPayload(
            "Europe/Berlin", make_current(), make_hourly(), make_daily()
        )
        on_success(operation_id, payload)
        return _Request()


class _Scheduler:
    def schedule_once(self, delay, callback):
        return _Timer()

    def cancel(self, handle):
        pass


class _Clock:
    def now(self):
        return ACCEPTED_AT


class _Listener:
    def __call__(self, state):
        self.state = state


class PortContractTests(unittest.TestCase):
    def test_runtime_doubles_satisfy_framework_neutral_protocols(self) -> None:
        self.assertIsInstance(_Request(), RequestHandle)
        self.assertIsInstance(_Timer(), TimerHandle)
        self.assertIsInstance(_LocationProvider(), LocationProvider)
        self.assertIsInstance(_WeatherProvider(), WeatherProvider)
        self.assertIsInstance(_Scheduler(), RefreshScheduler)
        self.assertIsInstance(_Clock(), Clock)
        self.assertIsInstance(_Listener(), StateListener)

    def test_location_provider_callbacks_use_internal_types(self) -> None:
        successes: list[tuple[OperationId, tuple[Location, ...]]] = []
        failures: list[tuple[OperationId, ServiceFailure]] = []
        operation_id = OperationId(1)

        handle = _LocationProvider().search(
            "Berlin",
            operation_id,
            lambda callback_id, locations: successes.append(
                (callback_id, locations)
            ),
            lambda callback_id, failure: failures.append((callback_id, failure)),
        )

        self.assertIsInstance(handle, RequestHandle)
        self.assertEqual(successes[0][0], operation_id)
        self.assertIsInstance(successes[0][1][0], Location)
        self.assertEqual(failures, [])

    def test_weather_provider_callbacks_use_internal_types(self) -> None:
        successes: list[tuple[OperationId, WeatherPayload]] = []
        operation_id = OperationId(2)

        handle = _WeatherProvider().fetch(
            Location(52.52, 13.405, "Berlin", "Germany"),
            operation_id,
            lambda callback_id, payload: successes.append((callback_id, payload)),
            lambda _operation_id, _failure: None,
        )

        self.assertIsInstance(handle, RequestHandle)
        self.assertEqual(successes[0][0], operation_id)
        self.assertIsInstance(successes[0][1], WeatherPayload)

    def test_failure_callback_uses_typed_service_failure(self) -> None:
        captured: list[tuple[OperationId, ServiceFailure]] = []
        operation_id = OperationId(3)
        callback = captured.append

        callback((operation_id, ConnectionFailure()))

        self.assertEqual(captured[0][0], operation_id)
        self.assertIsInstance(captured[0][1], ServiceFailure)


if __name__ == "__main__":
    unittest.main()
