"""Main window composition for views and application-controller bindings."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from weather_forecast.application.controller import ApplicationController
from weather_forecast.application.state import ApplicationState
from weather_forecast.ui.location_search import LocationSearchView
from weather_forecast.ui.presenters import present_application
from weather_forecast.ui.weather_display import WeatherDisplayView


class MainWindow(QMainWindow):
    """Forward user intents and render controller-owned state snapshots."""

    def __init__(
        self,
        controller: ApplicationController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller

        self.setWindowTitle("Weather Forecast")
        self.setMinimumSize(800, 600)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        self.location_search = LocationSearchView(central)
        self.weather_display = WeatherDisplayView(central)
        layout.addWidget(self.location_search)
        layout.addWidget(self.weather_display, 1)
        self.setCentralWidget(central)

        self.location_search.input_changed.connect(
            self._controller.update_search_input
        )
        self.location_search.search_submitted.connect(
            self._controller.submit_search
        )
        self.location_search.location_selected.connect(
            self._controller.select_location
        )
        self._controller.add_listener(self.render_state)
        self.render_state(self._controller.state)

    def render_state(self, state: ApplicationState) -> None:
        """Render both views from the same immutable application snapshot."""
        model = present_application(state)
        self.location_search.render(model.search)
        self.weather_display.render(model.weather)
