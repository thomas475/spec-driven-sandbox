"""Provider-independent weather values and validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from weather_forecast.domain.location import Location


class WeatherCondition(Enum):
    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    FOG = "fog"
    RAIN = "rain"
    SNOW = "snow"
    STORM = "storm"
    UNKNOWN = "unknown"


def _validate_number(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


def _validate_percentage(name: str, value: float) -> None:
    _validate_number(name, value)
    if not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100")


def _validate_non_negative(name: str, value: float) -> None:
    _validate_number(name, value)
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_condition(condition: WeatherCondition) -> None:
    if not isinstance(condition, WeatherCondition):
        raise TypeError("condition must be a WeatherCondition")


def _resolve_time_zone(time_zone_id: str) -> ZoneInfo:
    if not isinstance(time_zone_id, str):
        raise TypeError("time_zone_id must be a string")
    if not time_zone_id:
        raise ValueError("time_zone_id must not be empty")
    try:
        return ZoneInfo(time_zone_id)
    except ZoneInfoNotFoundError as error:
        raise ValueError("time_zone_id must identify a resolvable IANA time zone") from error


def _time_zone_key(value: datetime) -> str | None:
    return value.tzinfo.key if isinstance(value.tzinfo, ZoneInfo) else None


@dataclass(frozen=True, slots=True)
class CurrentWeather:
    temperature_c: float
    feels_like_c: float
    condition: WeatherCondition
    relative_humidity_percent: float
    wind_speed_kmh: float
    precipitation_probability_percent: float
    precipitation_mm: float

    def __post_init__(self) -> None:
        _validate_number("temperature_c", self.temperature_c)
        _validate_number("feels_like_c", self.feels_like_c)
        _validate_condition(self.condition)
        _validate_percentage("relative_humidity_percent", self.relative_humidity_percent)
        _validate_non_negative("wind_speed_kmh", self.wind_speed_kmh)
        _validate_percentage(
            "precipitation_probability_percent",
            self.precipitation_probability_percent,
        )
        _validate_non_negative("precipitation_mm", self.precipitation_mm)


@dataclass(frozen=True, slots=True)
class HourlyForecastEntry:
    local_time: datetime
    temperature_c: float
    condition: WeatherCondition
    precipitation_probability_percent: float

    def __post_init__(self) -> None:
        if not isinstance(self.local_time, datetime):
            raise TypeError("local_time must be a datetime")
        if _time_zone_key(self.local_time) is None:
            raise ValueError("local_time must use an IANA time zone")
        if any(
            (
                self.local_time.minute,
                self.local_time.second,
                self.local_time.microsecond,
            )
        ):
            raise ValueError("local_time must represent a forecast-hour boundary")
        _validate_number("temperature_c", self.temperature_c)
        _validate_condition(self.condition)
        _validate_percentage(
            "precipitation_probability_percent",
            self.precipitation_probability_percent,
        )


@dataclass(frozen=True, slots=True)
class DailyForecastEntry:
    local_date: date
    minimum_temperature_c: float
    maximum_temperature_c: float
    condition: WeatherCondition
    precipitation_probability_percent: float
    precipitation_mm: float

    def __post_init__(self) -> None:
        if not isinstance(self.local_date, date) or isinstance(self.local_date, datetime):
            raise TypeError("local_date must be a date")
        _validate_number("minimum_temperature_c", self.minimum_temperature_c)
        _validate_number("maximum_temperature_c", self.maximum_temperature_c)
        _validate_condition(self.condition)
        _validate_percentage(
            "precipitation_probability_percent",
            self.precipitation_probability_percent,
        )
        _validate_non_negative("precipitation_mm", self.precipitation_mm)


def _validate_hourly_entries(
    hourly: tuple[HourlyForecastEntry, ...],
    time_zone_id: str,
    minimum_length: int,
) -> None:
    if not isinstance(hourly, tuple):
        raise TypeError("hourly must be a tuple")
    if len(hourly) < minimum_length:
        raise ValueError(f"hourly must contain at least {minimum_length} entries")
    for entry in hourly:
        if not isinstance(entry, HourlyForecastEntry):
            raise TypeError("hourly must contain HourlyForecastEntry values")
        if _time_zone_key(entry.local_time) != time_zone_id:
            raise ValueError("hourly entries must use the report IANA time zone")
    for previous, current in zip(hourly, hourly[1:]):
        if current.local_time.astimezone(UTC) - previous.local_time.astimezone(UTC) != timedelta(hours=1):
            raise ValueError("hourly entries must be consecutive")


def _validate_daily_entries(
    daily: tuple[DailyForecastEntry, ...], minimum_length: int
) -> None:
    if not isinstance(daily, tuple):
        raise TypeError("daily must be a tuple")
    if len(daily) < minimum_length:
        raise ValueError(f"daily must contain at least {minimum_length} entries")
    for entry in daily:
        if not isinstance(entry, DailyForecastEntry):
            raise TypeError("daily must contain DailyForecastEntry values")
    for previous, current in zip(daily, daily[1:]):
        if current.local_date - previous.local_date != timedelta(days=1):
            raise ValueError("daily entries must be consecutive")


@dataclass(frozen=True, slots=True)
class WeatherPayload:
    time_zone_id: str
    current: CurrentWeather
    hourly: tuple[HourlyForecastEntry, ...]
    daily: tuple[DailyForecastEntry, ...]

    def __post_init__(self) -> None:
        _resolve_time_zone(self.time_zone_id)
        if not isinstance(self.current, CurrentWeather):
            raise TypeError("current must be CurrentWeather")
        _validate_hourly_entries(self.hourly, self.time_zone_id, minimum_length=24)
        _validate_daily_entries(self.daily, minimum_length=7)


@dataclass(frozen=True, slots=True)
class WeatherReport:
    time_zone_id: str
    current: CurrentWeather
    hourly: tuple[HourlyForecastEntry, ...]
    daily: tuple[DailyForecastEntry, ...]

    def __post_init__(self) -> None:
        _resolve_time_zone(self.time_zone_id)
        if not isinstance(self.current, CurrentWeather):
            raise TypeError("current must be CurrentWeather")
        if len(self.hourly) != 24:
            raise ValueError("hourly must contain exactly 24 entries")
        if len(self.daily) != 7:
            raise ValueError("daily must contain exactly 7 entries")
        _validate_hourly_entries(self.hourly, self.time_zone_id, minimum_length=24)
        _validate_daily_entries(self.daily, minimum_length=7)


@dataclass(frozen=True, slots=True)
class LoadedWeather:
    location: Location
    report: WeatherReport
    last_updated: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location):
            raise TypeError("location must be a Location")
        if not isinstance(self.report, WeatherReport):
            raise TypeError("report must be a WeatherReport")
        if not isinstance(self.last_updated, datetime):
            raise TypeError("last_updated must be a datetime")
        if _time_zone_key(self.last_updated) != self.report.time_zone_id:
            raise ValueError("last_updated must use the report IANA time zone")

        acceptance_hour = self.last_updated.replace(minute=0, second=0, microsecond=0)
        if self.report.hourly[0].local_time != acceptance_hour:
            raise ValueError("hourly forecast must begin with the acceptance hour")
        if self.report.daily[0].local_date != self.last_updated.date():
            raise ValueError("daily forecast must begin with the acceptance local date")

