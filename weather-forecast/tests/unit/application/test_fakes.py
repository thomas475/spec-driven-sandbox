from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fakes import (  # noqa: E402
    FakeClock,
    FakeLocationProvider,
    FakeRefreshScheduler,
    FakeRequestHandle,
    FakeWeatherProvider,
    StateRecorder,
)
from weather_forecast.application.ports import (  # noqa: E402
    Clock,
    LocationProvider,
    OperationId,
    RefreshScheduler,
    RequestHandle,
    StateListener,
    WeatherProvider,
)
from weather_forecast.application.state import ApplicationState  # noqa: E402
from weather_forecast.domain.failures import (  # noqa: E402
    ConnectionFailure,
    TimeoutFailure,
)
from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.domain.weather import (  # noqa: E402
    CurrentWeather,
    DailyForecastEntry,
    HourlyForecastEntry,
    WeatherCondition,
    WeatherPayload,
)


ZONE = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 8, 26, 14, 30, tzinfo=ZONE)


def make_payload() -> WeatherPayload:
    current = CurrentWeather(
        20.0,
        19.0,
        WeatherCondition.CLEAR,
        60.0,
        10.0,
        5.0,
        0.0,
    )
    start_hour = NOW.replace(minute=0)
    hourly = tuple(
        HourlyForecastEntry(
            start_hour + timedelta(hours=index),
            20.0,
            WeatherCondition.CLEAR,
            5.0,
        )
        for index in range(24)
    )
    daily = tuple(
        DailyForecastEntry(
            date(2026, 8, 26) + timedelta(days=index),
            10.0,
            22.0,
            WeatherCondition.CLEAR,
            5.0,
            0.0,
        )
        for index in range(7)
    )
    return WeatherPayload("Europe/Berlin", current, hourly, daily)


class ProviderFakeTests(unittest.TestCase):
    def test_location_requests_can_succeed_and_fail_in_any_order(self) -> None:
        provider = FakeLocationProvider()
        successes: list[tuple[OperationId, tuple[Location, ...]]] = []
        failures: list[tuple[OperationId, object]] = []
        berlin = Location(52.52, 13.405, "Berlin", "Germany")

        provider.search(
            "first",
            OperationId(1),
            lambda operation_id, locations: successes.append(
                (operation_id, locations)
            ),
            lambda operation_id, failure: failures.append((operation_id, failure)),
        )
        provider.search(
            "second",
            OperationId(2),
            lambda operation_id, locations: successes.append(
                (operation_id, locations)
            ),
            lambda operation_id, failure: failures.append((operation_id, failure)),
        )

        provider.requests[1].succeed((berlin,))
        provider.requests[0].fail(ConnectionFailure())

        self.assertEqual(successes, [(OperationId(2), (berlin,))])
        self.assertEqual(failures[0][0], OperationId(1))
        self.assertIsInstance(failures[0][1], ConnectionFailure)
        self.assertEqual([request.query for request in provider.requests], ["first", "second"])

    def test_weather_requests_capture_locations_and_control_completions(self) -> None:
        provider = FakeWeatherProvider()
        successes: list[tuple[OperationId, WeatherPayload]] = []
        failures: list[tuple[OperationId, object]] = []
        berlin = Location(52.52, 13.405, "Berlin", "Germany")
        munich = Location(48.137, 11.575, "Munich", "Germany")

        provider.fetch(
            berlin,
            OperationId(1),
            lambda operation_id, payload: successes.append((operation_id, payload)),
            lambda operation_id, failure: failures.append((operation_id, failure)),
        )
        provider.fetch(
            munich,
            OperationId(2),
            lambda operation_id, payload: successes.append((operation_id, payload)),
            lambda operation_id, failure: failures.append((operation_id, failure)),
        )

        provider.requests[1].fail(TimeoutFailure())
        provider.requests[0].succeed(make_payload())

        self.assertEqual(failures[0][0], OperationId(2))
        self.assertIsInstance(failures[0][1], TimeoutFailure)
        self.assertEqual(successes[0][0], OperationId(1))
        self.assertIsInstance(successes[0][1], WeatherPayload)
        self.assertEqual([request.location for request in provider.requests], [berlin, munich])

    def test_request_handle_records_cancellation_without_suppressing_races(self) -> None:
        handle = FakeRequestHandle()
        callbacks: list[OperationId] = []
        provider = FakeLocationProvider()
        returned_handle = provider.search(
            "Berlin",
            OperationId(1),
            lambda operation_id, _locations: callbacks.append(operation_id),
            lambda operation_id, _failure: callbacks.append(operation_id),
        )

        handle.cancel()
        returned_handle.cancel()
        provider.requests[0].succeed(())

        self.assertTrue(handle.cancelled)
        self.assertTrue(returned_handle.cancelled)
        self.assertEqual(callbacks, [OperationId(1)])

    def test_provider_fakes_satisfy_application_ports(self) -> None:
        self.assertIsInstance(FakeLocationProvider(), LocationProvider)
        self.assertIsInstance(FakeWeatherProvider(), WeatherProvider)
        self.assertIsInstance(FakeRequestHandle(), RequestHandle)


class TimeAndStateFakeTests(unittest.TestCase):
    def test_clock_is_deterministic_and_advanceable(self) -> None:
        clock = FakeClock(NOW)

        clock.advance(timedelta(minutes=15))

        self.assertEqual(clock.now(), NOW + timedelta(minutes=15))
        self.assertIsInstance(clock, Clock)

    def test_scheduler_fires_once_and_records_delay(self) -> None:
        scheduler = FakeRefreshScheduler()
        calls: list[str] = []
        timer = scheduler.schedule_once(
            timedelta(minutes=15), lambda: calls.append("fired")
        )

        timer.fire()
        timer.fire()

        self.assertEqual(timer.delay, timedelta(minutes=15))
        self.assertEqual(calls, ["fired"])
        self.assertTrue(timer.fired)
        self.assertIsInstance(scheduler, RefreshScheduler)

    def test_cancelled_timer_does_not_fire(self) -> None:
        scheduler = FakeRefreshScheduler()
        calls: list[str] = []
        timer = scheduler.schedule_once(
            timedelta(minutes=15), lambda: calls.append("fired")
        )

        scheduler.cancel(timer)
        timer.fire()

        self.assertTrue(timer.cancelled)
        self.assertFalse(timer.fired)
        self.assertEqual(calls, [])

    def test_state_recorder_captures_snapshots_and_latest(self) -> None:
        recorder = StateRecorder()
        initial = ApplicationState()
        edited = ApplicationState(search_input="Berlin")

        recorder(initial)
        recorder(edited)

        self.assertEqual(recorder.snapshots, [initial, edited])
        self.assertIs(recorder.latest, edited)
        self.assertIsInstance(recorder, StateListener)


if __name__ == "__main__":
    unittest.main()
