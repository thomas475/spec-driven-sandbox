from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.domain.failures import InvalidResponseFailure  # noqa: E402
from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.infrastructure.open_meteo_location import (  # noqa: E402
    GEOCODING_ENDPOINT,
    build_location_search_url,
    parse_location_response,
)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class OpenMeteoLocationRequestTests(unittest.TestCase):
    def test_builds_encoded_request_from_trimmed_query(self) -> None:
        url = build_location_search_url("  New York / Berlin  ")
        parts = urlsplit(url)

        self.assertEqual(
            f"{parts.scheme}://{parts.netloc}{parts.path}",
            GEOCODING_ENDPOINT,
        )
        self.assertEqual(parse_qs(parts.query), {"name": ["New York / Berlin"]})
        self.assertNotIn(" ", url)

    def test_rejects_empty_submitted_query(self) -> None:
        with self.assertRaises(ValueError):
            build_location_search_url(" \t ")


class OpenMeteoLocationConversionTests(unittest.TestCase):
    def test_converts_coordinates_required_metadata_and_optional_region(self) -> None:
        locations = parse_location_response(fixture("location_valid.json"))

        self.assertEqual(len(locations), 2)
        self.assertIsInstance(locations[0], Location)
        self.assertEqual(
            (
                locations[0].latitude,
                locations[0].longitude,
                locations[0].city,
                locations[0].country,
                locations[0].region,
            ),
            (52.52437, 13.41053, "Berlin", "Germany", "Berlin"),
        )
        self.assertIsNone(locations[1].region)

    def test_discards_malformed_siblings_without_losing_valid_entries(self) -> None:
        locations = parse_location_response(fixture("location_mixed.json"))

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].city, "Berlin")

    def test_duplicate_names_remain_separate(self) -> None:
        locations = parse_location_response(fixture("location_valid.json"))

        self.assertEqual([location.city for location in locations], ["Berlin", "Berlin"])
        self.assertNotEqual(locations[0].latitude, locations[1].latitude)

    def test_wholly_invalid_entries_are_a_successful_empty_result(self) -> None:
        self.assertEqual(
            parse_location_response(fixture("location_invalid_entries.json")),
            (),
        )
        self.assertEqual(parse_location_response(b"{}"), ())

    def test_malformed_top_level_json_or_schema_is_invalid_response(self) -> None:
        malformed_bodies = (
            b"not json",
            b"[]",
            b'{"results": null}',
            b'{"results": {}}',
            b"\xff",
        )

        for body in malformed_bodies:
            with self.subTest(body=body):
                with self.assertRaises(InvalidResponseFailure):
                    parse_location_response(body)


if __name__ == "__main__":
    unittest.main()
