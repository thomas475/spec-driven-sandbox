"""PySide6 location-search widget that renders state and emits user intent."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from weather_forecast.domain.location import Location
from weather_forecast.ui.presenters import LocationSearchRenderModel


class LocationSearchView(QWidget):
    """Render location-search state without owning workflow state."""

    input_changed = Signal(str)
    search_submitted = Signal()
    location_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search for a city")
        self.search_button = QPushButton("Search", self)
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.search_input, 1)
        input_layout.addWidget(self.search_button)

        self.loading_label = QLabel(self)
        self.error_label = QLabel(self)
        self.error_label.setObjectName("searchError")
        self.empty_label = QLabel(self)
        self.results_list = QListWidget(self)

        layout = QVBoxLayout(self)
        layout.addLayout(input_layout)
        layout.addWidget(self.loading_label)
        layout.addWidget(self.error_label)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.results_list)

        self.search_input.textEdited.connect(self.input_changed)
        self.search_input.returnPressed.connect(self.search_submitted)
        self.search_button.clicked.connect(self.search_submitted)
        self.results_list.itemClicked.connect(self._result_clicked)

        self.loading_label.hide()
        self.error_label.hide()
        self.empty_label.hide()

    def render(self, model: LocationSearchRenderModel) -> None:
        """Replace presentation state without emitting user intents."""
        if self.search_input.text() != model.input_text:
            self.search_input.setText(model.input_text)

        self._set_optional_message(self.loading_label, model.loading_message)
        self._set_optional_message(self.error_label, model.error_message)
        self._set_optional_message(self.empty_label, model.empty_message)

        self.results_list.clear()
        for result in model.results:
            item = QListWidgetItem(result.display_text)
            item.setData(Qt.ItemDataRole.UserRole, result.location)
            self.results_list.addItem(item)
        self.results_list.setCurrentRow(-1)

    @staticmethod
    def _set_optional_message(label: QLabel, message: str | None) -> None:
        label.setText(message or "")
        label.setVisible(message is not None)

    def _result_clicked(self, item: QListWidgetItem) -> None:
        location = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(location, Location):
            self.location_selected.emit(location)
