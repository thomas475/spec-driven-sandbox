# Feature: Weather Retrieval

## Goal

Retrieve current and forecast weather data for the location selected by the user and expose it to the rest of the application in a validated internal format.

## Requirements

### Fetch Trigger

* Weather retrieval starts when the user selects a location.
* The selected location must be identified by latitude and longitude.
* Automatic refresh begins only after weather has been successfully retrieved for an active location.

### Current Weather Data

The weather retrieval feature must provide:

* current temperature
* feels-like temperature
* weather condition
* relative humidity
* wind speed
* precipitation probability
* current precipitation amount

### Weather Condition Model

The internal weather condition model must support at least:

* `clear`
* `partly_cloudy`
* `cloudy`
* `fog`
* `rain`
* `snow`
* `storm`
* `unknown`

Provider-specific weather codes must be mapped into this provider-independent condition set.

Unknown or unsupported provider weather codes must map to `unknown`.

Other application layers must not depend directly on provider-specific weather codes.

### Hourly Forecast

* The hourly forecast must contain 24 consecutive forecast entries.
* The first entry must represent the local forecast hour in which the weather retrieval is successfully completed and accepted.
* The application clock is authoritative for determining the current instant.
* Each hourly entry must provide:

  * local time
  * temperature
  * weather condition
  * precipitation probability

### Daily Forecast

* The daily forecast must contain 7 consecutive days.
* Each daily entry must provide:

  * local date
  * minimum temperature
  * maximum temperature
  * weather condition
  * precipitation probability
  * precipitation amount
* Daily forecast values must use provider-supplied daily aggregates.
* The application must not derive required daily aggregate values from hourly forecast data when equivalent provider-supplied daily values are available.
* The seven-day forecast begins with the selected location's local calendar date at the time the weather response is successfully accepted.

### Time Zone

* Forecast timestamps and dates must use the selected location's local time zone.
* The internal weather model must represent the selected location's time zone using an IANA time-zone identifier.
* The selected time zone must be resolvable by Python's `zoneinfo`.
* If the provider returns a time zone that cannot be resolved by `zoneinfo`, the weather response must be treated as invalid.
* A fixed UTC offset alone is not sufficient as the internal time-zone representation.
* Weather data must not be interpreted using the computer's local time zone unless it is the same as the selected location's time zone.

### Units

Weather data must use:

* Celsius for temperature
* km/h for wind speed
* millimeters for precipitation
* percentages from 0 to 100 for humidity and precipitation probability

### Data Validation

* External weather responses must be validated before being accepted.
* Required weather fields must be present and contain valid values.
* Humidity must be between 0 and 100.
* Precipitation probability must be between 0 and 100.
* Wind speed must not be negative.
* Precipitation amount must not be negative.
* Numeric weather values must be finite.
* Partial or malformed responses must not replace previously valid weather data.
* External provider data must be converted into the internal weather domain model before being exposed to other application layers.

### State Handling

* Existing valid weather data must remain available while new weather data is being fetched.
* Existing weather data must only be replaced after the new response has been completely retrieved and validated.
* A successful retrieval replaces the previous weather data atomically.

### Requested and Active Locations

* The application must distinguish between the most recently requested location and the active successfully loaded location.
* When retrieval for a requested location fails, the requested location remains available in application state for error and retry context.
* A failed requested location must not replace the active successfully loaded location.

### Overlapping Weather Requests

* Only the most recently selected location may update the active weather state.
* Weather responses or errors belonging to an older location selection must not replace state belonging to a newer selection.
* Whether obsolete network requests are physically cancelled or merely ignored is an implementation decision.

### Automatic Refresh

* Weather for the active location must be refreshed 15 minutes after the most recent successful weather retrieval.
* A successful refresh schedules the next refresh 15 minutes later.
* A failed refresh must keep the previous valid weather data.
* A failed refresh must not trigger an immediate automatic retry.
* After a failed refresh completes, the next normal refresh attempt occurs 15 minutes after that failed request completes.
* If a refresh for the active location is still in progress when another refresh interval is reached, another concurrent refresh for that same location must not be started.

### Location Changes

* When a new location is selected, automatic refreshes for the previous active location must stop.
* Weather for the previous active location may remain available as fallback display data while the newly selected location is being retrieved.
* Retrieval results for the previous location must not replace weather state after a newer location has been selected.

### Failed Initial Retrieval

* If weather retrieval for a newly selected location fails before any successful retrieval for that location, no automatic refresh schedule is started for that location.
* No immediate automatic retry is performed.
* The user may explicitly retry by selecting the location again.

### Weather Error State

* A failed retrieval must expose an error state to the application layer.
* Starting a new weather retrieval clears the previous weather error state.
* A successful retrieval leaves no active weather retrieval error state.

## Error Cases

* If the weather service cannot be reached, the previous valid weather data must remain available.
* If a request times out, the previous valid weather data must remain available.
* If the external service returns incomplete or invalid data, the response must be rejected.
* If the provider time zone cannot be resolved as an IANA time zone, the response must be rejected.
* A failed weather retrieval must report an error state to the application layer.
* Retrieval failures must not terminate the application.
* Failed requests must not partially update the current weather state.

## Acceptance Criteria

* Selecting a valid location triggers a weather request using its latitude and longitude.
* A successful request produces validated current weather data in the internal domain model.
* Current precipitation amount is available in millimeters.
* Provider-specific weather codes are converted into the internal weather-condition model.
* Unknown provider weather codes are represented as `unknown`.
* A successful request produces 24 consecutive hourly forecast entries beginning with the local forecast hour in which the response is successfully accepted.
* Each hourly entry provides local time, temperature, weather condition, and precipitation probability.
* A successful request produces a 7-day daily forecast.
* Daily forecast values use provider-supplied daily aggregates.
* Each daily entry provides minimum temperature, maximum temperature, weather condition, precipitation probability, and precipitation amount.
* Forecast times and dates represent the selected location's IANA time zone.
* A response with an unusable time zone is rejected.
* Returned temperatures are represented in Celsius.
* Returned wind speeds are represented in km/h.
* Returned precipitation amounts are represented in millimeters.
* Existing weather data remains available while a refresh is in progress.
* New weather data becomes active only after the complete response has been validated.
* A failed requested location remains distinguishable from the active successfully loaded location.
* A failed refresh preserves the previous valid weather data.
* A failed refresh does not cause an immediate retry.
* The next refresh after a failed refresh is scheduled 15 minutes after the failed request completes.
* Older overlapping weather requests cannot overwrite state belonging to a newer location selection.
* Concurrent refreshes for the same active location are not started.
* A failed initial retrieval does not start an automatic refresh schedule.
* Invalid or incomplete responses never replace previously valid weather data.
