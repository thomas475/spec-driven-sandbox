"""Application composition and process lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import sys
from typing import TextIO

from PySide6.QtNetwork import QNetworkAccessManager
from PySide6.QtWidgets import QApplication

from weather_forecast.application.controller import ApplicationController
from weather_forecast.infrastructure.open_meteo_location import (
    OpenMeteoLocationProvider,
)
from weather_forecast.infrastructure.open_meteo_weather import OpenMeteoWeatherProvider
from weather_forecast.infrastructure.qt_network import QtNetworkTransport
from weather_forecast.infrastructure.qt_scheduler import QtRefreshScheduler
from weather_forecast.ui.main_window import MainWindow


class SystemClock:
    """Read the current, timezone-aware system instant."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(slots=True, weakref_slot=True)
class ApplicationRuntime:
    """Own application-scoped objects and coordinate orderly shutdown."""

    application: QApplication
    network_manager: QNetworkAccessManager
    transport: QtNetworkTransport
    location_provider: OpenMeteoLocationProvider
    weather_provider: OpenMeteoWeatherProvider
    scheduler: QtRefreshScheduler
    clock: SystemClock
    controller: ApplicationController
    window: MainWindow
    _closed: bool = False

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.controller.close()


def configure_logging(stream: TextIO | None = None) -> logging.Logger:
    """Configure non-persistent warning logging to standard error."""
    logger = logging.getLogger("weather_forecast")
    logger.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setLevel(logging.WARNING)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    return logger


def compose_application(application: QApplication) -> ApplicationRuntime:
    """Create the complete object graph without starting network work."""
    network_manager = QNetworkAccessManager(application)
    transport = QtNetworkTransport(network_manager)
    location_provider = OpenMeteoLocationProvider(transport)
    weather_provider = OpenMeteoWeatherProvider(transport)
    scheduler = QtRefreshScheduler(application)
    clock = SystemClock()
    controller = ApplicationController(
        location_provider,
        weather_provider=weather_provider,
        clock=clock,
        refresh_scheduler=scheduler,
    )
    window = MainWindow(controller)
    runtime = ApplicationRuntime(
        application,
        network_manager,
        transport,
        location_provider,
        weather_provider,
        scheduler,
        clock,
        controller,
        window,
    )
    application.aboutToQuit.connect(runtime.shutdown)
    return runtime


def main(argv: list[str] | None = None) -> int:
    """Launch the fully composed Qt application."""
    configure_logging()
    application = QApplication(argv if argv is not None else sys.argv)
    runtime = compose_application(application)
    runtime.window.show()
    return application.exec()
