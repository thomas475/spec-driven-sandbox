"""Immutable application state published to presentation listeners."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from weather_forecast.domain.failures import UserFacingError
from weather_forecast.domain.location import Location
from weather_forecast.domain.weather import LoadedWeather


class SearchResultState(Enum):
    INITIAL = "initial"
    RESULTS = "results"
    NO_RESULTS = "no_results"


class WeatherLoading(Enum):
    LOCATION_LOAD = "location_load"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class ApplicationState:
    search_input: str = ""
    search_results: tuple[Location, ...] = ()
    search_result_state: SearchResultState = SearchResultState.INITIAL
    search_loading: bool = False
    search_error: UserFacingError | None = None
    requested_location: Location | None = None
    loaded_weather: LoadedWeather | None = None
    weather_loading: WeatherLoading | None = None
    weather_error: UserFacingError | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.search_input, str):
            raise TypeError("search_input must be a string")
        if not isinstance(self.search_results, tuple):
            raise TypeError("search_results must be a tuple")
        if not all(isinstance(location, Location) for location in self.search_results):
            raise TypeError("search_results must contain Location values")
        if not isinstance(self.search_result_state, SearchResultState):
            raise TypeError("search_result_state must be a SearchResultState")
        if self.search_result_state is SearchResultState.RESULTS and not self.search_results:
            raise ValueError("RESULTS state requires at least one search result")
        if (
            self.search_result_state
            in (SearchResultState.INITIAL, SearchResultState.NO_RESULTS)
            and self.search_results
        ):
            raise ValueError("INITIAL and NO_RESULTS states require empty results")
        if not isinstance(self.search_loading, bool):
            raise TypeError("search_loading must be a bool")
        if self.search_error is not None and not isinstance(
            self.search_error, UserFacingError
        ):
            raise TypeError("search_error must be a UserFacingError or None")
        if self.requested_location is not None and not isinstance(
            self.requested_location, Location
        ):
            raise TypeError("requested_location must be a Location or None")
        if self.loaded_weather is not None and not isinstance(
            self.loaded_weather, LoadedWeather
        ):
            raise TypeError("loaded_weather must be LoadedWeather or None")
        if self.weather_loading is not None and not isinstance(
            self.weather_loading, WeatherLoading
        ):
            raise TypeError("weather_loading must be WeatherLoading or None")
        if self.weather_error is not None and not isinstance(
            self.weather_error, UserFacingError
        ):
            raise TypeError("weather_error must be a UserFacingError or None")

