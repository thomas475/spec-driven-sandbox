"""Provider-independent location values."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True, eq=False)
class Location:
    """A geographic location identified exclusively by its coordinates."""

    latitude: float
    longitude: float
    city: str
    country: str
    region: str | None = None

    def __post_init__(self) -> None:
        self._validate_coordinate("latitude", self.latitude, -90.0, 90.0)
        self._validate_coordinate("longitude", self.longitude, -180.0, 180.0)
        self._validate_required_text("city", self.city)
        self._validate_required_text("country", self.country)
        if self.region is not None and not isinstance(self.region, str):
            raise TypeError("region must be a string or None")

    @staticmethod
    def _validate_coordinate(
        name: str, value: float, minimum: float, maximum: float
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")
        if not isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"{name} must be finite and between {minimum} and {maximum}")

    @staticmethod
    def _validate_required_text(name: str, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if not value.strip():
            raise ValueError(f"{name} must not be empty")

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Location):
            return NotImplemented
        return self.latitude == other.latitude and self.longitude == other.longitude

    def __hash__(self) -> int:
        return hash((self.latitude, self.longitude))

