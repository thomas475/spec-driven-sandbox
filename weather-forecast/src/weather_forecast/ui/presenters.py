"""Pure conversion from application snapshots to immutable UI render models."""

from __future__ import annotations

from dataclasses import dataclass

from weather_forecast.application.state import ApplicationState, SearchResultState
from weather_forecast.domain.failures import UserFacingError
from weather_forecast.domain.location import Location
from weather_forecast.domain.weather import LoadedWeather, WeatherCondition


SELECT_LOCATION_MESSAGE = "Search for and select a location to view weather."
SEARCHING_MESSAGE = "Searching…"
UPDATING_MESSAGE = "Updating weather…"
NO_RESULTS_MESSAGE = "No results"

_ERROR_MESSAGES = {
    UserFacingError.LOCATION_CONNECTION: (
        "Unable to connect to the location service. Please try again."
    ),
    UserFacingError.LOCATION_SEARCH_FAILED: (
        "Unable to search for locations. Please try again."
    ),
    UserFacingError.WEATHER_UPDATE_FAILED: (
        "Weather could not be updated. Please try again."
    ),
}

_CONDITION_LABELS = {
    WeatherCondition.CLEAR: "Clear",
    WeatherCondition.PARTLY_CLOUDY: "Partly cloudy",
    WeatherCondition.CLOUDY: "Cloudy",
    WeatherCondition.FOG: "Fog",
    WeatherCondition.RAIN: "Rain",
    WeatherCondition.SNOW: "Snow",
    WeatherCondition.STORM: "Storm",
    WeatherCondition.UNKNOWN: "Unknown",
}


@dataclass(frozen=True, slots=True)
class LocationResultRenderModel:
    location: Location
    city: str
    country: str
    region: str | None
    display_text: str


@dataclass(frozen=True, slots=True)
class LocationSearchRenderModel:
    input_text: str
    results: tuple[LocationResultRenderModel, ...]
    loading: bool
    loading_message: str | None
    empty_message: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class CurrentWeatherRenderModel:
    temperature: str
    condition: str
    feels_like: str
    precipitation_probability: str
    relative_humidity: str
    wind_speed: str
    precipitation: str


@dataclass(frozen=True, slots=True)
class HourlyForecastRenderModel:
    local_time: str
    temperature: str
    condition: str
    precipitation_probability: str


@dataclass(frozen=True, slots=True)
class DailyForecastRenderModel:
    local_date: str
    minimum_temperature: str
    maximum_temperature: str
    condition: str
    precipitation_probability: str
    precipitation: str


@dataclass(frozen=True, slots=True)
class WeatherContentRenderModel:
    location_header: str
    current: CurrentWeatherRenderModel
    hourly: tuple[HourlyForecastRenderModel, ...]
    daily: tuple[DailyForecastRenderModel, ...]
    last_updated: str


@dataclass(frozen=True, slots=True)
class WeatherDisplayRenderModel:
    instruction: str | None
    content: WeatherContentRenderModel | None
    loading: bool
    loading_message: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class ApplicationRenderModel:
    search: LocationSearchRenderModel
    weather: WeatherDisplayRenderModel


def present_application(state: ApplicationState) -> ApplicationRenderModel:
    """Produce the complete deterministic representation for one snapshot."""
    return ApplicationRenderModel(
        search=present_location_search(state),
        weather=present_weather_display(state),
    )


def present_location_search(state: ApplicationState) -> LocationSearchRenderModel:
    results = tuple(_present_location(location) for location in state.search_results)
    empty_message = (
        NO_RESULTS_MESSAGE
        if state.search_result_state is SearchResultState.NO_RESULTS
        else None
    )
    return LocationSearchRenderModel(
        input_text=state.search_input,
        results=results,
        loading=state.search_loading,
        loading_message=SEARCHING_MESSAGE if state.search_loading else None,
        empty_message=empty_message,
        error_message=_message_for(state.search_error),
    )


def present_weather_display(state: ApplicationState) -> WeatherDisplayRenderModel:
    content = (
        _present_loaded_weather(state.loaded_weather)
        if state.loaded_weather is not None
        else None
    )
    loading = state.weather_loading is not None
    return WeatherDisplayRenderModel(
        instruction=SELECT_LOCATION_MESSAGE if content is None else None,
        content=content,
        loading=loading,
        loading_message=UPDATING_MESSAGE if loading else None,
        error_message=_message_for(state.weather_error),
    )


def condition_label(condition: WeatherCondition) -> str:
    """Return the safe user-facing label for an internal condition."""
    if not isinstance(condition, WeatherCondition):
        raise TypeError("condition must be a WeatherCondition")
    return _CONDITION_LABELS[condition]


def _present_location(location: Location) -> LocationResultRenderModel:
    parts = [location.city]
    if location.region:
        parts.append(location.region)
    parts.append(location.country)
    return LocationResultRenderModel(
        location=location,
        city=location.city,
        country=location.country,
        region=location.region,
        display_text=", ".join(parts),
    )


def _present_loaded_weather(loaded: LoadedWeather) -> WeatherContentRenderModel:
    report = loaded.report
    current = report.current
    current_model = CurrentWeatherRenderModel(
        temperature=_temperature(current.temperature_c),
        condition=condition_label(current.condition),
        feels_like=_temperature(current.feels_like_c),
        precipitation_probability=_percentage(
            current.precipitation_probability_percent
        ),
        relative_humidity=_percentage(current.relative_humidity_percent),
        wind_speed=_wind_speed(current.wind_speed_kmh),
        precipitation=_precipitation(current.precipitation_mm),
    )
    hourly = tuple(
        HourlyForecastRenderModel(
            local_time=entry.local_time.strftime("%H:%M"),
            temperature=_temperature(entry.temperature_c),
            condition=condition_label(entry.condition),
            precipitation_probability=_percentage(
                entry.precipitation_probability_percent
            ),
        )
        for entry in report.hourly
    )
    daily = tuple(
        DailyForecastRenderModel(
            local_date=entry.local_date.isoformat(),
            minimum_temperature=_temperature(entry.minimum_temperature_c),
            maximum_temperature=_temperature(entry.maximum_temperature_c),
            condition=condition_label(entry.condition),
            precipitation_probability=_percentage(
                entry.precipitation_probability_percent
            ),
            precipitation=_precipitation(entry.precipitation_mm),
        )
        for entry in report.daily
    )
    return WeatherContentRenderModel(
        location_header=f"{loaded.location.city}, {loaded.location.country}",
        current=current_model,
        hourly=hourly,
        daily=daily,
        last_updated=(
            f"Last updated: {loaded.last_updated:%Y-%m-%d %H:%M} "
            f"{report.time_zone_id}"
        ),
    )


def _message_for(error: UserFacingError | None) -> str | None:
    return _ERROR_MESSAGES.get(error) if error is not None else None


def _number(value: float) -> str:
    return format(value, "g")


def _temperature(value: float) -> str:
    return f"{_number(value)} °C"


def _percentage(value: float) -> str:
    return f"{_number(value)}%"


def _wind_speed(value: float) -> str:
    return f"{_number(value)} km/h"


def _precipitation(value: float) -> str:
    return f"{_number(value)} mm"
