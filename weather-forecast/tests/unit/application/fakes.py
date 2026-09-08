"""Deterministic test doubles for application workflow tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from weather_forecast.application.ports import OperationId
from weather_forecast.application.state import ApplicationState
from weather_forecast.domain.failures import ServiceFailure
from weather_forecast.domain.location import Location
from weather_forecast.domain.weather import WeatherPayload


@dataclass(slots=True)
class FakeRequestHandle:
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


@dataclass(slots=True)
class PendingLocationRequest:
    query: str
    operation_id: OperationId
    on_success: Callable[[OperationId, tuple[Location, ...]], None]
    on_failure: Callable[[OperationId, ServiceFailure], None]
    handle: FakeRequestHandle = field(default_factory=FakeRequestHandle)

    def succeed(self, locations: tuple[Location, ...]) -> None:
        self.on_success(self.operation_id, locations)

    def fail(self, failure: ServiceFailure) -> None:
        self.on_failure(self.operation_id, failure)


@dataclass(slots=True)
class FakeLocationProvider:
    requests: list[PendingLocationRequest] = field(default_factory=list)

    def search(
        self,
        query: str,
        operation_id: OperationId,
        on_success: Callable[[OperationId, tuple[Location, ...]], None],
        on_failure: Callable[[OperationId, ServiceFailure], None],
    ) -> FakeRequestHandle:
        request = PendingLocationRequest(
            query,
            operation_id,
            on_success,
            on_failure,
        )
        self.requests.append(request)
        return request.handle


@dataclass(slots=True)
class PendingWeatherRequest:
    location: Location
    operation_id: OperationId
    on_success: Callable[[OperationId, WeatherPayload], None]
    on_failure: Callable[[OperationId, ServiceFailure], None]
    handle: FakeRequestHandle = field(default_factory=FakeRequestHandle)

    def succeed(self, payload: WeatherPayload) -> None:
        self.on_success(self.operation_id, payload)

    def fail(self, failure: ServiceFailure) -> None:
        self.on_failure(self.operation_id, failure)


@dataclass(slots=True)
class FakeWeatherProvider:
    requests: list[PendingWeatherRequest] = field(default_factory=list)

    def fetch(
        self,
        location: Location,
        operation_id: OperationId,
        on_success: Callable[[OperationId, WeatherPayload], None],
        on_failure: Callable[[OperationId, ServiceFailure], None],
    ) -> FakeRequestHandle:
        request = PendingWeatherRequest(
            location,
            operation_id,
            on_success,
            on_failure,
        )
        self.requests.append(request)
        return request.handle


@dataclass(slots=True)
class FakeClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, duration: timedelta) -> None:
        self.current += duration


@dataclass(slots=True)
class FakeTimerHandle:
    delay: timedelta
    callback: Callable[[], None]
    cancelled: bool = False
    fired: bool = False

    def fire(self) -> None:
        if self.cancelled or self.fired:
            return
        self.fired = True
        self.callback()


@dataclass(slots=True)
class FakeRefreshScheduler:
    timers: list[FakeTimerHandle] = field(default_factory=list)

    def schedule_once(
        self, delay: timedelta, callback: Callable[[], None]
    ) -> FakeTimerHandle:
        timer = FakeTimerHandle(delay, callback)
        self.timers.append(timer)
        return timer

    def cancel(self, handle: FakeTimerHandle) -> None:
        handle.cancelled = True


@dataclass(slots=True)
class StateRecorder:
    snapshots: list[ApplicationState] = field(default_factory=list)

    def __call__(self, state: ApplicationState) -> None:
        self.snapshots.append(state)

    @property
    def latest(self) -> ApplicationState | None:
        return self.snapshots[-1] if self.snapshots else None

