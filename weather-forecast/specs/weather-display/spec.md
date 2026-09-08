# Feature: Weather Display

## Goal

Display the selected location's current weather and forecast in a clear, minimal, and understandable interface.

## Requirements

### Location Header

* The active location must be displayed prominently.
* The displayed location must include:

  * city
  * country
* Region may be displayed when available, but it is not required in the active location header.

### Current Weather

The interface must display:

* current temperature
* weather condition
* feels-like temperature
* precipitation probability
* relative humidity
* wind speed
* current precipitation amount

### Hourly Forecast

* The interface must provide the hourly forecast for the next 24 forecast hours.
* Each hourly forecast entry must display:

  * local time
  * temperature
  * weather condition
  * precipitation probability
* All 24 hourly entries must remain accessible on normal application window sizes.
* The exact navigation or layout mechanism used to expose all 24 entries is an implementation and UI planning decision.

### Daily Forecast

* The interface must provide a 7-day forecast.
* Each daily entry must display:

  * minimum temperature
  * maximum temperature
  * weather condition
  * precipitation probability
  * precipitation amount

### Units

The interface must display:

* temperature in Celsius
* wind speed in km/h
* precipitation in millimeters
* humidity and precipitation probability as percentages

### Last Updated

* The interface must display the time of the most recent successful weather retrieval and validation.
* `Last updated` represents the time at which the application successfully accepted the complete weather response.
* The displayed timestamp must use the selected location's local time zone.
* The timestamp must only change after a complete and valid weather update has been accepted.
* The exact visual formatting of the timestamp is a UI planning decision.

### Loading and Refresh State

* Existing weather data must remain visible while updated weather data is being fetched.
* The interface must indicate that an update is currently in progress.
* The loading state must not prevent the user from viewing the existing weather data.
* Starting a new weather retrieval clears a previous weather error state.

### Error State

* If a weather update fails, previously valid weather data must remain visible.
* The interface must display an understandable error message indicating that the weather could not be updated.
* The previously successful `Last updated` timestamp must remain unchanged after a failed update.
* Raw technical exceptions or external service details must not be shown to the user.

### No Weather Data

* If no location has been successfully loaded yet, the weather display must not show fabricated or placeholder weather values.
* The interface must clearly indicate that the user must first search for and select a location.
* A failed first retrieval must not cause the failed location to appear as though valid weather has been loaded.

## Acceptance Criteria

* Successfully loading a location results in its city and country being displayed.
* Current temperature, condition, feels-like temperature, precipitation probability, humidity, wind speed, and current precipitation amount are visible.
* The complete next 24 forecast hours are accessible to the user.
* Every hourly entry shows local time, temperature, weather condition, and precipitation probability.
* A complete 7-day forecast is displayed.
* Every daily entry shows min/max temperature, condition, precipitation probability, and precipitation amount.
* Temperatures are displayed in Celsius.
* Wind speed is displayed in km/h.
* Precipitation is displayed in millimeters.
* The time of the last successful retrieval and validation is visible in the selected location's local time.
* During a refresh, existing weather information remains visible and an updating state is shown.
* A successful refresh replaces the displayed weather data and updates the `Last updated` timestamp.
* A failed refresh preserves the existing weather data and timestamp while showing an error state.
* Starting another weather retrieval clears the previous weather error state.
* Before any location has successfully loaded, the interface does not display invented weather information.
