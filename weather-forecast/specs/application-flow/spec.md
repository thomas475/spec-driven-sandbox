# Application Flow

## Goal

Define how location search, weather retrieval, and weather display work together as one user flow.

## Initial State

* When the application starts, no location is active.
* No weather data is displayed.
* The location search interface is available immediately.
* The weather display indicates that a location must first be selected.

## Location Search Flow

* The user edits the city search input.
* Editing the input does not itself start a search.
* The user starts a search using Enter or the search button.
* The submitted value is trimmed before the search begins.
* The location search feature retrieves matching locations.
* Existing successful search results remain visible until the new search completes successfully.
* Only the most recently started search may update search state.

### Successful Search

If the search succeeds:

* the result list is replaced with the new valid results
* the user may select one of the returned locations
* any previous search error state is cleared

### No Results

If the search succeeds but contains no valid locations:

* the result area displays a "No results" state

### Failed Search

If the search fails:

* existing successful search results remain unchanged
* an understandable error state is shown
* no weather retrieval is started

## Location Selection Flow

* Selecting a location makes it the currently requested location.
* Selecting a location immediately starts weather retrieval for that location.
* Search results may remain visible.
* Selecting a different result starts retrieval for the newly selected location.
* Only the most recently selected location may become the active displayed location.

## Requested and Active Locations

The application distinguishes between:

* the most recently requested location
* the active successfully loaded location

A requested location does not become the active displayed location until valid weather data for it has been completely retrieved and accepted.

If retrieval for the requested location fails:

* the requested location remains available in state for error and retry context
* the active location remains unchanged
* the previous valid weather display remains active

* requested_location represents the most recent location explicitly selected by the user.
* Automatic weather refreshes must not modify requested_location.

## Weather Retrieval Flow

* Existing valid weather data remains visible while a request for a selected location is in progress.
* New weather data must not become active until it has been completely retrieved and validated.

### Successful Retrieval

When retrieval succeeds for the most recently selected location:

* that location becomes the active location
* the new weather data becomes the active weather data
* the weather display updates atomically to the new location and weather data
* the `Last updated` timestamp is updated
* any previous weather retrieval error state is cleared
* the automatic refresh schedule for that active location begins

### Failed Retrieval

When retrieval fails:

* previously valid active location and weather data remain unchanged
* the most recently requested location remains available for error and retry context
* the previous `Last updated` timestamp remains unchanged
* the weather display shows an understandable error state
* partial or invalid new weather data must not be displayed
* a failed first retrieval does not create a new active location
* no automatic refresh schedule begins for a location that has never successfully loaded

## Changing Location

* The user may perform another location search at any time.
* Selecting a new location immediately stops future automatic refresh scheduling for the previous active location.
* Weather data for the previous active location remains visible while weather for the newly selected location is being retrieved.
* The weather display must switch to the new location and its weather only after the new weather data has been successfully retrieved and validated.
* If retrieval for the new location fails, the previous active location and weather remain displayed.
* Any later completion belonging to an older location selection must not replace state belonging to the newest selection.

## Automatic Refresh

* Weather for the active location is refreshed 15 minutes after the most recent successful weather retrieval.
* During refresh, the currently displayed weather remains visible.
* Only one refresh request for the active location may be in progress at a time.
* A successful refresh replaces the previous weather data and updates the `Last updated` timestamp.
* A successful refresh schedules the next refresh 15 minutes later.
* A failed refresh preserves the previous weather data and timestamp and displays an error state.
* A failed refresh does not trigger an immediate retry.
* After a failed refresh completes, the next normal refresh attempt occurs 15 minutes later.

## Error Lifecycle

* Starting a new non-empty location search clears the previous location-search error state.
* Starting a new weather retrieval clears the previous weather-retrieval error state.
* Successful completion leaves no corresponding active error state.

## State Consistency

At any point, the application must distinguish between:

* current search input
* current search results
* current search loading state
* current search error state
* most recently requested location
* active successfully loaded location
* active weather data
* weather loading state
* weather error state
* time of the last successful weather retrieval

The application must prevent stale results from older asynchronous operations from replacing newer state.

## End-to-End Acceptance Criteria

* The application starts without fabricated weather data.
* Editing the search field does not start a location search.
* The user can search for a city and explicitly select a specific location.
* Selecting a location automatically starts weather retrieval.
* Successful retrieval atomically updates the active location and weather display.
* A failed requested location remains distinguishable from the active location.
* The display is never partially updated with incomplete weather data.
* Searching for another location does not immediately destroy previously valid weather information.
* Selecting a new location does not replace the active weather display until valid weather for the new location is available.
* A failed search does not trigger weather retrieval.
* A failed location change preserves the previously active location and weather.
* Older overlapping searches cannot overwrite newer search state.
* Older overlapping weather requests cannot overwrite state belonging to a newer location selection.
* Automatic refreshes preserve existing weather data until valid replacement data is available.
* Failed refreshes do not immediately retry.
* The next refresh after a failed refresh occurs 15 minutes after the failed request completes.
* No concurrent refreshes occur for the same active location.
* The user interface remains responsive throughout searching, retrieval, location changes, and automatic refresh operations.
