"""Open-Meteo forecast request construction and response conversion."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from weather_forecast.application.ports import OperationId, RequestHandle
from weather_forecast.domain.failures import InvalidResponseFailure, ServiceFailure
from weather_forecast.domain.location import Location
from weather_forecast.domain.weather import (
    CurrentWeather,
    DailyForecastEntry,
    HourlyForecastEntry,
    WeatherCondition,
    WeatherPayload,
)
from weather_forecast.infrastructure.qt_network import QtNetworkTransport


FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "weather_code",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation_probability",
    "precipitation",
)
HOURLY_FIELDS = (
    "temperature_2m",
    "weather_code",
    "precipitation_probability",
)
DAILY_FIELDS = (
    "temperature_2m_min",
    "temperature_2m_max",
    "weather_code",
    "precipitation_probability_max",
    "precipitation_sum",
)


class OpenMeteoWeatherProvider:
    """Asynchronous Open-Meteo implementation of the weather provider port."""

    def __init__(self, transport: QtNetworkTransport) -> None:
        self._transport = transport

    def fetch(
        self,
        location: Location,
        operation_id: OperationId,
        on_success: Callable[[OperationId, WeatherPayload], None],
        on_failure: Callable[[OperationId, ServiceFailure], None],
    ) -> RequestHandle:
        def response_received(body: bytes) -> None:
            try:
                payload = parse_weather_response(body)
            except InvalidResponseFailure as failure:
                on_failure(operation_id, failure)
            else:
                on_success(operation_id, payload)

        return self._transport.get(
            build_weather_url(location),
            response_received,
            lambda failure: on_failure(operation_id, failure),
        )


def build_weather_url(location: Location) -> str:
    """Build the finalized eight-day Open-Meteo forecast URL."""
    if not isinstance(location, Location):
        raise TypeError("location must be a Location")
    parameters = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "current": ",".join(CURRENT_FIELDS),
        "hourly": ",".join(HOURLY_FIELDS),
        "daily": ",".join(DAILY_FIELDS),
        "timezone": "auto",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "forecast_days": 8,
    }
    return f"{FORECAST_ENDPOINT}?{urlencode(parameters)}"


def map_weather_code(code: int) -> WeatherCondition:
    """Map a WMO weather interpretation code to the internal condition set."""
    if isinstance(code, bool) or not isinstance(code, int):
        raise ValueError("weather code must be an integer")
    if code == 0:
        return WeatherCondition.CLEAR
    if code in (1, 2):
        return WeatherCondition.PARTLY_CLOUDY
    if code == 3:
        return WeatherCondition.CLOUDY
    if code in (45, 48):
        return WeatherCondition.FOG
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return WeatherCondition.RAIN
    if code in (71, 73, 75, 77, 85, 86):
        return WeatherCondition.SNOW
    if code in (95, 96, 99):
        return WeatherCondition.STORM
    return WeatherCondition.UNKNOWN


def parse_weather_response(body: bytes | str) -> WeatherPayload:
    """Convert a complete provider response into a validated staging payload."""
    try:
        document = json.loads(body)
        if not isinstance(document, dict):
            raise TypeError("weather response must be an object")

        time_zone_id = document["timezone"]
        zone = ZoneInfo(time_zone_id)
        current_data = _required_object(document, "current")
        hourly_data = _required_object(document, "hourly")
        daily_data = _required_object(document, "daily")

        current = CurrentWeather(
            temperature_c=current_data["temperature_2m"],
            feels_like_c=current_data["apparent_temperature"],
            condition=map_weather_code(current_data["weather_code"]),
            relative_humidity_percent=current_data["relative_humidity_2m"],
            wind_speed_kmh=current_data["wind_speed_10m"],
            precipitation_probability_percent=current_data[
                "precipitation_probability"
            ],
            precipitation_mm=current_data["precipitation"],
        )
        hourly = _parse_hourly(hourly_data, zone)
        daily = _parse_daily(daily_data)
        return WeatherPayload(time_zone_id, current, hourly, daily)
    except InvalidResponseFailure:
        raise
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidResponseFailure() from error


def _required_object(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document[key]
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be an object")
    return value


def _required_series(section: dict[str, Any], key: str) -> list[Any]:
    value = section[key]
    if not isinstance(value, list):
        raise TypeError(f"{key} must be an array")
    return value


def _parse_hourly(
    section: dict[str, Any],
    zone: ZoneInfo,
) -> tuple[HourlyForecastEntry, ...]:
    times = _required_series(section, "time")
    temperatures = _required_series(section, "temperature_2m")
    codes = _required_series(section, "weather_code")
    probabilities = _required_series(section, "precipitation_probability")
    _require_matching_lengths(times, temperatures, codes, probabilities)

    return tuple(
        HourlyForecastEntry(
            local_time=_parse_local_hour(time, zone),
            temperature_c=temperature,
            condition=map_weather_code(code),
            precipitation_probability_percent=probability,
        )
        for time, temperature, code, probability in zip(
            times, temperatures, codes, probabilities, strict=True
        )
    )


def _parse_daily(section: dict[str, Any]) -> tuple[DailyForecastEntry, ...]:
    dates = _required_series(section, "time")
    minimums = _required_series(section, "temperature_2m_min")
    maximums = _required_series(section, "temperature_2m_max")
    codes = _required_series(section, "weather_code")
    probabilities = _required_series(section, "precipitation_probability_max")
    precipitation = _required_series(section, "precipitation_sum")
    _require_matching_lengths(
        dates, minimums, maximums, codes, probabilities, precipitation
    )

    return tuple(
        DailyForecastEntry(
            local_date=_parse_local_date(local_date),
            minimum_temperature_c=minimum,
            maximum_temperature_c=maximum,
            condition=map_weather_code(code),
            precipitation_probability_percent=probability,
            precipitation_mm=amount,
        )
        for local_date, minimum, maximum, code, probability, amount in zip(
            dates,
            minimums,
            maximums,
            codes,
            probabilities,
            precipitation,
            strict=True,
        )
    )


def _require_matching_lengths(*series: list[Any]) -> None:
    if len({len(values) for values in series}) != 1:
        raise ValueError("weather series must have matching lengths")


def _parse_local_hour(value: Any, zone: ZoneInfo) -> datetime:
    if not isinstance(value, str):
        raise TypeError("forecast time must be a string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        raise ValueError("forecast time must be local provider time")
    return parsed.replace(tzinfo=zone)


def _parse_local_date(value: Any) -> date:
    if not isinstance(value, str):
        raise TypeError("forecast date must be a string")
    return date.fromisoformat(value)
