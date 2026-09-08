from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.domain.failures import InvalidResponseFailure  # noqa: E402
from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.domain.weather import WeatherCondition, WeatherPayload  # noqa: E402
from weather_forecast.infrastructure.open_meteo_weather import (  # noqa: E402
    CURRENT_FIELDS,
    DAILY_FIELDS,
    FORECAST_ENDPOINT,
    HOURLY_FIELDS,
    build_weather_url,
    map_weather_code,
    parse_weather_response,
)


BERLIN = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")


def fixture_bytes() -> bytes:
    return (FIXTURES / "weather_valid.json").read_bytes()


def fixture_document() -> dict:
    return json.loads(fixture_bytes())


def encoded(document: object) -> bytes:
    return json.dumps(document).encode()


class OpenMeteoWeatherRequestTests(unittest.TestCase):
    def test_builds_finalized_eight_day_request_with_explicit_units(self) -> None:
        parts = urlsplit(build_weather_url(BERLIN))
        query = parse_qs(parts.query)

        self.assertEqual(f"{parts.scheme}://{parts.netloc}{parts.path}", FORECAST_ENDPOINT)
        self.assertEqual(query["latitude"], ["52.52"])
        self.assertEqual(query["longitude"], ["13.405"])
        self.assertEqual(query["timezone"], ["auto"])
        self.assertEqual(query["temperature_unit"], ["celsius"])
        self.assertEqual(query["wind_speed_unit"], ["kmh"])
        self.assertEqual(query["precipitation_unit"], ["mm"])
        self.assertEqual(query["forecast_days"], ["8"])
        self.assertEqual(query["current"][0].split(","), list(CURRENT_FIELDS))
        self.assertEqual(query["hourly"][0].split(","), list(HOURLY_FIELDS))
        self.assertEqual(query["daily"][0].split(","), list(DAILY_FIELDS))


class WeatherCodeMappingTests(unittest.TestCase):
    def test_maps_every_finalized_wmo_code_group(self) -> None:
        expected = {
            WeatherCondition.CLEAR: (0,),
            WeatherCondition.PARTLY_CLOUDY: (1, 2),
            WeatherCondition.CLOUDY: (3,),
            WeatherCondition.FOG: (45, 48),
            WeatherCondition.RAIN: (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82),
            WeatherCondition.SNOW: (71, 73, 75, 77, 85, 86),
            WeatherCondition.STORM: (95, 96, 99),
        }
        for condition, codes in expected.items():
            for code in codes:
                with self.subTest(code=code):
                    self.assertIs(map_weather_code(code), condition)

    def test_unsupported_integer_codes_map_to_unknown(self) -> None:
        for code in (-1, 4, 50, 100, 1000):
            with self.subTest(code=code):
                self.assertIs(map_weather_code(code), WeatherCondition.UNKNOWN)


class OpenMeteoWeatherConversionTests(unittest.TestCase):
    def test_converts_complete_response_to_provider_independent_payload(self) -> None:
        payload = parse_weather_response(fixture_bytes())

        self.assertIsInstance(payload, WeatherPayload)
        self.assertEqual(payload.time_zone_id, "Europe/Berlin")
        self.assertEqual(payload.current.temperature_c, 21.5)
        self.assertEqual(payload.current.feels_like_c, 20.2)
        self.assertIs(payload.current.condition, WeatherCondition.PARTLY_CLOUDY)
        self.assertEqual(payload.current.relative_humidity_percent, 61)
        self.assertEqual(payload.current.wind_speed_kmh, 13.4)
        self.assertEqual(payload.current.precipitation_probability_percent, 25)
        self.assertEqual(payload.current.precipitation_mm, 0.2)

    def test_converts_aware_local_hours_and_provider_daily_aggregates(self) -> None:
        payload = parse_weather_response(fixture_bytes())

        self.assertEqual(len(payload.hourly), 39)
        self.assertEqual(
            payload.hourly[0].local_time,
            datetime(2026, 8, 26, tzinfo=ZoneInfo("Europe/Berlin")),
        )
        self.assertEqual(payload.hourly[0].local_time.tzinfo.key, "Europe/Berlin")
        self.assertEqual(len(payload.daily), 8)
        self.assertEqual(payload.daily[0].local_date, date(2026, 8, 26))
        self.assertEqual(payload.daily[1].minimum_temperature_c, 11)
        self.assertEqual(payload.daily[1].maximum_temperature_c, 21)
        self.assertEqual(payload.daily[1].precipitation_probability_percent, 10)
        self.assertEqual(payload.daily[1].precipitation_mm, 0.1)
        self.assertIs(payload.daily[-1].condition, WeatherCondition.UNKNOWN)

    def test_fixture_covers_acceptance_time_windows(self) -> None:
        payload = parse_weather_response(fixture_bytes())
        acceptance_hour = datetime(2026, 8, 26, 14, tzinfo=ZoneInfo("Europe/Berlin"))

        hourly_start = next(i for i, entry in enumerate(payload.hourly) if entry.local_time == acceptance_hour)
        self.assertEqual(len(payload.hourly[hourly_start : hourly_start + 24]), 24)
        self.assertEqual(len(payload.daily[:7]), 7)

    def test_invalid_whole_responses_are_rejected(self) -> None:
        cases: dict[str, bytes] = {"malformed_json": b"not json", "top_level": b"[]"}
        base = fixture_document()

        missing = copy.deepcopy(base)
        del missing["current"]["temperature_2m"]
        cases["missing_field"] = encoded(missing)

        mismatch = copy.deepcopy(base)
        mismatch["hourly"]["weather_code"] = mismatch["hourly"]["weather_code"][:-1]
        cases["mismatched_series"] = encoded(mismatch)

        malformed_schema = copy.deepcopy(base)
        malformed_schema["daily"] = []
        cases["malformed_schema"] = encoded(malformed_schema)

        non_finite = copy.deepcopy(base)
        non_finite["current"]["temperature_2m"] = float("nan")
        cases["non_finite_number"] = encoded(non_finite)

        invalid_number = copy.deepcopy(base)
        invalid_number["current"]["relative_humidity_2m"] = 101
        cases["invalid_percentage"] = encoded(invalid_number)

        negative = copy.deepcopy(base)
        negative["daily"]["precipitation_sum"][0] = -1
        cases["negative_precipitation"] = encoded(negative)

        invalid_code = copy.deepcopy(base)
        invalid_code["current"]["weather_code"] = "clear"
        cases["invalid_weather_code"] = encoded(invalid_code)

        unusable_zone = copy.deepcopy(base)
        unusable_zone["timezone"] = "Not/A_Zone"
        cases["unusable_zone"] = encoded(unusable_zone)

        inadequate_hourly = copy.deepcopy(base)
        for key in inadequate_hourly["hourly"]:
            inadequate_hourly["hourly"][key] = inadequate_hourly["hourly"][key][:23]
        cases["inadequate_hourly"] = encoded(inadequate_hourly)

        inadequate_daily = copy.deepcopy(base)
        for key in inadequate_daily["daily"]:
            inadequate_daily["daily"][key] = inadequate_daily["daily"][key][:6]
        cases["inadequate_daily"] = encoded(inadequate_daily)

        for name, body in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(InvalidResponseFailure):
                    parse_weather_response(body)


if __name__ == "__main__":
    unittest.main()
