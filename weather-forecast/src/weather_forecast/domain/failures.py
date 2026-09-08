"""Failures shared across application boundaries."""

from __future__ import annotations

from enum import Enum


class ServiceFailure(Exception):
    """Base type for an expected external-service failure."""

    def __init__(self) -> None:
        super().__init__()


class ConnectionFailure(ServiceFailure):
    """The external service could not be reached."""


class TimeoutFailure(ServiceFailure):
    """The external request exceeded its deadline."""


class HttpFailure(ServiceFailure):
    """The external service returned an unsuccessful HTTP response."""


class InvalidResponseFailure(ServiceFailure):
    """The external response could not form a valid internal model."""


class UserFacingError(Enum):
    """Semantic error categories safe for the presentation layer."""

    LOCATION_CONNECTION = "location_connection"
    LOCATION_SEARCH_FAILED = "location_search_failed"
    WEATHER_UPDATE_FAILED = "weather_update_failed"

