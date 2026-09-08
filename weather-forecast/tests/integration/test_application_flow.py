from __future__ import annotations

import os
import sys
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests" / "unit" / "application"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from fakes import (  # noqa: E402
    FakeClock,
    FakeLocationProvider,
    FakeRefreshScheduler,
    FakeWeatherProvider,
)
from weather_forecast.application.controller import ApplicationController  # noqa: E402
from weather_forecast.domain.failures import ConnectionFailure  # noqa: E402
from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.domain.weather import (  # noqa: E402
    CurrentWeather,
    DailyForecastEntry,
    HourlyForecastEntry,
    WeatherCondition,
    WeatherPayload,
)
from weather_forecast.ui.main_window import MainWindow  # noqa: E402


ZONE = ZoneInfo("Europe/Berlin")
BERLIN = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")
MUNICH = Location(48.137, 11.575, "Munich", "Germany", "Bavaria")
REFRESH_DELAY = timedelta(minutes=15)


def weather_payload(marker: float = 20) -> WeatherPayload:
    first_hour = datetime(2026, 8, 26, tzinfo=ZONE)
    current = CurrentWeather(
        marker,
        marker - 1,
        WeatherCondition.CLEAR,
        50,
        10,
        5,
        0,
    )
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


class IntegratedApplicationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.location_provider = FakeLocationProvider()
        self.weather_provider = FakeWeatherProvider()
        self.scheduler = FakeRefreshScheduler()
        self.clock = FakeClock(datetime(2026, 8, 26, 12, 30, tzinfo=UTC))
        self.controller = ApplicationController(
            self.location_provider,
            weather_provider=self.weather_provider,
            clock=self.clock,
            refresh_scheduler=self.scheduler,
        )
        self.window = MainWindow(self.controller)
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.controller.close()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def submit(self, text: str) -> None:
        self.window.location_search.search_input.clear()
        QTest.keyClicks(self.window.location_search.search_input, text)
        QTest.mouseClick(
            self.window.location_search.search_button,
            Qt.MouseButton.LeftButton,
        )

    def select_result(self, row: int) -> None:
        item = self.window.location_search.results_list.item(row)
        self.window.location_search.results_list.itemClicked.emit(item)

    def load_berlin(self, marker: float = 20) -> None:
        self.submit("Berlin")
        self.location_provider.requests[-1].succeed((BERLIN, MUNICH))
        self.select_result(0)
        self.weather_provider.requests[-1].succeed(weather_payload(marker))
        self.app.processEvents()


class ApplicationFlowIntegrationTests(IntegratedApplicationTestCase):
    def test_complete_search_selection_and_refresh_success_failure_flow(self) -> None:
        self.assertTrue(self.window.weather_display.instruction_label.isVisible())

        self.submit("  Berlin  ")
        self.assertEqual(self.location_provider.requests[-1].query, "Berlin")
        self.assertEqual(self.window.location_search.search_input.text(), "  Berlin  ")
        self.location_provider.requests[-1].succeed((BERLIN, MUNICH))
        self.assertEqual(self.window.location_search.results_list.count(), 2)

        self.select_result(0)
        self.assertIs(self.weather_provider.requests[-1].location, BERLIN)
        self.assertTrue(self.window.weather_display.loading_label.isVisible())
        self.weather_provider.requests[-1].succeed(weather_payload(20))
        self.app.processEvents()

        display = self.window.weather_display
        self.assertEqual(display.location_header.text(), "Berlin, Germany")
        self.assertEqual(display.current_labels["temperature"].text(), "20 °C")
        self.assertEqual(len(display.hourly_cards), 24)
        self.assertEqual(len(display.daily_cards), 7)
        first_timestamp = display.last_updated_label.text()
        self.assertEqual(self.scheduler.timers[-1].delay, REFRESH_DELAY)

        self.scheduler.timers[-1].fire()
        self.assertTrue(display.loading_label.isVisible())
        self.assertEqual(display.current_labels["temperature"].text(), "20 °C")
        self.clock.advance(timedelta(minutes=3))
        self.weather_provider.requests[-1].succeed(weather_payload(30))
        self.app.processEvents()
        refreshed_timestamp = display.last_updated_label.text()
        self.assertEqual(display.current_labels["temperature"].text(), "30 °C")
        self.assertNotEqual(refreshed_timestamp, first_timestamp)

        self.scheduler.timers[-1].fire()
        request_count = len(self.weather_provider.requests)
        self.weather_provider.requests[-1].fail(ConnectionFailure())
        self.app.processEvents()
        self.assertEqual(len(self.weather_provider.requests), request_count)
        self.assertEqual(display.current_labels["temperature"].text(), "30 °C")
        self.assertEqual(display.last_updated_label.text(), refreshed_timestamp)
        self.assertTrue(display.error_label.isVisible())
        self.assertEqual(self.scheduler.timers[-1].delay, REFRESH_DELAY)

    def test_no_results_and_failed_search_preserve_previous_results_and_weather(self) -> None:
        self.load_berlin()
        weather_request_count = len(self.weather_provider.requests)

        self.submit("unreachable")
        self.location_provider.requests[-1].fail(ConnectionFailure())
        self.app.processEvents()
        self.assertEqual(self.window.location_search.results_list.count(), 2)
        self.assertTrue(self.window.location_search.error_label.isVisible())
        self.assertEqual(len(self.weather_provider.requests), weather_request_count)
        self.assertEqual(
            self.window.weather_display.location_header.text(),
            "Berlin, Germany",
        )

        self.submit("nowhere")
        self.location_provider.requests[-1].succeed(())
        self.app.processEvents()
        self.assertEqual(self.window.location_search.results_list.count(), 0)
        self.assertTrue(self.window.location_search.empty_label.isVisible())
        self.assertFalse(self.window.location_search.error_label.isVisible())
        self.assertEqual(len(self.weather_provider.requests), weather_request_count)

    def test_location_change_keeps_fallback_until_atomic_success(self) -> None:
        self.load_berlin(20)
        previous_timestamp = self.window.weather_display.last_updated_label.text()

        self.select_result(1)
        self.assertEqual(self.controller.state.requested_location, MUNICH)
        self.assertEqual(self.controller.state.loaded_weather.location, BERLIN)
        self.assertEqual(self.window.weather_display.location_header.text(), "Berlin, Germany")
        self.weather_provider.requests[-1].fail(ConnectionFailure())
        self.app.processEvents()
        self.assertEqual(self.window.weather_display.location_header.text(), "Berlin, Germany")
        self.assertEqual(
            self.window.weather_display.last_updated_label.text(),
            previous_timestamp,
        )

        self.select_result(1)
        self.clock.advance(timedelta(minutes=2))
        self.weather_provider.requests[-1].succeed(weather_payload(40))
        self.app.processEvents()
        self.assertEqual(self.window.weather_display.location_header.text(), "Munich, Germany")
        self.assertEqual(self.window.weather_display.current_labels["temperature"].text(), "40 °C")
        self.assertFalse(self.window.weather_display.error_label.isVisible())


if __name__ == "__main__":
    unittest.main()
