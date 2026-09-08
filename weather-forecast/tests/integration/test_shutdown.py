from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "unit" / "application"))

from fakes import (  # noqa: E402
    FakeClock,
    FakeLocationProvider,
    FakeRefreshScheduler,
    FakeWeatherProvider,
    StateRecorder,
)
from weather_forecast.application.controller import ApplicationController  # noqa: E402
from weather_forecast.domain.failures import ConnectionFailure  # noqa: E402
from weather_forecast.domain.location import Location  # noqa: E402


BERLIN = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")


class ShutdownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.location_provider = FakeLocationProvider()
        self.weather_provider = FakeWeatherProvider()
        self.scheduler = FakeRefreshScheduler()
        self.listener = StateRecorder()
        self.controller = ApplicationController(
            self.location_provider,
            (self.listener,),
            weather_provider=self.weather_provider,
            clock=FakeClock(datetime(2026, 8, 26, 12, tzinfo=UTC)),
            refresh_scheduler=self.scheduler,
        )

    def test_shutdown_cancels_requests_and_disconnects_late_callbacks(self) -> None:
        self.controller.update_search_input("Berlin")
        self.controller.submit_search()
        self.controller.select_location(BERLIN)
        search = self.location_provider.requests[-1]
        weather = self.weather_provider.requests[-1]
        snapshots_before_close = len(self.listener.snapshots)
        state_before_close = self.controller.state

        self.controller.close()
        search.succeed((BERLIN,))
        weather.fail(ConnectionFailure())
        self.controller.update_search_input("late edit")

        self.assertTrue(self.controller.is_closed)
        self.assertTrue(search.handle.cancelled)
        self.assertTrue(weather.handle.cancelled)
        self.assertIs(self.controller.state, state_before_close)
        self.assertEqual(len(self.listener.snapshots), snapshots_before_close)

    def test_shutdown_cancels_refresh_timer_and_is_idempotent(self) -> None:
        self.controller._schedule_refresh()
        timer = self.scheduler.timers[-1]

        self.controller.close()
        self.controller.close()
        timer.fire()

        self.assertTrue(timer.cancelled)
        self.assertEqual(self.weather_provider.requests, [])


if __name__ == "__main__":
    unittest.main()
