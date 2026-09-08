# Weather Forecast Application Tasks

The tasks below are ordered by implementation dependency. They use `.spec-driven/constitution.md`, all specifications under `specs/`, and `.spec-driven/plan.md` as authoritative sources. No unresolved contradiction exists among those sources.

## Phase 1 — Project foundation

### T001 — Create the Python project skeleton

**Goal**
Create an installable Python 3.13+ source-layout project with the package boundaries and test directories defined by the plan, using PySide6 as the only runtime dependency.

**Files**
- `pyproject.toml`
- `src/weather_forecast/__init__.py`
- `src/weather_forecast/__main__.py`
- `src/weather_forecast/domain/__init__.py`
- `src/weather_forecast/application/__init__.py`
- `src/weather_forecast/infrastructure/__init__.py`
- `src/weather_forecast/ui/__init__.py`
- `tests/unit/domain/`
- `tests/unit/application/`
- `tests/unit/infrastructure/`
- `tests/integration/`
- `tests/ui/`
- `tests/external/`

**References**
- Constitution §§1, 2, 6, and 8
- Plan §§1, 2, and 12

**Dependencies**
- None

**Tests**
- Add a smoke test that imports `weather_forecast` from the configured source layout.
- Verify project metadata requires Python 3.13+ and declares no runtime dependency other than PySide6.

**Done when**
- The package and test skeleton matches the finalized plan, the import smoke test passes, and no application behavior or unnecessary dependency has been added.

## Phase 2 — Domain models and application contracts

### T002 — Implement location and failure domain types

**Goal**
Define the immutable coordinate-identified `Location` model and the typed service/application failures used across layer boundaries.

**Files**
- `src/weather_forecast/domain/location.py`
- `src/weather_forecast/domain/failures.py`
- `tests/unit/domain/test_location.py`
- `tests/unit/domain/test_failures.py`

**References**
- Constitution §§3 and 7
- Location Search: Search Results, Malformed Results, and Error Cases
- Plan §§3 and 9

**Dependencies**
- T001

**Tests**
- Test finite, in-range latitude/longitude validation.
- Test that identity is based on coordinates rather than city metadata.
- Test required non-empty city/country and optional region.
- Test the distinct connection, timeout, HTTP, invalid-response, and user-facing failure categories without exposing provider details.

**Done when**
- Valid locations and failures can be constructed as immutable internal values, invalid locations are rejected, and same-name locations with different coordinates remain distinct.

### T003 — Implement weather domain values and validation

**Goal**
Define immutable provider-independent weather conditions, current weather, hourly/daily entries, staged payloads, accepted reports, and atomic loaded-weather aggregates with all specified validation.

**Files**
- `src/weather_forecast/domain/weather.py`
- `tests/unit/domain/test_weather.py`

**References**
- Weather Retrieval: Current Weather Data through Data Validation
- Weather Retrieval: Hourly Forecast, Daily Forecast, Time Zone, and Units
- Plan §3

**Dependencies**
- T001
- T002

**Tests**
- Test all eight internal weather conditions, including `UNKNOWN`.
- Test finite numeric values, percentage bounds, and non-negative wind/precipitation.
- Test resolvable IANA identifiers and aware local hourly timestamps; reject unusable zones.
- Test chronological/consecutive hourly and daily entries and insufficient coverage.
- Test accepted reports require exactly 24 hours starting at the acceptance hour and seven days starting at the acceptance local date.
- Test `LoadedWeather` atomically pairs location, report, and last-updated instant.

**Done when**
- All specified weather data can be represented without provider types, malformed/incomplete values are rejected, and no partial report can form active weather.

### T004 — Define application ports and immutable state

**Goal**
Define provider, scheduler, clock, request-handle, and state-listener protocols plus the immutable application state that distinguishes all required search and weather concepts.

**Files**
- `src/weather_forecast/application/ports.py`
- `src/weather_forecast/application/state.py`
- `tests/unit/application/test_state.py`

**References**
- Application Flow: State Consistency and Requested and Active Locations
- Location Search: Search State
- Weather Retrieval: Requested and Active Locations
- Plan §§4 and 6

**Dependencies**
- T002
- T003

**Tests**
- Test the initial snapshot: empty input/results, no requested/active location, no weather, no loading, and no errors.
- Test distinct initial/results/no-results search states and location-load/refresh weather states.
- Test immutable snapshots and separation of requested location from `loaded_weather.location`.
- Use static/runtime contract doubles to verify ports accept and return only declared internal types.

**Done when**
- Application and infrastructure/UI boundaries are explicit, contain no Qt/provider payload types, and represent every state distinction required by the specifications.

### T005 — Add deterministic application test doubles

**Goal**
Provide reusable fake providers, clock, one-shot scheduler, request handles, and state recorder so application workflows can be tested without UI or live services.

**Files**
- `tests/unit/application/fakes.py`
- `tests/unit/application/test_fakes.py`

**References**
- Constitution §§2 and 6
- Plan §§4 and 11

**Dependencies**
- T004

**Tests**
- Test controlled success/failure completion and deliberate out-of-order callbacks.
- Test fake request cancellation, clock advancement, one-shot timer firing/cancellation, and captured state snapshots.

**Done when**
- Later controller tests can deterministically drive requests, time, scheduling, cancellation races, and state publication with no PySide6 widget or network dependency.

## Phase 3 — Application flow and state coordination

### T006 — Implement search input and search workflow

**Goal**
Implement search editing/submission and result/error transitions, including trim-only submission, preservation rules, and stale-operation protection.

**Files**
- `src/weather_forecast/application/controller.py`
- `tests/unit/application/test_search_workflow.py`

**References**
- Location Search: all requirements and acceptance criteria except provider parsing details
- Application Flow: Initial State, Location Search Flow, Error Lifecycle, and State Consistency
- Plan §7, Startup and editing; Search submission

**Dependencies**
- T004
- T005

**Tests**
- Test per-keystroke input updates without starting requests or changing results/errors.
- Test Enter/button-equivalent submission through the same controller action contract.
- Test trimming only the submitted query while preserving text exactly as entered.
- Test whitespace-only no-op preserves results and error.
- Test loading/error lifecycle and preservation/replacement of successful results, including no-results.
- Test old results remain during loading and after failure.
- Test older successes/errors cannot overwrite a newer search and obsolete handles are aborted.
- Test a failed search never starts weather retrieval.

**Done when**
- Every specified search-state transition passes deterministic unit tests and only the most recently started search can alter visible search state.

### T007 — Implement location selection and weather acceptance

**Goal**
Implement explicit selection, requested-versus-active state, weather request lifecycle, clock-authoritative hourly/daily slicing, atomic success, and failure preservation.

**Files**
- `src/weather_forecast/application/controller.py`
- `tests/unit/application/test_weather_workflow.py`

**References**
- Weather Retrieval: Fetch Trigger, State Handling, Requested and Active Locations, Overlapping Weather Requests, and Failed Initial Retrieval
- Application Flow: Location Selection Flow through Failed Retrieval
- Plan §7, Selection and initial/location-change retrieval

**Dependencies**
- T003
- T005
- T006

**Tests**
- Test that explicit selection passes the complete location/coordinates and starts retrieval immediately.
- Test `requested_location` changes only on explicit selection and remains after failure.
- Test old loaded location/weather/timestamp remain visible while a new location loads or fails.
- Test acceptance uses one clock instant converted through the payload's IANA zone, selects 24 hours from its containing hour and seven daily aggregates from its local date, and sets local `last_updated`.
- Test complete success atomically commits location/report/timestamp and clears errors.
- Test invalid/partial candidates follow the failure transition with no partial commit.
- Test a failed first load creates no active location or refresh schedule.
- Test older selection successes/errors cannot overwrite newer state and obsolete requests are aborted.

**Done when**
- Only a complete report for the most recent explicit selection can become active, while every specified fallback and requested-location rule is preserved.

### T008 — Implement automatic refresh coordination

**Goal**
Implement one-shot 15-minute refresh scheduling, success/failure rescheduling, single-request enforcement, and invalidation on location change.

**Files**
- `src/weather_forecast/application/controller.py`
- `tests/unit/application/test_refresh_workflow.py`

**References**
- Weather Retrieval: Automatic Refresh and Location Changes
- Application Flow: Changing Location and Automatic Refresh
- Plan §7, Refresh

**Dependencies**
- T007

**Tests**
- Test no schedule exists before the first successful load.
- Test success schedules one refresh exactly 15 minutes later.
- Test refresh retains loaded data/timestamp and clears the prior weather error while loading.
- Test refresh success atomically replaces data/time and schedules from success.
- Test refresh failure preserves data/time, shows an error, performs no immediate retry, and schedules 15 minutes after failure completion.
- Test no concurrent refresh starts and stale timer/request callbacks are harmless.
- Test explicit selection cancels the prior active-location schedule and refresh never modifies `requested_location`.

**Done when**
- Refresh behavior, timing anchors, preservation, and concurrency rules exactly match both weather and application-flow specifications.

## Phase 4 — Open-Meteo and Qt infrastructure

### T009 — Implement Open-Meteo location conversion

**Goal**
Build the Open-Meteo geocoding request and convert its JSON response into valid internal locations while discarding malformed entries individually.

**Files**
- `src/weather_forecast/infrastructure/open_meteo_location.py`
- `tests/unit/infrastructure/test_open_meteo_location.py`
- `tests/unit/infrastructure/fixtures/location_*.json`

**References**
- Location Search: Search Results, Malformed Results, No Results, and Error Cases
- Constitution §4
- Plan §8

**Dependencies**
- T002
- T004

**Tests**
- Test encoded trimmed-query request construction.
- Test valid coordinate/city/country conversion and optional region.
- Test malformed siblings are discarded without losing valid entries.
- Test duplicate city names remain separate and a wholly invalid response becomes a successful empty result when structurally valid.
- Test malformed top-level JSON/schema reports `InvalidResponseFailure`.

**Done when**
- Location conversion returns only internal `Location` values, never auto-resolves duplicates, and handles individual versus whole-response invalidity as specified.

### T010 — Implement Open-Meteo weather conversion

**Goal**
Build the finalized eight-day Open-Meteo request and convert complete provider data into a validated provider-independent `WeatherPayload`.

**Files**
- `src/weather_forecast/infrastructure/open_meteo_weather.py`
- `tests/unit/infrastructure/test_open_meteo_weather.py`
- `tests/unit/infrastructure/fixtures/weather_*.json`

**References**
- Weather Retrieval: Current Weather Data through Data Validation
- Weather Retrieval: Error Cases and Acceptance Criteria
- Plan §§3 and 8

**Dependencies**
- T003
- T004

**Tests**
- Test coordinates, `timezone=auto`, explicit units, required variables, and `forecast_days=8` request parameters.
- Test all finalized WMO mappings, including every unsupported code to `UNKNOWN`.
- Test current, hourly, and provider-supplied daily aggregate conversion without deriving daily values from hourly data.
- Test IANA-zone resolution and aware local timestamps/dates.
- Test missing fields, malformed JSON/schema, mismatched series, non-finite/out-of-range/negative values, unusable zones, and inadequate horizon fail the whole response.
- Test fixtures contain enough data for acceptance-time 24-hour and seven-day selection.

**Done when**
- Valid Open-Meteo data produces only a complete internal `WeatherPayload`, all specified invalid responses are rejected, and provider codes/structures do not escape the adapter module.

### T011 — Implement asynchronous Qt network transport

**Goal**
Provide shared non-blocking `QNetworkAccessManager` request mechanics with 30-second timeouts, classification, cancellation, exactly-once callbacks, and cleanup.

**Files**
- `src/weather_forecast/infrastructure/qt_network.py`
- `tests/unit/infrastructure/test_qt_network.py`

**References**
- Constitution §§4, 5, and 7
- Application Flow: UI responsiveness and stale-operation criteria
- Plan §5 and §9

**Dependencies**
- T002
- T004

**Tests**
- Use controlled Qt network doubles to test asynchronous success without blocking the event loop.
- Test connection and HTTP classification.
- Test the single-shot 30-second timeout aborts and reports `TimeoutFailure` once.
- Test manual cancellation races, completion-once behavior, timer/reply disposal, and late callback safety.
- Test raw Qt/HTTP details do not cross the transport contract.

**Done when**
- Requests are entirely signal-driven, enforce the timeout, complete once, clean up reliably, and never block the GUI event loop.

### T012 — Connect Open-Meteo providers to Qt transport

**Goal**
Complete `LocationProvider` and `WeatherProvider` implementations by composing the tested request/conversion logic with the shared asynchronous transport.

**Files**
- `src/weather_forecast/infrastructure/open_meteo_location.py`
- `src/weather_forecast/infrastructure/open_meteo_weather.py`
- `tests/unit/infrastructure/test_open_meteo_providers.py`

**References**
- Constitution §§2, 4, and 7
- Plan §§4, 5, 8, and 9

**Dependencies**
- T009
- T010
- T011

**Tests**
- Test each provider returns a cancellable request handle and exactly one typed callback.
- Test transport failures propagate as typed failures and parser failures as `InvalidResponseFailure`.
- Test successful callbacks contain only internal models and the original operation ID.
- Test cancellation/late completion cannot be mistaken for a current visible failure.

**Done when**
- Both provider protocols are fully implemented asynchronously and all provider-specific behavior remains isolated from application and UI layers.

### T013 — Implement the Qt one-shot refresh scheduler

**Goal**
Implement the scheduler port using cancellable single-shot `QTimer`s without embedding workflow policy in infrastructure.

**Files**
- `src/weather_forecast/infrastructure/qt_scheduler.py`
- `tests/unit/infrastructure/test_qt_scheduler.py`

**References**
- Weather Retrieval: Automatic Refresh
- Plan §§4, 7, and 8

**Dependencies**
- T004

**Tests**
- Test a callback fires once after the requested delay.
- Test cancellation prevents firing and timer objects are cleaned up.
- Test the scheduler does not create repeating/concurrent policy on its own.

**Done when**
- The application can schedule and cancel one-shot refresh callbacks through the port with no Qt type exposed to controller logic.

## Phase 5 — Presentation and UI

### T014 — Implement presenters and render models

**Goal**
Convert application snapshots into clean UI render models, exact unit/timestamp formatting, internal condition labels, and understandable redacted errors.

**Files**
- `src/weather_forecast/ui/presenters.py`
- `tests/ui/test_presenters.py`

**References**
- Weather Display: all requirements
- Location Search: Search Results, No Results, and Error Cases
- Constitution §§5 and 7
- Plan §§9 and 10

**Dependencies**
- T003
- T004

**Tests**
- Test city/country and optional search-result region formatting.
- Test every current/hourly/daily value includes the specified unit or percentage representation.
- Test all condition labels, including a safe `unknown` label.
- Test `Last updated: YYYY-MM-DD HH:MM <IANA zone>` formatting.
- Test initial, loading, no-results, and independent search/weather errors.
- Test no raw exception, URL, payload, HTTP, Qt, or provider detail appears in user messages.

**Done when**
- Every specified state/value has a deterministic view representation and presentation contains no application mutation or external-service access.

### T015 — Implement the location-search view

**Goal**
Build the minimal PySide6 search field, button, loading/error/no-results states, and explicitly selectable result list below the field.

**Files**
- `src/weather_forecast/ui/location_search.py`
- `tests/ui/test_location_search_view.py`

**References**
- Location Search: all UI requirements and acceptance criteria
- Plan §10

**Dependencies**
- T014

**Tests**
- Test text edits emit input updates without search submission.
- Test Enter and button emit the same submission action.
- Test visible text remains exactly as typed.
- Test results appear below input with city/country and optional region.
- Test duplicate and single results remain separately selectable and never auto-select.
- Test old results remain visible with non-destructive loading/error indicators and successful empty results show “No results.”
- Test selection emits the complete `Location` object.

**Done when**
- The widget renders every specified search state and exposes only user intents, with no provider access or authoritative state ownership.

### T016 — Implement the weather-display view

**Goal**
Build the minimal PySide6 weather display with initial, active, loading, and error states plus all required current, 24-hour, seven-day, unit, and timestamp content.

**Files**
- `src/weather_forecast/ui/weather_display.py`
- `tests/ui/test_weather_display_view.py`

**References**
- Weather Display: all requirements and acceptance criteria
- Plan §10

**Dependencies**
- T014

**Tests**
- Test initial instruction has no fabricated weather or failed requested-location header.
- Test active header shows city/country and all required current values/units.
- Test 24 local hourly entries are accessible through horizontal scrolling.
- Test seven daily entries and required aggregates are displayed.
- Test exact local last-updated format.
- Test existing data stays accessible under update/error states and failed updates preserve the rendered timestamp.
- Test the vertical/horizontal scroll layout keeps all sections reachable at 800×600 logical pixels.

**Done when**
- The view accurately renders every weather-display state without partial replacement, blocking interaction, or external-service knowledge.

### T017 — Compose the main window and controller bindings

**Goal**
Compose both views, connect user actions to the controller, and render published snapshots while keeping UI and application ownership separate.

**Files**
- `src/weather_forecast/ui/main_window.py`
- `tests/ui/test_main_window.py`

**References**
- Application Flow: Initial State, State Consistency, and End-to-End Acceptance Criteria
- Constitution §§2 and 5
- Plan §§4, 6, and 10

**Dependencies**
- T006
- T007
- T008
- T015
- T016

**Tests**
- Test startup wiring renders immediate search availability and no-weather instruction.
- Test UI actions invoke only controller methods and snapshots render both views.
- Test search and weather loading/errors remain independent.
- Test deferred fake provider callbacks leave the Qt event loop and visible existing content responsive.

**Done when**
- The combined window drives the complete controller interface without directly calling infrastructure or duplicating application state.

## Phase 6 — Composition and cross-layer integration

### T018 — Build the composition root and shutdown lifecycle

**Goal**
Wire one application-scoped network manager, providers, scheduler, clock, controller, presenters, and views; add the executable entry point and finalized safe shutdown behavior.

**Files**
- `src/weather_forecast/bootstrap.py`
- `src/weather_forecast/__main__.py`
- `tests/integration/test_bootstrap.py`
- `tests/integration/test_shutdown.py`

**References**
- Constitution §§1, 2, 4, 5, and 7
- Plan §§2, 5, 8, 9, and 10

**Dependencies**
- T012
- T013
- T017

**Tests**
- Test composition uses one `QNetworkAccessManager` and injects dependencies without global mutable state.
- Test startup produces a usable window without making a weather request.
- Test shutdown marks the controller closed, cancels timer/replies, disconnects listeners, and makes late callbacks harmless.
- Test default logging uses standard error at `WARNING`, installs no file handler, and does not persist/emit sensitive payload or query/coordinate data.

**Done when**
- `python -m weather_forecast` launches the fully composed application, and startup/shutdown honor all finalized architectural and lifecycle decisions.

### T019 — Verify integrated application flows

**Goal**
Exercise the major cross-layer behaviors with real controller/presenters/views and deterministic fake providers, clock, scheduler, and network completions.

**Files**
- `tests/integration/test_application_flow.py`
- `tests/integration/test_async_ordering.py`

**References**
- All acceptance criteria in `specs/application-flow/spec.md`
- Constitution §6
- Plan §11, Integration and UI tests

**Dependencies**
- T018

**Tests**
- Test startup → edit → trimmed search → explicit result selection → weather success → refresh success/failure.
- Test no-results and failed-search flows preserve the required previous state and never trigger weather.
- Test location change success/failure preserves fallback display until an atomic valid replacement.
- Deliver overlapping search, selection, and refresh callbacks out of order and verify none overwrite newer state.
- Test failed first retrieval, explicit reselection retry, refresh timing, and no concurrent refresh.
- Test deferred asynchronous completions keep the UI event loop responsive.

**Done when**
- The major components work together exactly as the application-flow specification describes, without live external services or timing nondeterminism.

## Phase 7 — Final verification

### T020 — Perform specification and constitution verification

**Goal**
Run the complete automated suite and audit the finished implementation against every authoritative acceptance criterion and architectural constraint.

**Files**
- `.spec-driven/constitution.md` (read-only verification source)
- `.spec-driven/plan.md` (read-only verification source)
- `specs/location-search/spec.md` (read-only verification source)
- `specs/weather-retrieval/spec.md` (read-only verification source)
- `specs/weather-display/spec.md` (read-only verification source)
- `specs/application-flow/spec.md` (read-only verification source)
- all implementation and test files created by T001–T019

**References**
- Entire constitution
- All requirements and acceptance criteria in all four specifications
- Plan §§1–13

**Dependencies**
- T019

**Tests**
- Run every domain, application, infrastructure, UI, and integration test in the normal deterministic suite.
- Confirm all acceptance criteria have direct implementation and proportionate automated coverage.
- Confirm stale asynchronous search/weather/refresh results cannot overwrite newer state.
- Confirm failed searches and weather requests preserve the exact required previous valid state and timestamps.
- Confirm the UI remains responsive throughout network waiting and all external requests time out after 30 seconds.
- Confirm no normal test depends on a live service; any optional external smoke test is separately marked and excluded.

**Done when**
- All required automated tests pass.
- Every acceptance criterion in all four specifications is accounted for.
- No unspecified functionality, unnecessary dependency, persistence, telemetry, or hypothetical abstraction was introduced.
- No constitution rule is violated: UI/application/provider separation holds, provider data is converted before crossing layers, application logic is UI-independent, and no global mutable state exists.
- Stale results, failure-preservation behavior, atomic weather replacement, timeout handling, and UI responsiveness have explicit passing verification.
