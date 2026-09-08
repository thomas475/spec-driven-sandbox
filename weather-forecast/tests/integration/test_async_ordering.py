from __future__ import annotations

import sys
import unittest
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "integration"))

from PySide6.QtCore import QTimer  # noqa: E402

from test_application_flow import (  # noqa: E402
    BERLIN,
    MUNICH,
    REFRESH_DELAY,
    IntegratedApplicationTestCase,
    weather_payload,
)
from weather_forecast.domain.failures import ConnectionFailure  # noqa: E402


class AsyncOrderingIntegrationTests(IntegratedApplicationTestCase):
    def test_overlapping_search_and_selection_callbacks_cannot_overwrite_newer_ui(self) -> None:
        self.submit("old search")
        old_search = self.location_provider.requests[-1]
        self.submit("new search")
        new_search = self.location_provider.requests[-1]

        old_search.succeed((BERLIN,))
        new_search.succeed((BERLIN, MUNICH))
        old_search.fail(ConnectionFailure())
        self.assertEqual(self.window.location_search.results_list.count(), 2)
        self.assertFalse(self.window.location_search.error_label.isVisible())

        self.select_result(0)
        old_weather = self.weather_provider.requests[-1]
        self.select_result(1)
        new_weather = self.weather_provider.requests[-1]
        old_weather.succeed(weather_payload(10))
        self.assertIsNone(self.controller.state.loaded_weather)
        new_weather.succeed(weather_payload(30))
        old_weather.fail(ConnectionFailure())
        self.app.processEvents()

        self.assertEqual(self.window.weather_display.location_header.text(), "Munich, Germany")
        self.assertEqual(self.window.weather_display.current_labels["temperature"].text(), "30 °C")
        self.assertFalse(self.window.weather_display.error_label.isVisible())

    def test_late_refresh_cannot_replace_new_selection(self) -> None:
        self.load_berlin(20)
        refresh_timer = self.scheduler.timers[-1]
        refresh_timer.fire()
        stale_refresh = self.weather_provider.requests[-1]

        self.select_result(1)
        new_selection = self.weather_provider.requests[-1]
        stale_refresh.succeed(weather_payload(50))
        self.assertEqual(self.controller.state.loaded_weather.location, BERLIN)
        new_selection.succeed(weather_payload(40))
        stale_refresh.fail(ConnectionFailure())
        self.app.processEvents()

        self.assertEqual(self.window.weather_display.location_header.text(), "Munich, Germany")
        self.assertEqual(self.window.weather_display.current_labels["temperature"].text(), "40 °C")

    def test_failed_first_load_reselection_retry_and_single_refresh(self) -> None:
        self.submit("Berlin")
        self.location_provider.requests[-1].succeed((BERLIN,))
        self.select_result(0)
        self.weather_provider.requests[-1].fail(ConnectionFailure())
        self.app.processEvents()

        self.assertIsNone(self.controller.state.loaded_weather)
        self.assertEqual(self.scheduler.timers, [])
        self.assertTrue(self.window.weather_display.instruction_label.isVisible())
        self.assertTrue(self.window.weather_display.error_label.isVisible())

        self.select_result(0)
        self.assertFalse(self.window.weather_display.error_label.isVisible())
        self.weather_provider.requests[-1].succeed(weather_payload())
        self.assertEqual(self.scheduler.timers[-1].delay, REFRESH_DELAY)

        timer = self.scheduler.timers[-1]
        timer.fire()
        refresh = self.weather_provider.requests[-1]
        request_count = len(self.weather_provider.requests)
        timer.callback()
        self.assertEqual(len(self.weather_provider.requests), request_count)

        refresh.fail(ConnectionFailure())
        self.assertEqual(len(self.weather_provider.requests), request_count)
        retry_timer = self.scheduler.timers[-1]
        self.assertEqual(retry_timer.delay, REFRESH_DELAY)
        self.clock.advance(timedelta(minutes=15))
        retry_timer.fire()
        self.assertEqual(len(self.weather_provider.requests), request_count + 1)

    def test_deferred_completions_leave_the_qt_event_loop_responsive(self) -> None:
        self.submit("Berlin")
        search = self.location_provider.requests[-1]
        markers: list[str] = []

        QTimer.singleShot(0, lambda: markers.append("event loop ran"))
        QTimer.singleShot(0, lambda: search.succeed((BERLIN,)))
        self.app.processEvents()

        self.assertEqual(markers, ["event loop ran"])
        self.assertEqual(self.window.location_search.results_list.count(), 1)
        self.select_result(0)
        weather = self.weather_provider.requests[-1]
        QTimer.singleShot(0, lambda: markers.append("weather wait responsive"))
        QTimer.singleShot(0, lambda: weather.succeed(weather_payload()))
        self.app.processEvents()

        self.assertEqual(
            markers,
            ["event loop ran", "weather wait responsive"],
        )
        self.assertEqual(self.window.weather_display.location_header.text(), "Berlin, Germany")


if __name__ == "__main__":
    unittest.main()
