# Weather Forecast Application Implementation Plan

## 1. Scope and constraints

This plan is derived exclusively from:

- `.spec-driven/constitution.md`
- `specs/application-flow/spec.md`
- `specs/location-search/spec.md`
- `specs/weather-display/spec.md`
- `specs/weather-retrieval/spec.md`

The application will use Python 3.13 or newer, PySide6, and Open-Meteo. The UI will not call external services. External data will be converted to provider-independent internal models and validated before it can become active. Application behavior will be testable without widgets or live services. There will be no global mutable state and no speculative infrastructure. Remaining ambiguities are listed in section 13 rather than silently resolved.

## 2. Package and module structure

```text
weather-forecast/
├── pyproject.toml
├── src/
│   └── weather_forecast/
│       ├── __init__.py
│       ├── __main__.py
│       ├── bootstrap.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── location.py
│       │   ├── weather.py
│       │   └── failures.py
│       ├── application/
│       │   ├── __init__.py
│       │   ├── ports.py
│       │   ├── state.py
│       │   └── controller.py
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── qt_network.py
│       │   ├── qt_scheduler.py
│       │   ├── open_meteo_location.py
│       │   └── open_meteo_weather.py
│       └── ui/
│           ├── __init__.py
│           ├── main_window.py
│           ├── location_search.py
│           ├── weather_display.py
│           └── presenters.py
└── tests/
    ├── unit/
    │   ├── domain/
    │   ├── application/
    │   └── infrastructure/
    ├── integration/
    ├── ui/
    └── external/
```

- `domain` contains immutable internal data and validation and has no PySide6/provider imports.
- `application` owns state and workflows and depends only on domain types and ports.
- `infrastructure` implements Qt transport/timing and Open-Meteo conversion.
- `ui` renders immutable state and forwards user actions; it owns no authoritative workflow state.
- `bootstrap.py` is the only composition root and creates all mutable service instances.
- `__main__.py` only launches the composed application.

PySide6 is the only planned runtime dependency. Use standard-library dataclasses, enums, protocols, JSON, `datetime`, `zoneinfo`, and `unittest`. Any further dependency must be justified before addition.

## 3. Domain models

Use frozen dataclasses (or equivalent immutable value objects).

### Location

`Location`:

- `latitude: float`
- `longitude: float`
- `city: str`
- `country: str`
- `region: str | None`

Latitude/longitude form identity; names are metadata. Coordinates must be finite and geographically valid. City/country must be non-empty; region is optional. Same-name locations remain separate.

### Weather conditions

`WeatherCondition` enum:

- `CLEAR`
- `PARTLY_CLOUDY`
- `CLOUDY`
- `FOG`
- `RAIN`
- `SNOW`
- `STORM`
- `UNKNOWN`

No Open-Meteo code may escape infrastructure. The Open-Meteo adapter will use this explicit WMO-code mapping:

- `0` → `CLEAR`
- `1`, `2` → `PARTLY_CLOUDY`
- `3` → `CLOUDY`
- `45`, `48` → `FOG`
- `51`, `53`, `55`, `56`, `57`, `61`, `63`, `65`, `66`, `67`, `80`, `81`, `82` → `RAIN`
- `71`, `73`, `75`, `77`, `85`, `86` → `SNOW`
- `95`, `96`, `99` → `STORM`
- every other value → `UNKNOWN`

This provider-adapter policy keeps the domain categories fixed and treats freezing rain/drizzle as rain and thunderstorm variants as storm.

### Weather values

`CurrentWeather`:

- `temperature_c: float`
- `feels_like_c: float`
- `condition: WeatherCondition`
- `relative_humidity_percent: float`
- `wind_speed_kmh: float`
- `precipitation_probability_percent: float`
- `precipitation_mm: float`

`HourlyForecastEntry`:

- `local_time: datetime` (aware, in the selected location's IANA zone)
- `temperature_c: float`
- `condition: WeatherCondition`
- `precipitation_probability_percent: float`

`DailyForecastEntry`:

- `local_date: date`
- `minimum_temperature_c: float`
- `maximum_temperature_c: float`
- `condition: WeatherCondition`
- `precipitation_probability_percent: float`
- `precipitation_mm: float`

### Staged and accepted weather

`WeatherPayload` is a provider-independent, validated staging model returned by the provider adapter:

- `time_zone_id: str` (IANA identifier resolvable by `zoneinfo.ZoneInfo`)
- `current: CurrentWeather`
- `hourly: tuple[HourlyForecastEntry, ...]` containing the provider's eight-day hourly window, from which the specified acceptance-time window is selected
- `daily: tuple[DailyForecastEntry, ...]` containing provider-supplied aggregates

`WeatherReport` is the accepted display model:

- `time_zone_id: str`
- `current: CurrentWeather`
- `hourly: tuple[HourlyForecastEntry, ...]` of exactly 24 consecutive entries, beginning with the selected location's local forecast hour containing the acceptance instant
- `daily: tuple[DailyForecastEntry, ...]` of exactly seven consecutive local dates, beginning with the selected location's local calendar date at acceptance

`LoadedWeather` is committed atomically:

- `location: Location`
- `report: WeatherReport`
- `last_updated: datetime`, the exact application acceptance instant converted to `report.time_zone_id`

The staging model lets infrastructure convert all provider data before exposure while allowing the application—using its injected authoritative clock—to select and validate the exact 24-hour window at acceptance. No staged/partial data is displayed.

Validation requires required fields/types, finite numeric values, percentages in `[0, 100]`, non-negative wind/precipitation, a resolvable IANA zone, chronological/consecutive periods, matching local time zone, sufficient hourly coverage, exactly 24 accepted hours, and exactly seven consecutive daily aggregates. Unsupported provider weather codes map to `UNKNOWN` rather than invalidating an otherwise valid response.

## 4. Layer interfaces

Declare standard-library protocols in `application/ports.py`:

```python
class LocationProvider(Protocol):
    def search(
        self,
        query: str,
        operation_id: OperationId,
        on_success: Callable[[OperationId, tuple[Location, ...]], None],
        on_failure: Callable[[OperationId, ServiceFailure], None],
    ) -> RequestHandle: ...

class WeatherProvider(Protocol):
    def fetch(
        self,
        location: Location,
        operation_id: OperationId,
        on_success: Callable[[OperationId, WeatherPayload], None],
        on_failure: Callable[[OperationId, ServiceFailure], None],
    ) -> RequestHandle: ...

class RefreshScheduler(Protocol):
    def schedule_once(
        self, delay: timedelta, callback: Callable[[], None]
    ) -> TimerHandle: ...
    def cancel(self, handle: TimerHandle) -> None: ...

class Clock(Protocol):
    def now(self) -> datetime: ...

class StateListener(Protocol):
    def __call__(self, state: ApplicationState) -> None: ...
```

`RequestHandle` exposes best-effort cancellation without leaking Qt. Operation IDs, not cancellation, guarantee stale-response safety.

UI-to-application calls are:

- `update_search_input(text)` on every edit; this changes input state only.
- `submit_search()` from both Enter and the button; the controller reads and trims current input.
- `select_location(location)` on explicit result selection.
- an internal refresh action invoked by the scheduler.

The controller emits immutable `ApplicationState` snapshots. Presenters turn snapshots into view strings/models. Widgets render and emit intent only.

## 5. Non-blocking PySide6 networking

Create one application-scoped `QNetworkAccessManager` on the GUI thread in `bootstrap.py`. Adapters issue asynchronous `get()` calls and consume `QNetworkReply` signals. Never perform synchronous network calls, blocking waits, nested `processEvents()` loops, or network work in widgets.

Each request has a single-shot 30-second `QTimer`:

1. Start the reply and timer.
2. On timeout, abort and report exactly one `TimeoutFailure`.
3. On completion, stop the timer, classify network/HTTP status, read the complete body, parse JSON, validate/convert it, and invoke one callback.
4. Dispose reply/timer safely after completion.

Parsing is bounded to the requested forecast response and can run in the completion handler. A worker thread is not added without measured evidence that parsing harms responsiveness.

When a newer search or explicit location operation begins, the controller will abort the obsolete request to avoid unnecessary work. Every callback is still matched against the controller's current operation ID because cancellation can race with completion. Late successes and failures are ignored with no state effect.

On application shutdown, the composition root marks the controller closed, cancels the refresh timer, aborts all tracked replies, disconnects state listeners, and then allows Qt objects to be destroyed. Completion handlers check the closed flag/operation identity, so no callback can mutate state or access disposed UI.

## 6. State ownership

One `ApplicationController` owns all mutable application state. No global mutable state exists. Providers own only transient request objects; the scheduler owns timer objects; UI controls own presentation state only.

`ApplicationState` contains:

- `search_input: str`, updated on every edit
- `search_results: tuple[Location, ...]`
- `search_result_state: Initial | Results | NoResults`
- `search_loading: bool`
- `search_error: UserFacingError | None`
- `requested_location: Location | None`, retained after failure for error/retry context
- `loaded_weather: LoadedWeather | None`; its location is the active location
- `weather_loading: None | LocationLoad | Refresh`
- `weather_error: UserFacingError | None`

Private controller state holds current search/weather operation IDs and request handles plus the refresh timer handle. `requested_location` changes only on explicit user selection; automatic refresh does not modify it. Requested and active locations are never conflated. Search and weather loading/errors remain independent.

## 7. State transitions

### Startup and editing

- Start with empty input, no results/location/weather, idle loading, and no errors.
- Make search available immediately and show the select-a-location instruction without placeholder weather.
- Each edit updates only `search_input`; it starts no request and changes no results/error.

### Search submission

- Trim current input only to produce the submitted query. Preserve `search_input` and the visible text exactly as typed unless the user edits it.
- If empty after trimming: perform no request and preserve results and search error.
- Otherwise: create a new search operation ID, clear search error, set loading, retain prior successful results/result state, and call `LocationProvider.search`.
- A matching success replaces results atomically, clears error, and ends loading. Zero valid results produces `NoResults`.
- A matching failure preserves results/result state, ends loading, exposes an understandable error, and starts no weather retrieval.
- Ignore every non-current search callback.

The location adapter discards malformed individual entries, keeps valid siblings, and returns a successful empty tuple if none are valid. No result is auto-selected, even when exactly one exists.

### Selection and initial/location-change retrieval

- Explicit selection sets `requested_location`, immediately cancels future refresh scheduling for the prior active location, creates a new weather operation ID, clears weather error, sets `LocationLoad`, and calls `WeatherProvider.fetch` with the full location.
- Preserve `loaded_weather` throughout retrieval.
- Ignore every callback from an older selection.

For a matching successful payload:

1. Read one authoritative acceptance instant from `Clock`.
2. Resolve `payload.time_zone_id`, convert the instant into that local zone, and identify its containing local forecast hour.
3. Select exactly 24 consecutive hourly entries beginning at that hour and exactly seven provider-supplied daily aggregates beginning with that local calendar date.
4. Validate the complete `WeatherReport`.
5. Atomically commit `LoadedWeather(requested_location, report, local_acceptance_instant)`.
6. End loading, clear weather error, and schedule one refresh for 15 minutes later.

If payload-to-report acceptance fails, handle it as `InvalidResponseFailure` rather than committing partial data.

For a matching failure: retain `requested_location`, preserve the entire prior `loaded_weather` and timestamp, end loading, expose a weather error, and schedule no refresh for the failed requested location. Explicit reselection retries it.

### Refresh

- The one-shot timer fires 15 minutes after the most recent success.
- If a refresh is already active, do not start another.
- Otherwise clear weather error, set `Refresh`, and fetch `loaded_weather.location` while retaining visible data.
- On success, use the same clock-based acceptance/window process, atomically replace the active aggregate, and schedule another one-shot timer 15 minutes after success.
- On failure, preserve the active aggregate/timestamp, expose an error, and schedule the next one-shot attempt 15 minutes after failure completion. Do not retry immediately.
- Selecting a location cancels the old active-location schedule and invalidates any old refresh callback.
- Refresh actions never modify `requested_location`; it continues to represent the most recent explicit user selection.

One-shot timers directly express the success/failure scheduling anchors and prevent concurrent refresh creation.

## 8. External provider abstractions

`OpenMeteoLocationProvider` alone knows the geocoding endpoint, parameters, and response keys. It validates coordinates/city/country, treats region as optional, converts valid entries to `Location`, and discards malformed entries individually.

`OpenMeteoWeatherProvider` alone knows the forecast endpoint, parameters, response schema, units, and code mapping. It requests the selected coordinates with `timezone=auto`, all specified current/hourly/daily variables, Celsius, km/h, millimeters, and `forecast_days=8`. Eight local forecast days are a small bounded overfetch that guarantees at least 24 entries beginning at the acceptance hour even when a request crosses an hour/day boundary within its 30-second lifetime; the application exposes only the required 24 hours and seven days. If the returned data still cannot cover the acceptance-time window, the response is invalid. It returns only `WeatherPayload` or a typed failure.

`qt_network.py` contains only genuinely shared transport mechanics: async GET, timeout, cancellation, HTTP/network classification, exactly-once completion, and cleanup. Provider parsing stays in its adapter.

`QtRefreshScheduler` implements one-shot scheduling with `QTimer`. Other providers can replace either adapter in `bootstrap.py` without changes to domain, controller, or UI.

## 9. Error propagation

Infrastructure-to-application failures:

- `ConnectionFailure`: service cannot be reached
- `TimeoutFailure`: 30-second deadline elapsed
- `HttpFailure`: unsuccessful HTTP response
- `InvalidResponseFailure`: malformed JSON/schema, invalid values, unusable IANA zone, inconsistent series, or inadequate required data

Adapters translate Qt/HTTP/JSON details and complete a live operation once. Obsolete cancellations/callbacks are ignored by operation ID and create no user-visible error. Expected failures must not escape Qt callbacks or terminate the application.

The application applies preservation rules and exposes semantic `UserFacingError` values. Presenters map them to understandable search/weather messages without URLs, payloads, status internals, raw exceptions, or stack traces. A candidate rejected during acceptance is propagated through the same weather-failure transition.

Malformed location entries are handled inside their adapter as specified; a malformed weather response is rejected as a whole. Search and weather errors are independent and clear only on the specified non-empty search/weather start and success transitions.

Use Python's standard `logging` module for non-persistent development diagnostics only. Log failure category and exception context to standard error at `DEBUG` level; do not log response bodies, user search text, coordinates, telemetry, or provider payloads. The default application configuration installs no file handler and uses `WARNING`, keeping normal expected failures out of persistent storage while preserving a simple opt-in diagnostic path.

## 10. UI plan

`MainWindow` composes:

- `LocationSearchView`: text field, search button, loading indicator, error/no-results state, and results below the field. Results show city/country and region when present and retain the complete `Location` for explicit selection.
- `WeatherDisplayView`: initial instruction or atomic loaded content containing active city/country, current weather, 24-hour forecast, seven-day forecast, local last-updated time, and non-destructive loading/error indicators.

Omit region from the active header because it is optional there and the constitution calls for a minimal UI. Use a horizontally scrollable hourly list so all 24 entries remain accessible without enlarging the window; each item shows local time, Celsius temperature, condition, and precipitation percentage. Daily items show date, min/max Celsius, condition, precipitation percentage, and millimeters. Current weather shows every required value and unit. Set a minimum supported content size of 800×600 logical pixels; at that size, the main weather area scrolls vertically and the hourly row scrolls horizontally, so no required entry is unreachable.

Render `Last updated` from the stored aware acceptance instant in the active location's IANA zone as `Last updated: YYYY-MM-DD HH:MM <IANA zone>` using a 24-hour clock and no seconds. Loading indicators never clear or obstruct existing data. A failed first load keeps the no-weather instruction visible and does not present the requested location as active.

## 11. Testing strategy

Use deterministic fake providers, clock, scheduler, handles, and state listeners. Normal tests never call a live service.

### Domain tests

- Coordinate identity/ranges; required city/country; optional region.
- All numeric validation, percentage bounds, and non-negative fields.
- IANA-zone resolution and aware local times.
- Chronological/consecutive hourly/daily periods, exact accepted 24/7 sizes, and insufficient coverage rejection.
- Every condition, including `UNKNOWN`, and atomic `LoadedWeather`.

### Application tests

- Initial state and no fabricated weather.
- Per-keystroke input updates without requests/state side effects.
- Trimming; whitespace-only submission preserving results/error; identical Enter/button submission.
- Search success/no-results/failure, old-result preservation, error lifecycle, duplicates/single results, stale callback rejection.
- Exact selected object/coordinates passed to retrieval.
- Requested versus active location, requested-location retention after failure, fallback display, and atomic success.
- Clock-authoritative local-hour and local-date selection at acceptance, local last-updated time, invalid candidate failure, and no partial commit.
- Weather error clearing, stale selection/refresh rejection, and failed-first-load behavior.
- Refresh begins only after success; 15-minute success/failure anchors; single in-flight refresh; no immediate retry; old schedule cancellation on selection.
- Search/weather state independence.

### Infrastructure tests

- Fixed Open-Meteo fixtures; no live network.
- Location filtering with malformed and valid siblings.
- Request parameters for coordinates, units, IANA time zone, required current/hourly/daily variables, and adequate ranges.
- Every provider-code mapping, including unsupported to `UNKNOWN`.
- Eight-day request horizon and rejection when it still cannot cover the acceptance-time 24-hour window.
- Provider daily aggregate conversion without deriving replacements from hourly values, including a seven-day window beginning on the acceptance date in the selected location's zone.
- Malformed JSON/schema, missing fields, invalid numeric values, unusable zones, inconsistent arrays, and insufficient coverage rejection.
- Connection/HTTP/timeout/cancellation/exactly-once/cleanup behavior with controlled Qt network doubles.

### Integration and UI tests

- Compose real controller/presenters with fake services through search → explicit selection → load → refresh success/failure.
- Exercise changed location and deliberately out-of-order callbacks.
- Confirm no provider structures cross adapter boundaries.
- Drive both search triggers and selection in PySide6.
- Assert initial/loading/results/no-results/errors and required metadata.
- Assert every current value/unit, 24 accessible hourly entries, seven daily entries, and local timestamp.
- Assert existing content remains viewable during loading/failure and technical errors are absent.
- Use deferred fake callbacks to verify event-loop responsiveness.
- Verify the 800×600 minimum layout keeps every required section reachable through its vertical/horizontal scroll areas and verify the exact last-updated format.
- Verify orderly shutdown cancels timers/replies and late callbacks cannot reach state listeners or disposed widgets.

Optional live Open-Meteo smoke tests must be explicitly marked external, excluded from normal runs, and never be sole behavioral coverage.

## 12. Implementation sequence

1. Add project metadata and package/test skeleton with only justified dependencies.
2. Implement immutable domain types and validation tests.
3. Define ports, state, typed failures, and deterministic test fakes.
4. Implement controller transitions test-first, including acceptance-time/date slicing, operation IDs, and one-shot refresh scheduling.
5. Implement/test Open-Meteo converters using fixed fixtures.
6. Implement Qt asynchronous transport, timeout/cancellation, adapters, and scheduler.
7. Implement presenters and minimal PySide6 views.
8. Wire the composition root and add integration/UI tests.
9. Optionally run separately marked external smoke tests.

## 13. Unresolved ambiguities

No unresolved specification ambiguities remain after the current constitution and specifications are applied. The remaining details in this plan are implementation choices that do not add behavior beyond those sources.
