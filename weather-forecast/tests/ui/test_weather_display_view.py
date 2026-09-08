from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from weather_forecast.ui.presenters import (  # noqa: E402
    CurrentWeatherRenderModel,
    DailyForecastRenderModel,
    HourlyForecastRenderModel,
    SELECT_LOCATION_MESSAGE,
    UPDATING_MESSAGE,
    WeatherContentRenderModel,
    WeatherDisplayRenderModel,
)
from weather_forecast.ui.weather_display import WeatherDisplayView  # noqa: E402


def content(timestamp: str = "Last updated: 2026-08-26 14:37 Europe/Berlin"):
    return WeatherContentRenderModel(
        location_header="Berlin, Germany",
        current=CurrentWeatherRenderModel(
            temperature="21.5 °C",
            condition="Partly cloudy",
            feels_like="20.25 °C",
            precipitation_probability="25%",
            relative_humidity="61%",
            wind_speed="13.4 km/h",
            precipitation="0.2 mm",
        ),
        hourly=tuple(
            HourlyForecastRenderModel(
                local_time=f"{hour % 24:02d}:00",
                temperature=f"{10 + hour} °C",
                condition="Rain",
                precipitation_probability=f"{hour}%",
            )
            for hour in range(24)
        ),
        daily=tuple(
            DailyForecastRenderModel(
                local_date=f"2026-0{8 if day < 6 else 9}-{26 + day if day < 6 else 1:02d}",
                minimum_temperature=f"{10 + day} °C",
                maximum_temperature=f"{20 + day} °C",
                condition="Snow",
                precipitation_probability=f"{30 + day}%",
                precipitation=f"{day + 0.5:g} mm",
            )
            for day in range(7)
        ),
        last_updated=timestamp,
    )


def weather_model(
    *,
    displayed: WeatherContentRenderModel | None = None,
    instruction: str | None = None,
    loading: bool = False,
    error: str | None = None,
) -> WeatherDisplayRenderModel:
    return WeatherDisplayRenderModel(
        instruction=instruction,
        content=displayed,
        loading=loading,
        loading_message=UPDATING_MESSAGE if loading else None,
        error_message=error,
    )


class WeatherDisplayViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.view = WeatherDisplayView()
        self.view.resize(800, 600)
        self.view.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.view.close()
        self.view.deleteLater()
        self.app.processEvents()

    def visible_text(self) -> str:
        return " ".join(
            label.text() for label in self.view.findChildren(QLabel) if label.isVisible()
        )

    def test_initial_and_failed_first_states_show_no_fabricated_or_requested_weather(self) -> None:
        self.view.render(
            weather_model(
                instruction=SELECT_LOCATION_MESSAGE,
                error="Weather could not be updated. Please try again.",
            )
        )

        text = self.visible_text()
        self.assertIn(SELECT_LOCATION_MESSAGE, text)
        self.assertIn("Weather could not be updated", text)
        self.assertNotIn("Berlin", text)
        self.assertNotIn("°C", text)
        self.assertFalse(self.view.vertical_scroll.isVisible())

    def test_active_header_and_all_current_values_and_units_are_visible(self) -> None:
        self.view.render(weather_model(displayed=content()))

        self.assertEqual(self.view.location_header.text(), "Berlin, Germany")
        self.assertEqual(
            {key: label.text() for key, label in self.view.current_labels.items()},
            {
                "temperature": "21.5 °C",
                "condition": "Partly cloudy",
                "feels_like": "20.25 °C",
                "precipitation_probability": "25%",
                "relative_humidity": "61%",
                "wind_speed": "13.4 km/h",
                "precipitation": "0.2 mm",
            },
        )

    def test_all_24_local_hourly_entries_are_horizontally_accessible(self) -> None:
        self.view.render(weather_model(displayed=content()))
        self.app.processEvents()

        self.assertEqual(len(self.view.hourly_cards), 24)
        self.assertEqual(self.view.hourly_cards[0].title(), "00:00")
        self.assertEqual(self.view.hourly_cards[-1].title(), "23:00")
        self.assertGreater(self.view.hourly_scroll.horizontalScrollBar().maximum(), 0)
        self.view.hourly_scroll.horizontalScrollBar().setValue(
            self.view.hourly_scroll.horizontalScrollBar().maximum()
        )
        self.assertEqual(
            self.view.hourly_scroll.horizontalScrollBar().value(),
            self.view.hourly_scroll.horizontalScrollBar().maximum(),
        )

    def test_all_seven_daily_provider_aggregates_are_displayed(self) -> None:
        self.view.render(weather_model(displayed=content()))

        self.assertEqual(len(self.view.daily_cards), 7)
        first_text = " ".join(
            label.text() for label in self.view.daily_cards[0].findChildren(QLabel)
        )
        self.assertIn("10 °C", first_text)
        self.assertIn("20 °C", first_text)
        self.assertIn("Snow", first_text)
        self.assertIn("30%", first_text)
        self.assertIn("0.5 mm", first_text)

    def test_exact_local_last_updated_text_is_rendered(self) -> None:
        self.view.render(weather_model(displayed=content()))

        self.assertEqual(
            self.view.last_updated_label.text(),
            "Last updated: 2026-08-26 14:37 Europe/Berlin",
        )

    def test_update_and_error_keep_existing_content_and_timestamp_accessible(self) -> None:
        timestamp = "Last updated: 2026-08-26 14:37 Europe/Berlin"
        self.view.render(
            weather_model(
                displayed=content(timestamp),
                loading=True,
                error="Weather could not be updated. Please try again.",
            )
        )

        self.assertTrue(self.view.loading_label.isVisible())
        self.assertTrue(self.view.error_label.isVisible())
        self.assertTrue(self.view.vertical_scroll.isVisible())
        self.assertTrue(self.view.vertical_scroll.isEnabled())
        self.assertEqual(self.view.location_header.text(), "Berlin, Germany")
        self.assertEqual(self.view.last_updated_label.text(), timestamp)

    def test_vertical_and_horizontal_layout_keep_sections_reachable_at_800_by_600(self) -> None:
        self.view.render(weather_model(displayed=content()))
        self.app.processEvents()

        self.assertEqual(self.view.size().width(), 800)
        self.assertEqual(self.view.size().height(), 600)
        self.assertGreater(self.view.vertical_scroll.verticalScrollBar().maximum(), 0)
        self.assertGreater(self.view.hourly_scroll.horizontalScrollBar().maximum(), 0)
        vertical_bar = self.view.vertical_scroll.verticalScrollBar()
        vertical_bar.setValue(vertical_bar.maximum())
        self.assertEqual(vertical_bar.value(), vertical_bar.maximum())
        self.assertTrue(self.view.last_updated_label.isVisible())


if __name__ == "__main__":
    unittest.main()
