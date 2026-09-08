from __future__ import annotations

import os
import sys
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
APPLICATION_TEST_SUPPORT = PROJECT_ROOT / "tests" / "unit" / "application"
sys.path.insert(0, str(SOURCE_ROOT))
sys.path.insert(0, str(APPLICATION_TEST_SUPPORT))

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from fakes import (  # noqa: E402
    FakeClock,
    FakeLocationProvider,
    FakeRefreshScheduler,
    FakeWeatherProvider,
)
from weather_forecast.application.controller import ApplicationController  # noqa: E402
from weather_forecast.application.state import (  # noqa: E402
    ApplicationState,
    SearchResultState,
    WeatherLoading,
)
from weather_forecast.domain.failures import ConnectionFailure, UserFacingError  # noqa: E402
from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.domain.weather import (  # noqa: E402
    CurrentWeather,
    DailyForecastEntry,
    HourlyForecastEntry,
    WeatherCondition,
    WeatherPayload,
)
from weather_forecast.ui.main_window import MainWindow  # noqa: E402
from weather_forecast.ui.presenters import SELECT_LOCATION_MESSAGE  # noqa: E402


ZONE = ZoneInfo("Europe/Berlin")
BERLIN = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")
MUNICH = Location(48.137, 11.575, "Munich", "Germany", "Bavaria")


class SpyController:
    def __init__(self) -> None:
        self.state = ApplicationState()
        self.listeners = []
        self.input_updates = []
        self.submissions = 0
        self.selections = []

    def add_listener(self, listener) -> None:
        self.listeners.append(listener)

    def update_search_input(self, text: str) -> None:
        self.input_updates.append(text)

    def submit_search(self) -> None:
        self.submissions += 1

    def select_location(self, location: Location) -> None:
        self.selections.append(location)

    def publish(self, state: ApplicationState) -> None:
        self.state = state
        for listener in tuple(self.listeners):
            listener(state)


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


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
            self.window.deleteLater()
            self.app.processEvents()

    def show_window(self, controller) -> MainWindow:
        self.window = MainWindow(controller)
        self.window.show()
        self.app.processEvents()
        return self.window

    def test_startup_renders_search_availability_and_no_weather_instruction(self) -> None:
        window = self.show_window(SpyController())

        self.assertTrue(window.location_search.search_input.isEnabled())
        self.assertTrue(window.location_search.search_button.isEnabled())
        self.assertEqual(
            window.weather_display.instruction_label.text(),
            SELECT_LOCATION_MESSAGE,
        )
        self.assertTrue(window.weather_display.instruction_label.isVisible())
        self.assertFalse(window.weather_display.vertical_scroll.isVisible())
        self.assertEqual(window.minimumWidth(), 800)
        self.assertEqual(window.minimumHeight(), 600)

    def test_ui_actions_only_invoke_controller_and_snapshots_render_both_views(self) -> None:
        controller = SpyController()
        window = self.show_window(controller)

        QTest.keyClicks(window.location_search.search_input, "Berlin")
        QTest.keyClick(window.location_search.search_input, Qt.Key.Key_Return)
        controller.publish(
            ApplicationState(
                search_input="Berlin",
                search_results=(BERLIN, MUNICH),
                search_result_state=SearchResultState.RESULTS,
                weather_error=UserFacingError.WEATHER_UPDATE_FAILED,
            )
        )
        window.location_search.results_list.itemClicked.emit(
            window.location_search.results_list.item(1)
        )

        self.assertEqual(controller.input_updates[-1], "Berlin")
        self.assertEqual(controller.submissions, 1)
        self.assertEqual(controller.selections, [MUNICH])
        self.assertEqual(window.location_search.results_list.count(), 2)
        self.assertTrue(window.weather_display.error_label.isVisible())

    def test_search_and_weather_loading_and_errors_render_independently(self) -> None:
        controller = SpyController()
        window = self.show_window(controller)

        controller.publish(
            ApplicationState(
                search_loading=True,
                weather_error=UserFacingError.WEATHER_UPDATE_FAILED,
            )
        )
        self.assertTrue(window.location_search.loading_label.isVisible())
        self.assertFalse(window.location_search.error_label.isVisible())
        self.assertFalse(window.weather_display.loading_label.isVisible())
        self.assertTrue(window.weather_display.error_label.isVisible())

        controller.publish(
            ApplicationState(
                search_error=UserFacingError.LOCATION_SEARCH_FAILED,
                weather_loading=WeatherLoading.LOCATION_LOAD,
            )
        )
        self.assertFalse(window.location_search.loading_label.isVisible())
        self.assertTrue(window.location_search.error_label.isVisible())
        self.assertTrue(window.weather_display.loading_label.isVisible())
        self.assertFalse(window.weather_display.error_label.isVisible())

    def test_deferred_callbacks_keep_event_loop_and_existing_content_responsive(self) -> None:
        location_provider = FakeLocationProvider()
        weather_provider = FakeWeatherProvider()
        controller = ApplicationController(
            location_provider,
            weather_provider=weather_provider,
            clock=FakeClock(datetime(2026, 8, 26, 12, 30, tzinfo=UTC)),
            refresh_scheduler=FakeRefreshScheduler(),
        )
        window = self.show_window(controller)

        QTest.keyClicks(window.location_search.search_input, "cities")
        QTest.mouseClick(window.location_search.search_button, Qt.MouseButton.LeftButton)
        location_provider.requests[-1].succeed((BERLIN, MUNICH))
        window.location_search.results_list.itemClicked.emit(
            window.location_search.results_list.item(0)
        )
        weather_provider.requests[-1].succeed(payload())
        self.app.processEvents()
        timestamp = window.weather_display.last_updated_label.text()

        window.location_search.results_list.itemClicked.emit(
            window.location_search.results_list.item(1)
        )
        event_loop_markers = []
        QTimer.singleShot(0, lambda: event_loop_markers.append("responsive"))
        self.app.processEvents()

        self.assertEqual(event_loop_markers, ["responsive"])
        self.assertTrue(window.weather_display.loading_label.isVisible())
        self.assertEqual(window.weather_display.location_header.text(), "Berlin, Germany")
        self.assertEqual(window.weather_display.last_updated_label.text(), timestamp)

        weather_provider.requests[-1].fail(ConnectionFailure())
        self.app.processEvents()
        self.assertEqual(window.weather_display.location_header.text(), "Berlin, Germany")
        self.assertEqual(window.weather_display.last_updated_label.text(), timestamp)
        self.assertTrue(window.weather_display.error_label.isVisible())


if __name__ == "__main__":
    unittest.main()
