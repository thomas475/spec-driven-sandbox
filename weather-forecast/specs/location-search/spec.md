# Feature: Location Search

## Goal

Allow the user to search for a city, inspect matching locations, and explicitly select the intended location.

The selected location is then passed to the weather retrieval feature.

## Requirements

### Search Input

* The user can enter a city name into a search field.
* The current search input state updates as the user types.
* Leading and trailing whitespace must be removed when the search is submitted.
* If the resulting submitted search input is empty, no search is started and the current search results and error state remain unchanged.
* Trimming affects only the submitted search query.
* The visible search field retains the text exactly as entered by the user unless the user edits it.

### Search Trigger

* A search can be started by pressing Enter while the search field is active.
* A search can also be started through a search button.
* Both triggers must produce the same behavior.

### Search Results

* Search results must be displayed below the search field.
* Each valid result must display:

  * city
  * country
  * region, when available
* Locations with the same city name must be displayed as separate results.
* Duplicate city names must not be automatically resolved.
* Even when exactly one result is returned, the user must explicitly select it.
* City and country are required for a result to be considered valid.
* Region is optional.

### Malformed Results

* Individual malformed or incomplete results must be discarded.
* Valid results from the same response may still be displayed.
* A malformed individual result must not invalidate the entire response if other valid results are available.

### No Results

* If a search completes successfully but contains no valid matching locations, the application must display a "No results" state.

### Location Selection

* The user can select a location from the search results.
* Selecting a location starts weather retrieval for that location.
* The complete internal location object, including latitude and longitude, must be passed to the weather retrieval feature.

### Search State

* The most recent successfully retrieved result list remains visible until another search completes successfully.
* Starting a new search must not immediately remove the previous results.
* A failed search must not replace or clear the previous successful results.
* A successful search replaces the previous result list, including when the new result list is empty.

### Overlapping Searches

* Only the most recently started search may update the visible search state.
* Results or errors from an older search that complete after a newer search has started must not replace the state belonging to the newer search.
* Whether older network requests are physically cancelled or merely ignored is an implementation decision.

### Search Error State

* If a search fails, an understandable error state must be exposed to the user interface.
* Starting a new non-empty search clears the previous search error state.
* A successful search leaves no active search error state.

## Error Cases

* If the location service cannot be reached, the application must communicate that no connection to the service could be established.
* A failed request must not terminate the application.
* A failed request must not modify the previous successful search results.
* Invalid or incomplete location entries must not be presented as selectable locations.

## Acceptance Criteria

* Entering `Berlin` and starting a search retrieves matching locations.
* Entering `  Berlin  ` behaves the same as entering `Berlin`.
* Entering only whitespace does not start a search.
* Editing the search field updates the current search input state without starting a search.
* Pressing Enter and clicking the search button perform equivalent searches.
* Search results appear below the search field.
* Every valid displayed result contains city and country information.
* Region is displayed when available.
* Multiple locations with the same city name remain individually selectable.
* A single returned location is not selected automatically.
* Invalid individual results are discarded without discarding valid results from the same response.
* A successful search with no valid results displays a "No results" state.
* Selecting a location triggers weather retrieval for that exact location.
* Existing results remain visible while another search is in progress.
* Existing results remain visible if the new search fails.
* Existing results are replaced only after the new search completes successfully.
* Older overlapping searches cannot overwrite the state of a newer search.
* Starting a new non-empty search clears the previous search error state.
* Connection failures are communicated to the user without terminating the application.
