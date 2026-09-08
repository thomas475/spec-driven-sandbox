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

from fakes import FakeLocationProvider, FakeWeatherProvider, StateRecorder  # noqa: E402
from weather_forecast.application.controller import ApplicationController  # noqa: E402
from weather_forecast.application.state import WeatherLoading  # noqa: E402
from weather_forecast.domain.failures import (  # noqa: E402
    ConnectionFailure,
    UserFacingError,
)
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
BERLIN_ZONE = ZoneInfo("Europe/Berlin")


class CountingClock:
    def __init__(self, current: datetime) -> None:
        self.current = current
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.current


def weather_payload(
    *,
    first_hour: datetime = datetime(2026, 8, 26, tzinfo=BERLIN_ZONE),
    first_day: date = date(2026, 8, 26),
) -> WeatherPayload:
    current = CurrentWeather(21, 20, WeatherCondition.CLEAR, 55, 12, 10, 0)
    hourly = tuple(
        HourlyForecastEntry(
            first_hour + timedelta(hours=index),
            20 + index,
            WeatherCondition.CLEAR,
            10,
        )
        for index in range(48)
    )
    daily = tuple(
        DailyForecastEntry(
            first_day + timedelta(days=index),
            12,
            24,
            WeatherCondition.CLEAR,
            10,
            0,
        )
        for index in range(8)
    )
    return WeatherPayload("Europe/Berlin", current, hourly, daily)


class WeatherWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.location_provider = FakeLocationProvider()
        self.weather_provider = FakeWeatherProvider()
        self.clock = CountingClock(datetime(2026, 8, 26, 12, 37, tzinfo=UTC))
        self.recorder = StateRecorder()
        self.controller = ApplicationController(
            self.location_provider,
            (self.recorder,),
            weather_provider=self.weather_provider,
            clock=self.clock,
        )

    def select(self, location: Location = BERLIN):
        self.controller.select_location(location)
        return self.weather_provider.requests[-1]

    def test_selection_passes_complete_location_and_starts_immediately(self) -> None:
        request = self.select()

        self.assertIs(request.location, BERLIN)
        self.assertEqual((request.location.latitude, request.location.longitude), (52.52, 13.405))
        self.assertIs(self.controller.state.requested_location, BERLIN)
        self.assertIs(self.controller.state.weather_loading, WeatherLoading.LOCATION_LOAD)
        self.assertIsNone(self.controller.state.weather_error)
        self.assertIsNone(self.controller.state.loaded_weather)

    def test_failed_first_load_keeps_request_but_has_no_active_weather(self) -> None:
        request = self.select()

        request.fail(ConnectionFailure())

        self.assertIs(self.controller.state.requested_location, BERLIN)
        self.assertIsNone(self.controller.state.loaded_weather)
        self.assertIsNone(self.controller.state.weather_loading)
        self.assertIs(self.controller.state.weather_error, UserFacingError.WEATHER_UPDATE_FAILED)

    def test_acceptance_uses_one_clock_instant_and_exact_local_windows(self) -> None:
        request = self.select()

        request.succeed(weather_payload())

        loaded = self.controller.state.loaded_weather
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(self.clock.calls, 1)
        self.assertEqual(loaded.last_updated, datetime(2026, 8, 26, 14, 37, tzinfo=BERLIN_ZONE))
        self.assertEqual(len(loaded.report.hourly), 24)
        self.assertEqual(loaded.report.hourly[0].local_time, datetime(2026, 8, 26, 14, tzinfo=BERLIN_ZONE))
        self.assertEqual(len(loaded.report.daily), 7)
        self.assertEqual(loaded.report.daily[0].local_date, date(2026, 8, 26))

    def test_success_atomically_commits_complete_weather_and_clears_error(self) -> None:
        self.select().fail(ConnectionFailure())
        request = self.select()
        before_success = self.controller.state

        request.succeed(weather_payload())

        state = self.controller.state
        self.assertIsNone(before_success.loaded_weather)
        self.assertIs(state.requested_location, BERLIN)
        self.assertIsNotNone(state.loaded_weather)
        self.assertIs(state.loaded_weather.location, BERLIN)
        self.assertIsNone(state.weather_loading)
        self.assertIsNone(state.weather_error)

    def test_old_loaded_state_is_preserved_during_and_after_failed_change(self) -> None:
        self.select().succeed(weather_payload())
        previous = self.controller.state.loaded_weather

        request = self.select(MUNICH)

        self.assertIs(self.controller.state.requested_location, MUNICH)
        self.assertIs(self.controller.state.loaded_weather, previous)
        self.assertIs(self.controller.state.weather_loading, WeatherLoading.LOCATION_LOAD)
        request.fail(ConnectionFailure())
        self.assertIs(self.controller.state.requested_location, MUNICH)
        self.assertIs(self.controller.state.loaded_weather, previous)
        self.assertIs(self.controller.state.weather_error, UserFacingError.WEATHER_UPDATE_FAILED)

    def test_invalid_acceptance_window_follows_failure_without_partial_commit(self) -> None:
        request = self.select()

        request.succeed(
            weather_payload(first_hour=datetime(2026, 8, 26, 15, tzinfo=BERLIN_ZONE))
        )

        self.assertIsNone(self.controller.state.loaded_weather)
        self.assertIsNone(self.controller.state.weather_loading)
        self.assertIs(self.controller.state.weather_error, UserFacingError.WEATHER_UPDATE_FAILED)

    def test_new_selection_clears_error_and_stale_callbacks_cannot_overwrite_it(self) -> None:
        older = self.select(BERLIN)
        older.fail(ConnectionFailure())
        older = self.select(BERLIN)
        newer = self.select(MUNICH)

        self.assertTrue(older.handle.cancelled)
        self.assertIsNone(self.controller.state.weather_error)
        older.succeed(weather_payload())
        older.fail(ConnectionFailure())
        self.assertIs(self.controller.state.requested_location, MUNICH)
        self.assertIsNone(self.controller.state.loaded_weather)
        self.assertIs(self.controller.state.weather_loading, WeatherLoading.LOCATION_LOAD)

        newer.succeed(weather_payload())
        loaded = self.controller.state.loaded_weather
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertIs(loaded.location, MUNICH)


if __name__ == "__main__":
    unittest.main()
