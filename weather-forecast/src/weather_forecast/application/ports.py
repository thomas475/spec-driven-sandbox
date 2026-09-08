"""Framework-neutral interfaces used by application workflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import NewType, Protocol, TYPE_CHECKING, runtime_checkable

from weather_forecast.domain.failures import ServiceFailure
from weather_forecast.domain.location import Location
from weather_forecast.domain.weather import WeatherPayload

if TYPE_CHECKING:
    from weather_forecast.application.state import ApplicationState


OperationId = NewType("OperationId", int)


@runtime_checkable
class RequestHandle(Protocol):
    def cancel(self) -> None: ...


@runtime_checkable
class TimerHandle(Protocol):
    pass


@runtime_checkable
class LocationProvider(Protocol):
    def search(
        self,
        query: str,
        operation_id: OperationId,
        on_success: Callable[[OperationId, tuple[Location, ...]], None],
        on_failure: Callable[[OperationId, ServiceFailure], None],
    ) -> RequestHandle: ...


@runtime_checkable
class WeatherProvider(Protocol):
    def fetch(
        self,
        location: Location,
        operation_id: OperationId,
        on_success: Callable[[OperationId, WeatherPayload], None],
        on_failure: Callable[[OperationId, ServiceFailure], None],
    ) -> RequestHandle: ...


@runtime_checkable
class RefreshScheduler(Protocol):
    def schedule_once(
        self, delay: timedelta, callback: Callable[[], None]
    ) -> TimerHandle: ...

    def cancel(self, handle: TimerHandle) -> None: ...


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class StateListener(Protocol):
    def __call__(self, state: ApplicationState) -> None: ...

