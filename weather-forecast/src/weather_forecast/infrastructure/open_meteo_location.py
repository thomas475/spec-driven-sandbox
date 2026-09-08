"""Open-Meteo geocoding request construction and response conversion."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from weather_forecast.application.ports import OperationId, RequestHandle
from weather_forecast.domain.failures import InvalidResponseFailure, ServiceFailure
from weather_forecast.domain.location import Location
from weather_forecast.infrastructure.qt_network import QtNetworkTransport


GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"


class OpenMeteoLocationProvider:
    """Asynchronous Open-Meteo implementation of the location provider port."""

    def __init__(self, transport: QtNetworkTransport) -> None:
        self._transport = transport

    def search(
        self,
        query: str,
        operation_id: OperationId,
        on_success: Callable[[OperationId, tuple[Location, ...]], None],
        on_failure: Callable[[OperationId, ServiceFailure], None],
    ) -> RequestHandle:
        def response_received(body: bytes) -> None:
            try:
                locations = parse_location_response(body)
            except InvalidResponseFailure as failure:
                on_failure(operation_id, failure)
            else:
                on_success(operation_id, locations)

        return self._transport.get(
            build_location_search_url(query),
            response_received,
            lambda failure: on_failure(operation_id, failure),
        )


def build_location_search_url(query: str) -> str:
    """Build an encoded Open-Meteo geocoding URL for a submitted query."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    submitted_query = query.strip()
    if not submitted_query:
        raise ValueError("query must not be empty after trimming")
    return f"{GEOCODING_ENDPOINT}?{urlencode({'name': submitted_query})}"


def parse_location_response(body: bytes | str) -> tuple[Location, ...]:
    """Convert a complete geocoding response into valid internal locations."""
    try:
        document = json.loads(body)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as error:
        raise InvalidResponseFailure() from error

    if not isinstance(document, dict):
        raise InvalidResponseFailure()

    results = document.get("results", [])
    if not isinstance(results, list):
        raise InvalidResponseFailure()

    return tuple(
        location
        for entry in results
        if (location := _parse_location(entry)) is not None
    )


def _parse_location(entry: Any) -> Location | None:
    if not isinstance(entry, dict):
        return None

    try:
        region = entry.get("admin1")
        if region is not None and not isinstance(region, str):
            return None
        return Location(
            latitude=entry["latitude"],
            longitude=entry["longitude"],
            city=entry["name"],
            country=entry["country"],
            region=region,
        )
    except (KeyError, TypeError, ValueError):
        return None
