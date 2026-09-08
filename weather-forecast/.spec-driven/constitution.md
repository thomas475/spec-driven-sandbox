# Project Constitution

## 1. Technology

* Use Python 3.13 or newer.
* Use PySide6 for the user interface.
* Use Open-Meteo as the initial provider for location and weather data.
* Prefer the standard library. Additional dependencies require clear justification.

## 2. Architecture

* Keep user interface and application logic separate.
* Data from external services must be converted into internal application models.
* The user interface must not call external services directly.
* The application logic must be testable without the user interface.
* No global mutable state.

## 3. Domain Model

* Locations are identified by their latitude and longitude, not by their name.
* City name, region, and country are metadata used for display.
* If multiple locations with the same name are found, the user must explicitly select one.
* Duplicate location names must not be automatically resolved by the system.

## 4. External Services

* Open-Meteo is the initial external provider.
* Provider-specific behavior must remain isolated so that another provider can be substituted later without affecting unrelated application layers.
* Weather data should normally be refreshed every 15 minutes.
* External requests must time out after 30 seconds.
* Failed requests must be reported to the application layer.
* External service responses must always be converted into the internal domain model before being used by other layers.

## 5. User Interface

* The user interface must remain responsive while network communication occurs.
* The user interface should remain clean and minimal.
* Loading, empty, and error states must be clearly represented where relevant.

## 6. Testing

* Every specified behavior that contains application logic should be covered by automated tests.
* Integration tests should validate that the major application components work together correctly.
* Automated tests should not depend on a live external service unless the test is explicitly intended as an external integration test.

## 7. Error Handling / Reliability

* Expected errors must not terminate the application.
* Errors should be handled as close as practical to the layer responsible for them.
* User-facing errors must be understandable and must not expose raw implementation details.
* External service responses must be validated before being accepted.
* Malformed or incomplete external responses must be rejected rather than silently accepted.
* Network failures and invalid external responses must be represented explicitly to the application layer.

## 8. Scope & Engineering Discipline

* Do not infer architectural or functional decisions that are not explicitly stated.
* Only implement behavior that is explicitly requested or specified.
* Do not add unnecessary abstractions, dependencies, or infrastructure for hypothetical future requirements.
* If a specification is ambiguous, the ambiguity must be resolved before implementation.
