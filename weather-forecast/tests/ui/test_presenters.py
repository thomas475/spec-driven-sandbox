from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.application.state import (  # noqa: E402
    ApplicationState,
    SearchResultState,
    WeatherLoading,
)
from weather_forecast.domain.failures import UserFacingError  # noqa: E402
from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.domain.weather import (  # noqa: E402
    CurrentWeather,
    DailyForecastEntry,
    HourlyForecastEntry,
    LoadedWeather,
    WeatherCondition,
    WeatherReport,
)
from weather_forecast.ui.presenters import (  # noqa: E402
    NO_RESULTS_MESSAGE,
    SEARCHING_MESSAGE,
    SELECT_LOCATION_MESSAGE,
    UPDATING_MESSAGE,
    condition_label,
    present_application,
)


ZONE = ZoneInfo("Europe/Berlin")
BERLIN = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")
PARIS = Location(48.8575, 2.3514, "Paris", "France")


def loaded_weather() -> LoadedWeather:
    updated = datetime(2026, 8, 26, 14, 37, tzinfo=ZONE)
    current = CurrentWeather(
        21.5,
        20.25,
        WeatherCondition.PARTLY_CLOUDY,
        61,
        13.4,
        25,
        0.2,
    )
    hourly = tuple(
        HourlyForecastEntry(
            updated.replace(minute=0) + timedelta(hours=index),
            10 + index,
            WeatherCondition.RAIN,
            index,
        )
        for index in range(24)
    )
    daily = tuple(
        DailyForecastEntry(
            date(2026, 8, 26) + timedelta(days=index),
            10 + index,
            20 + index,
            WeatherCondition.SNOW,
            30 + index,
            0.5 + index,
        )
        for index in range(7)
    )
    return LoadedWeather(
        BERLIN,
        WeatherReport("Europe/Berlin", current, hourly, daily),
        updated,
    )


class PresenterTests(unittest.TestCase):
    def test_search_results_format_required_metadata_and_optional_region(self) -> None:
        model = present_application(
            ApplicationState(
                search_results=(BERLIN, PARIS),
                search_result_state=SearchResultState.RESULTS,
            )
        ).search

        self.assertEqual(model.results[0].display_text, "Berlin, Berlin, Germany")
        self.assertEqual(model.results[0].region, "Berlin")
        self.assertIs(model.results[0].location, BERLIN)
        self.assertEqual(model.results[1].display_text, "Paris, France")
        self.assertIsNone(model.results[1].region)

    def test_every_current_hourly_and_daily_value_has_required_representation(self) -> None:
        content = present_application(
            ApplicationState(loaded_weather=loaded_weather())
        ).weather.content
        self.assertIsNotNone(content)
        assert content is not None

        self.assertEqual(content.location_header, "Berlin, Germany")
        self.assertEqual(content.current.temperature, "21.5 °C")
        self.assertEqual(content.current.feels_like, "20.25 °C")
        self.assertEqual(content.current.precipitation_probability, "25%")
        self.assertEqual(content.current.relative_humidity, "61%")
        self.assertEqual(content.current.wind_speed, "13.4 km/h")
        self.assertEqual(content.current.precipitation, "0.2 mm")
        self.assertEqual(len(content.hourly), 24)
        self.assertEqual(content.hourly[0].local_time, "14:00")
        self.assertEqual(content.hourly[0].temperature, "10 °C")
        self.assertEqual(content.hourly[0].precipitation_probability, "0%")
        self.assertEqual(len(content.daily), 7)
        self.assertEqual(content.daily[0].local_date, "2026-08-26")
        self.assertEqual(content.daily[0].minimum_temperature, "10 °C")
        self.assertEqual(content.daily[0].maximum_temperature, "20 °C")
        self.assertEqual(content.daily[0].precipitation_probability, "30%")
        self.assertEqual(content.daily[0].precipitation, "0.5 mm")

    def test_all_condition_labels_include_safe_unknown(self) -> None:
        expected = {
            WeatherCondition.CLEAR: "Clear",
            WeatherCondition.PARTLY_CLOUDY: "Partly cloudy",
            WeatherCondition.CLOUDY: "Cloudy",
            WeatherCondition.FOG: "Fog",
            WeatherCondition.RAIN: "Rain",
            WeatherCondition.SNOW: "Snow",
            WeatherCondition.STORM: "Storm",
            WeatherCondition.UNKNOWN: "Unknown",
        }
        self.assertEqual(
            {condition: condition_label(condition) for condition in WeatherCondition},
            expected,
        )

    def test_last_updated_uses_exact_local_iana_format(self) -> None:
        content = present_application(
            ApplicationState(loaded_weather=loaded_weather())
        ).weather.content

        assert content is not None
        self.assertEqual(
            content.last_updated,
            "Last updated: 2026-08-26 14:37 Europe/Berlin",
        )

    def test_initial_loading_and_no_results_have_explicit_representations(self) -> None:
        initial = present_application(ApplicationState())
        self.assertEqual(initial.weather.instruction, SELECT_LOCATION_MESSAGE)
        self.assertIsNone(initial.weather.content)
        self.assertFalse(initial.search.loading)

        loading = present_application(
            ApplicationState(
                search_loading=True,
                weather_loading=WeatherLoading.LOCATION_LOAD,
            )
        )
        self.assertEqual(loading.search.loading_message, SEARCHING_MESSAGE)
        self.assertEqual(loading.weather.loading_message, UPDATING_MESSAGE)
        self.assertEqual(loading.weather.instruction, SELECT_LOCATION_MESSAGE)

        no_results = present_application(
            ApplicationState(search_result_state=SearchResultState.NO_RESULTS)
        )
        self.assertEqual(no_results.search.empty_message, NO_RESULTS_MESSAGE)

    def test_loaded_content_remains_present_during_refresh_and_failure(self) -> None:
        loaded = loaded_weather()
        model = present_application(
            ApplicationState(
                loaded_weather=loaded,
                weather_loading=WeatherLoading.REFRESH,
                weather_error=UserFacingError.WEATHER_UPDATE_FAILED,
            )
        ).weather

        self.assertIsNotNone(model.content)
        self.assertIsNone(model.instruction)
        self.assertTrue(model.loading)
        self.assertIsNotNone(model.error_message)

    def test_search_and_weather_errors_are_independent_and_redacted(self) -> None:
        base = ApplicationState(
            search_error=UserFacingError.LOCATION_CONNECTION,
            weather_error=UserFacingError.WEATHER_UPDATE_FAILED,
        )
        model = present_application(base)

        self.assertEqual(
            model.search.error_message,
            "Unable to connect to the location service. Please try again.",
        )
        self.assertEqual(
            model.weather.error_message,
            "Weather could not be updated. Please try again.",
        )
        generic = present_application(
            replace(base, search_error=UserFacingError.LOCATION_SEARCH_FAILED)
        )
        self.assertEqual(
            generic.search.error_message,
            "Unable to search for locations. Please try again.",
        )

        all_messages = " ".join(
            message
            for message in (
                model.search.error_message,
                model.weather.error_message,
                generic.search.error_message,
            )
            if message is not None
        ).lower()
        for forbidden in ("http", "https://", "payload", "exception", "qt", "open-meteo"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, all_messages)


if __name__ == "__main__":
    unittest.main()
