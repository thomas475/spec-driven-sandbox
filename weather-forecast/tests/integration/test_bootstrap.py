from __future__ import annotations

import io
import logging
import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from weather_forecast.bootstrap import (  # noqa: E402
    compose_application,
    configure_logging,
)
from weather_forecast.infrastructure.open_meteo_location import (  # noqa: E402
    OpenMeteoLocationProvider,
)
from weather_forecast.infrastructure.open_meteo_weather import (  # noqa: E402
    OpenMeteoWeatherProvider,
)


class BootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "runtime"):
            self.runtime.shutdown()
            self.runtime.window.close()
            self.runtime.window.deleteLater()
            self.app.processEvents()

    def test_composition_uses_one_manager_and_injects_shared_transport(self) -> None:
        self.runtime = compose_application(self.app)

        self.assertIsInstance(self.runtime.network_manager, QNetworkAccessManager)
        self.assertIs(self.runtime.transport._network_manager, self.runtime.network_manager)
        self.assertIsInstance(self.runtime.location_provider, OpenMeteoLocationProvider)
        self.assertIsInstance(self.runtime.weather_provider, OpenMeteoWeatherProvider)
        self.assertIs(self.runtime.location_provider._transport, self.runtime.transport)
        self.assertIs(self.runtime.weather_provider._transport, self.runtime.transport)

    def test_startup_produces_usable_window_without_weather_request(self) -> None:
        self.runtime = compose_application(self.app)
        self.runtime.window.show()
        self.app.processEvents()

        self.assertTrue(self.runtime.window.location_search.search_input.isEnabled())
        self.assertIsNone(self.runtime.controller.state.loaded_weather)
        self.assertIsNone(self.runtime.controller.state.requested_location)
        self.assertEqual(
            self.runtime.network_manager.findChildren(QNetworkReply),
            [],
        )

    def test_default_logging_is_warning_to_stderr_without_file_handler(self) -> None:
        stream = io.StringIO()
        logger = configure_logging(stream)

        logger.debug(
            "payload query=Berlin latitude=52.52 longitude=13.405"
        )
        logger.warning("warning category only")

        self.assertEqual(logger.level, logging.WARNING)
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)
        self.assertNotIsInstance(logger.handlers[0], logging.FileHandler)
        self.assertEqual(stream.getvalue(), "warning category only\n")


if __name__ == "__main__":
    unittest.main()
