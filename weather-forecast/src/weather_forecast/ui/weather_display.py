"""PySide6 weather display that renders complete presentation models."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from weather_forecast.ui.presenters import (
    CurrentWeatherRenderModel,
    DailyForecastRenderModel,
    HourlyForecastRenderModel,
    WeatherContentRenderModel,
    WeatherDisplayRenderModel,
)


class WeatherDisplayView(QWidget):
    """Render weather state without owning data or external-service behavior."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.instruction_label = QLabel(self)
        self.instruction_label.setWordWrap(True)
        self.loading_label = QLabel(self)
        self.error_label = QLabel(self)
        self.error_label.setObjectName("weatherError")

        self.vertical_scroll = QScrollArea(self)
        self.vertical_scroll.setWidgetResizable(True)
        self.vertical_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.instruction_label)
        layout.addWidget(self.loading_label)
        layout.addWidget(self.error_label)
        layout.addWidget(self.vertical_scroll, 1)

        self.location_header: QLabel | None = None
        self.current_labels: dict[str, QLabel] = {}
        self.hourly_scroll: QScrollArea | None = None
        self.hourly_cards: list[QGroupBox] = []
        self.daily_cards: list[QGroupBox] = []
        self.last_updated_label: QLabel | None = None

        self.instruction_label.hide()
        self.loading_label.hide()
        self.error_label.hide()
        self.vertical_scroll.hide()

    def render(self, model: WeatherDisplayRenderModel) -> None:
        """Render one complete weather-display snapshot."""
        self._set_optional_message(self.instruction_label, model.instruction)
        self._set_optional_message(self.loading_label, model.loading_message)
        self._set_optional_message(self.error_label, model.error_message)

        previous = self.vertical_scroll.takeWidget()
        if previous is not None:
            previous.deleteLater()

        self.location_header = None
        self.current_labels = {}
        self.hourly_scroll = None
        self.hourly_cards = []
        self.daily_cards = []
        self.last_updated_label = None

        if model.content is None:
            self.vertical_scroll.hide()
            return

        self.vertical_scroll.setWidget(self._build_content(model.content))
        self.vertical_scroll.show()

    @staticmethod
    def _set_optional_message(label: QLabel, message: str | None) -> None:
        label.setText(message or "")
        label.setVisible(message is not None)

    def _build_content(self, model: WeatherContentRenderModel) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)

        self.location_header = QLabel(model.location_header, content)
        self.location_header.setObjectName("activeLocation")
        header_font = self.location_header.font()
        header_font.setBold(True)
        header_font.setPointSize(header_font.pointSize() + 4)
        self.location_header.setFont(header_font)
        layout.addWidget(self.location_header)

        layout.addWidget(self._build_current(model.current, content))

        hourly_heading = QLabel("Hourly forecast", content)
        layout.addWidget(hourly_heading)
        self.hourly_scroll = self._build_hourly(model.hourly, content)
        layout.addWidget(self.hourly_scroll)

        daily_heading = QLabel("7-day forecast", content)
        layout.addWidget(daily_heading)
        for entry in model.daily:
            card = self._build_daily_card(entry, content)
            self.daily_cards.append(card)
            layout.addWidget(card)

        self.last_updated_label = QLabel(model.last_updated, content)
        self.last_updated_label.setObjectName("lastUpdated")
        layout.addWidget(self.last_updated_label)
        layout.addStretch(1)
        return content

    def _build_current(
        self,
        model: CurrentWeatherRenderModel,
        parent: QWidget,
    ) -> QGroupBox:
        group = QGroupBox("Current weather", parent)
        layout = QGridLayout(group)
        values = (
            ("temperature", "Temperature", model.temperature),
            ("condition", "Condition", model.condition),
            ("feels_like", "Feels like", model.feels_like),
            (
                "precipitation_probability",
                "Precipitation probability",
                model.precipitation_probability,
            ),
            ("relative_humidity", "Humidity", model.relative_humidity),
            ("wind_speed", "Wind speed", model.wind_speed),
            ("precipitation", "Precipitation", model.precipitation),
        )
        for row, (key, title, value) in enumerate(values):
            layout.addWidget(QLabel(f"{title}:", group), row, 0)
            value_label = QLabel(value, group)
            value_label.setObjectName(f"current_{key}")
            layout.addWidget(value_label, row, 1)
            self.current_labels[key] = value_label
        return group

    def _build_hourly(
        self,
        entries: tuple[HourlyForecastRenderModel, ...],
        parent: QWidget,
    ) -> QScrollArea:
        scroll = QScrollArea(parent)
        scroll.setObjectName("hourlyScroll")
        scroll.setWidgetResizable(False)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        for entry in entries:
            card = QGroupBox(entry.local_time, row)
            card.setMinimumWidth(135)
            card_layout = QVBoxLayout(card)
            card_layout.addWidget(QLabel(entry.temperature, card))
            card_layout.addWidget(QLabel(entry.condition, card))
            card_layout.addWidget(
                QLabel(f"Precipitation: {entry.precipitation_probability}", card)
            )
            self.hourly_cards.append(card)
            row_layout.addWidget(card)
        row_layout.addStretch(1)
        row.adjustSize()
        scroll.setWidget(row)
        scroll.setFixedHeight(row.sizeHint().height() + scroll.horizontalScrollBar().sizeHint().height())
        return scroll

    @staticmethod
    def _build_daily_card(
        entry: DailyForecastRenderModel,
        parent: QWidget,
    ) -> QGroupBox:
        card = QGroupBox(entry.local_date, parent)
        layout = QGridLayout(card)
        values = (
            ("Minimum", entry.minimum_temperature),
            ("Maximum", entry.maximum_temperature),
            ("Condition", entry.condition),
            ("Precipitation probability", entry.precipitation_probability),
            ("Precipitation", entry.precipitation),
        )
        for row, (title, value) in enumerate(values):
            layout.addWidget(QLabel(f"{title}:", card), row, 0)
            layout.addWidget(QLabel(value, card), row, 1)
        return card
