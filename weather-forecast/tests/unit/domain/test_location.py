from __future__ import annotations

import math
import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.domain.location import Location  # noqa: E402


class LocationTests(unittest.TestCase):
    def test_accepts_boundary_coordinates_and_optional_region(self) -> None:
        with_region = Location(90.0, -180.0, "Longyearbyen", "Norway", "Svalbard")
        without_region = Location(-90.0, 180.0, "South Pole", "Antarctica")

        self.assertEqual(with_region.region, "Svalbard")
        self.assertIsNone(without_region.region)

    def test_rejects_non_finite_coordinates(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(latitude=value):
                with self.assertRaises(ValueError):
                    Location(value, 0.0, "City", "Country")
            with self.subTest(longitude=value):
                with self.assertRaises(ValueError):
                    Location(0.0, value, "City", "Country")

    def test_rejects_out_of_range_coordinates(self) -> None:
        for latitude in (-90.0001, 90.0001):
            with self.subTest(latitude=latitude):
                with self.assertRaises(ValueError):
                    Location(latitude, 0.0, "City", "Country")
        for longitude in (-180.0001, 180.0001):
            with self.subTest(longitude=longitude):
                with self.assertRaises(ValueError):
                    Location(0.0, longitude, "City", "Country")

    def test_rejects_non_numeric_coordinates_including_booleans(self) -> None:
        for latitude in ("52.52", None, True):
            with self.subTest(latitude=latitude):
                with self.assertRaises(TypeError):
                    Location(latitude, 13.405, "Berlin", "Germany")  # type: ignore[arg-type]

    def test_requires_non_empty_city_and_country(self) -> None:
        for city, country in (("", "Germany"), ("   ", "Germany"), ("Berlin", ""), ("Berlin", "\t")):
            with self.subTest(city=city, country=country):
                with self.assertRaises(ValueError):
                    Location(52.52, 13.405, city, country)

    def test_region_must_be_a_string_or_none(self) -> None:
        with self.assertRaises(TypeError):
            Location(52.52, 13.405, "Berlin", "Germany", 123)  # type: ignore[arg-type]

    def test_identity_and_hash_use_only_coordinates(self) -> None:
        first = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")
        renamed = Location(52.52, 13.405, "Different metadata", "Elsewhere")
        same_name_elsewhere = Location(40.0, -75.0, "Berlin", "Germany")

        self.assertEqual(first, renamed)
        self.assertEqual(hash(first), hash(renamed))
        self.assertNotEqual(first, same_name_elsewhere)
        self.assertEqual(len({first, renamed, same_name_elsewhere}), 2)

    def test_is_immutable(self) -> None:
        location = Location(52.52, 13.405, "Berlin", "Germany")

        with self.assertRaises(FrozenInstanceError):
            location.city = "Munich"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()

