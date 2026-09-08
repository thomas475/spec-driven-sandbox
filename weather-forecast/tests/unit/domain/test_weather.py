from __future__ import annotations

import math
import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.domain.weather import (  # noqa: E402
    CurrentWeather,
    DailyForecastEntry,
    HourlyForecastEntry,
    LoadedWeather,
    WeatherCondition,
    WeatherPayload,
    WeatherReport,
)


BERLIN = ZoneInfo("Europe/Berlin")
ACCEPTED_AT = datetime(2026, 8, 26, 14, 37, tzinfo=BERLIN)


def current_weather(**changes: object) -> CurrentWeather:
    values: dict[str, object] = {
        "temperature_c": 20.0,
        "feels_like_c": 19.0,
        "condition": WeatherCondition.CLEAR,
        "relative_humidity_percent": 60.0,
        "wind_speed_kmh": 12.0,
        "precipitation_probability_percent": 20.0,
        "precipitation_mm": 0.0,
    }
    values.update(changes)
    return CurrentWeather(**values)  # type: ignore[arg-type]


def hourly_entries(
    count: int = 24,
    start: datetime = ACCEPTED_AT.replace(minute=0),
) -> tuple[HourlyForecastEntry, ...]:
    return tuple(
        HourlyForecastEntry(
            local_time=start + timedelta(hours=index),
            temperature_c=20.0 + index,
            condition=WeatherCondition.PARTLY_CLOUDY,
            precipitation_probability_percent=10.0,
        )
        for index in range(count)
    )


def daily_entries(
    count: int = 7,
    start: date = ACCEPTED_AT.date(),
) -> tuple[DailyForecastEntry, ...]:
    return tuple(
        DailyForecastEntry(
            local_date=start + timedelta(days=index),
            minimum_temperature_c=10.0,
            maximum_temperature_c=22.0,
            condition=WeatherCondition.CLOUDY,
            precipitation_probability_percent=30.0,
            precipitation_mm=1.5,
        )
        for index in range(count)
    )


def weather_report(**changes: object) -> WeatherReport:
    values: dict[str, object] = {
        "time_zone_id": "Europe/Berlin",
        "current": current_weather(),
        "hourly": hourly_entries(),
        "daily": daily_entries(),
    }
    values.update(changes)
    return WeatherReport(**values)  # type: ignore[arg-type]


class WeatherConditionTests(unittest.TestCase):
    def test_contains_the_eight_provider_independent_conditions(self) -> None:
        self.assertEqual(
            {condition.value for condition in WeatherCondition},
            {
                "clear",
                "partly_cloudy",
                "cloudy",
                "fog",
                "rain",
                "snow",
                "storm",
                "unknown",
            },
        )


class WeatherValueTests(unittest.TestCase):
    def test_current_weather_accepts_percentage_boundaries(self) -> None:
        weather = current_weather(
            relative_humidity_percent=0.0,
            precipitation_probability_percent=100.0,
        )

        self.assertEqual(weather.relative_humidity_percent, 0.0)
        self.assertEqual(weather.precipitation_probability_percent, 100.0)

    def test_rejects_non_finite_numeric_weather_values(self) -> None:
        fields = (
            "temperature_c",
            "feels_like_c",
            "relative_humidity_percent",
            "wind_speed_kmh",
            "precipitation_probability_percent",
            "precipitation_mm",
        )
        for field in fields:
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        current_weather(**{field: value})

    def test_rejects_out_of_range_percentages(self) -> None:
        for field in (
            "relative_humidity_percent",
            "precipitation_probability_percent",
        ):
            for value in (-0.1, 100.1):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        current_weather(**{field: value})

        for value in (-0.1, 100.1):
            with self.subTest(hourly_probability=value):
                with self.assertRaises(ValueError):
                    HourlyForecastEntry(
                        ACCEPTED_AT.replace(minute=0),
                        20.0,
                        WeatherCondition.RAIN,
                        value,
                    )
            with self.subTest(daily_probability=value):
                with self.assertRaises(ValueError):
                    DailyForecastEntry(
                        ACCEPTED_AT.date(),
                        10.0,
                        20.0,
                        WeatherCondition.RAIN,
                        value,
                        1.0,
                    )

    def test_rejects_negative_wind_and_precipitation(self) -> None:
        for field in ("wind_speed_kmh", "precipitation_mm"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    current_weather(**{field: -0.1})
        with self.assertRaises(ValueError):
            DailyForecastEntry(
                ACCEPTED_AT.date(),
                10.0,
                20.0,
                WeatherCondition.RAIN,
                20.0,
                -0.1,
            )

    def test_hourly_time_must_be_an_iana_aligned_hour(self) -> None:
        for invalid_time in (
            datetime(2026, 8, 26, 14),
            datetime(2026, 8, 26, 14, tzinfo=ZoneInfo("UTC")).replace(minute=1),
        ):
            with self.subTest(invalid_time=invalid_time):
                with self.assertRaises(ValueError):
                    HourlyForecastEntry(
                        invalid_time,
                        20.0,
                        WeatherCondition.CLEAR,
                        0.0,
                    )

    def test_values_are_immutable(self) -> None:
        weather = current_weather()

        with self.assertRaises(FrozenInstanceError):
            weather.temperature_c = 21.0  # type: ignore[misc]


class ForecastAggregateTests(unittest.TestCase):
    def test_payload_accepts_sufficient_consecutive_coverage(self) -> None:
        payload = WeatherPayload(
            "Europe/Berlin",
            current_weather(),
            hourly_entries(48),
            daily_entries(8),
        )

        self.assertEqual(len(payload.hourly), 48)
        self.assertEqual(len(payload.daily), 8)

    def test_payload_rejects_insufficient_coverage(self) -> None:
        with self.assertRaises(ValueError):
            WeatherPayload(
                "Europe/Berlin", current_weather(), hourly_entries(23), daily_entries()
            )
        with self.assertRaises(ValueError):
            WeatherPayload(
                "Europe/Berlin", current_weather(), hourly_entries(), daily_entries(6)
            )

    def test_rejects_unresolvable_time_zone(self) -> None:
        with self.assertRaises(ValueError):
            WeatherPayload(
                "Not/AZone", current_weather(), hourly_entries(), daily_entries()
            )

    def test_rejects_hourly_entries_from_a_different_time_zone(self) -> None:
        utc_entries = hourly_entries(
            start=ACCEPTED_AT.astimezone(ZoneInfo("UTC")).replace(minute=0)
        )
        with self.assertRaises(ValueError):
            WeatherPayload(
                "Europe/Berlin", current_weather(), utc_entries, daily_entries()
            )

    def test_rejects_non_consecutive_hourly_entries(self) -> None:
        entries = list(hourly_entries())
        entries[12] = HourlyForecastEntry(
            entries[12].local_time + timedelta(hours=1),
            entries[12].temperature_c,
            entries[12].condition,
            entries[12].precipitation_probability_percent,
        )
        with self.assertRaises(ValueError):
            WeatherPayload(
                "Europe/Berlin", current_weather(), tuple(entries), daily_entries()
            )

    def test_rejects_non_consecutive_daily_entries(self) -> None:
        entries = list(daily_entries())
        entries[3] = DailyForecastEntry(
            entries[3].local_date + timedelta(days=1),
            entries[3].minimum_temperature_c,
            entries[3].maximum_temperature_c,
            entries[3].condition,
            entries[3].precipitation_probability_percent,
            entries[3].precipitation_mm,
        )
        with self.assertRaises(ValueError):
            WeatherPayload(
                "Europe/Berlin", current_weather(), hourly_entries(), tuple(entries)
            )

    def test_report_requires_exact_24_hour_and_7_day_windows(self) -> None:
        for count in (23, 25):
            with self.subTest(hourly_count=count):
                with self.assertRaises(ValueError):
                    weather_report(hourly=hourly_entries(count))
        for count in (6, 8):
            with self.subTest(daily_count=count):
                with self.assertRaises(ValueError):
                    weather_report(daily=daily_entries(count))

    def test_loaded_weather_anchors_report_to_acceptance_time_and_location(self) -> None:
        location = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")
        report = weather_report()

        loaded = LoadedWeather(location, report, ACCEPTED_AT)

        self.assertIs(loaded.location, location)
        self.assertIs(loaded.report, report)
        self.assertEqual(loaded.last_updated, ACCEPTED_AT)

    def test_loaded_weather_rejects_wrong_hour_date_or_time_zone(self) -> None:
        location = Location(52.52, 13.405, "Berlin", "Germany")
        cases = (
            (
                weather_report(hourly=hourly_entries(start=datetime(2026, 8, 26, 15, tzinfo=BERLIN))),
                ACCEPTED_AT,
            ),
            (weather_report(daily=daily_entries(start=date(2026, 8, 27))), ACCEPTED_AT),
            (weather_report(), ACCEPTED_AT.astimezone(ZoneInfo("UTC"))),
        )
        for report, accepted_at in cases:
            with self.subTest(report=report, accepted_at=accepted_at):
                with self.assertRaises(ValueError):
                    LoadedWeather(location, report, accepted_at)


if __name__ == "__main__":
    unittest.main()
