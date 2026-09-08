from __future__ import annotations

import sys
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
TEST_SUPPORT = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE_ROOT))
sys.path.insert(0, str(TEST_SUPPORT))

from fakes import (  # noqa: E402
    FakeClock,
    FakeLocationProvider,
    FakeRefreshScheduler,
    FakeWeatherProvider,
)
from weather_forecast.application.controller import ApplicationController  # noqa: E402
from weather_forecast.application.state import WeatherLoading  # noqa: E402
from weather_forecast.domain.failures import ConnectionFailure, UserFacingError  # noqa: E402
from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.domain.weather import (  # noqa: E402
    CurrentWeather,
    DailyForecastEntry,
    HourlyForecastEntry,
    WeatherCondition,
    WeatherPayload,
)


BERLIN = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")
MUNICH = Location(48.137, 11.575, "Munich", "Germany", "Bavaria")
ZONE = ZoneInfo("Europe/Berlin")
REFRESH_DELAY = timedelta(minutes=15)


def payload(marker: float = 20) -> WeatherPayload:
    first_hour = datetime(2026, 8, 26, tzinfo=ZONE)
    current = CurrentWeather(marker, marker, WeatherCondition.CLEAR, 50, 10, 5, 0)
    hourly = tuple(
        HourlyForecastEntry(
            first_hour + timedelta(hours=index),
            marker + index,
            WeatherCondition.CLEAR,
            5,
        )
        for index in range(48)
    )
    daily = tuple(
        DailyForecastEntry(
            date(2026, 8, 26) + timedelta(days=index),
            marker - 5,
            marker + 5,
            WeatherCondition.CLEAR,
            5,
            0,
        )
        for index in range(8)
    )
    return WeatherPayload("Europe/Berlin", current, hourly, daily)


class RefreshWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.weather_provider = FakeWeatherProvider()
        self.scheduler = FakeRefreshScheduler()
        self.clock = FakeClock(datetime(2026, 8, 26, 12, 30, tzinfo=UTC))
        self.controller = ApplicationController(
            FakeLocationProvider(),
            weather_provider=self.weather_provider,
            clock=self.clock,
            refresh_scheduler=self.scheduler,
        )

    def load(self, location: Location = BERLIN, marker: float = 20):
        self.controller.select_location(location)
        request = self.weather_provider.requests[-1]
        request.succeed(payload(marker))
        return request

    def start_refresh(self):
        timer = self.scheduler.timers[-1]
        timer.fire()
        return self.weather_provider.requests[-1]

    def test_no_schedule_exists_before_first_success(self) -> None:
        self.assertEqual(self.scheduler.timers, [])

        self.controller.select_location(BERLIN)
        self.weather_provider.requests[-1].fail(ConnectionFailure())

        self.assertEqual(self.scheduler.timers, [])

    def test_success_schedules_exactly_one_refresh_fifteen_minutes_later(self) -> None:
        self.load()

        self.assertEqual(len(self.scheduler.timers), 1)
        self.assertEqual(self.scheduler.timers[0].delay, REFRESH_DELAY)
        self.assertFalse(self.scheduler.timers[0].cancelled)

    def test_refresh_preserves_loaded_data_and_clears_error_while_loading(self) -> None:
        self.load()
        first_refresh = self.start_refresh()
        first_refresh.fail(ConnectionFailure())
        previous = self.controller.state.loaded_weather

        second_refresh = self.start_refresh()

        self.assertIs(self.controller.state.loaded_weather, previous)
        self.assertIs(self.controller.state.weather_loading, WeatherLoading.REFRESH)
        self.assertIsNone(self.controller.state.weather_error)
        self.assertIs(second_refresh.location, BERLIN)

    def test_refresh_success_replaces_atomically_and_schedules_from_completion(self) -> None:
        self.load(marker=20)
        previous = self.controller.state.loaded_weather
        refresh = self.start_refresh()
        self.clock.advance(timedelta(minutes=4))

        refresh.succeed(payload(marker=30))

        loaded = self.controller.state.loaded_weather
        self.assertIsNot(loaded, previous)
        assert loaded is not None
        self.assertEqual(loaded.report.current.temperature_c, 30)
        self.assertEqual(loaded.last_updated, datetime(2026, 8, 26, 14, 34, tzinfo=ZONE))
        self.assertIsNone(self.controller.state.weather_loading)
        self.assertIsNone(self.controller.state.weather_error)
        self.assertEqual(self.scheduler.timers[-1].delay, REFRESH_DELAY)

    def test_refresh_failure_preserves_data_and_schedules_without_immediate_retry(self) -> None:
        self.load()
        previous = self.controller.state.loaded_weather
        refresh = self.start_refresh()
        request_count = len(self.weather_provider.requests)

        refresh.fail(ConnectionFailure())

        self.assertIs(self.controller.state.loaded_weather, previous)
        self.assertIsNone(self.controller.state.weather_loading)
        self.assertIs(self.controller.state.weather_error, UserFacingError.WEATHER_UPDATE_FAILED)
        self.assertEqual(len(self.weather_provider.requests), request_count)
        self.assertEqual(self.scheduler.timers[-1].delay, REFRESH_DELAY)
        self.assertFalse(self.scheduler.timers[-1].fired)

    def test_single_refresh_and_stale_timer_or_request_callbacks_are_harmless(self) -> None:
        self.load()
        old_timer = self.scheduler.timers[-1]
        refresh = self.start_refresh()
        request_count = len(self.weather_provider.requests)

        old_timer.callback()

        self.assertEqual(len(self.weather_provider.requests), request_count)
        refresh.succeed(payload(marker=30))
        accepted = self.controller.state.loaded_weather
        refresh.fail(ConnectionFailure())
        self.assertIs(self.controller.state.loaded_weather, accepted)

    def test_selection_cancels_prior_active_location_schedule(self) -> None:
        self.load(BERLIN)
        old_timer = self.scheduler.timers[-1]

        self.controller.select_location(MUNICH)

        self.assertTrue(old_timer.cancelled)
        request_count = len(self.weather_provider.requests)
        old_timer.callback()
        self.assertEqual(len(self.weather_provider.requests), request_count)

    def test_selection_aborts_refresh_and_refresh_never_changes_requested_location(self) -> None:
        self.load(BERLIN)
        old_timer = self.scheduler.timers[-1]
        requested = self.controller.state.requested_location

        refresh = self.start_refresh()
        self.assertIs(self.controller.state.requested_location, requested)
        self.controller.select_location(MUNICH)

        self.assertTrue(refresh.handle.cancelled)
        self.assertIs(self.controller.state.requested_location, MUNICH)
        refresh.succeed(payload(marker=40))
        self.assertIs(self.controller.state.requested_location, MUNICH)
        self.assertIs(self.controller.state.loaded_weather.location, BERLIN)

        self.weather_provider.requests[-1].fail(ConnectionFailure())
        old_timer.callback()
        self.assertEqual(len(self.weather_provider.requests), 3)


if __name__ == "__main__":
    unittest.main()
