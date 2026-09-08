# Weather Forecast

A small desktop weather application built with Python and PySide6. It allows searching for a city, selecting a matching location, and viewing the current weather, the next 24 hours, and a seven-day forecast. Weather and location data are provided by Open-Meteo.

## Requirements

* Python 3.13 or newer
* Internet access
* A desktop environment with Qt support

## Installation

Create and activate a virtual environment, then install the project:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run

To start the application:

```bash
python -m weather_forecast
```

## Tests

To run the test suite:

```bash
python -m unittest discover -s tests
```
