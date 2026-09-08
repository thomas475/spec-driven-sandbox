from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.ui.location_search import LocationSearchView  # noqa: E402
from weather_forecast.ui.presenters import (  # noqa: E402
    LocationResultRenderModel,
    LocationSearchRenderModel,
    NO_RESULTS_MESSAGE,
    SEARCHING_MESSAGE,
)


BERLIN = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")
BERLIN_US = Location(44.4687, -71.1851, "Berlin", "United States", "New Hampshire")
PARIS = Location(48.8575, 2.3514, "Paris", "France")


def result(location: Location) -> LocationResultRenderModel:
    parts = [location.city]
    if location.region:
        parts.append(location.region)
    parts.append(location.country)
    return LocationResultRenderModel(
        location,
        location.city,
        location.country,
        location.region,
        ", ".join(parts),
    )


def model(
    *,
    input_text: str = "",
    results: tuple[LocationResultRenderModel, ...] = (),
    loading_message: str | None = None,
    empty_message: str | None = None,
    error_message: str | None = None,
) -> LocationSearchRenderModel:
    return LocationSearchRenderModel(
        input_text=input_text,
        results=results,
        loading=loading_message is not None,
        loading_message=loading_message,
        empty_message=empty_message,
        error_message=error_message,
    )


class LocationSearchViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.view = LocationSearchView()
        self.view.show()

    def tearDown(self) -> None:
        self.view.close()
        self.view.deleteLater()
        self.app.processEvents()

    def test_text_edits_emit_updates_without_submitting_and_preserve_exact_text(self) -> None:
        edits = []
        submissions = []
        self.view.input_changed.connect(edits.append)
        self.view.search_submitted.connect(lambda: submissions.append("submit"))

        QTest.keyClicks(self.view.search_input, "  Berlin  ")

        self.assertEqual(edits[-1], "  Berlin  ")
        self.assertEqual(self.view.search_input.text(), "  Berlin  ")
        self.assertEqual(submissions, [])

    def test_enter_and_button_emit_the_same_submission_intent(self) -> None:
        submissions = []
        self.view.search_submitted.connect(lambda: submissions.append("submit"))

        QTest.keyClick(self.view.search_input, Qt.Key.Key_Return)
        QTest.mouseClick(self.view.search_button, Qt.MouseButton.LeftButton)

        self.assertEqual(submissions, ["submit", "submit"])

    def test_render_does_not_turn_state_updates_into_edit_intents(self) -> None:
        edits = []
        self.view.input_changed.connect(edits.append)

        self.view.render(model(input_text="  Berlin  "))

        self.assertEqual(self.view.search_input.text(), "  Berlin  ")
        self.assertEqual(edits, [])

    def test_results_are_below_input_with_complete_visible_metadata(self) -> None:
        self.view.render(model(results=(result(BERLIN), result(PARIS))))

        self.assertEqual(self.view.results_list.count(), 2)
        self.assertEqual(
            self.view.results_list.item(0).text(),
            "Berlin, Berlin, Germany",
        )
        self.assertEqual(self.view.results_list.item(1).text(), "Paris, France")
        self.assertGreater(
            self.view.results_list.mapTo(self.view, self.view.results_list.pos()).y(),
            self.view.search_input.y(),
        )

    def test_duplicate_and_single_results_are_not_auto_selected(self) -> None:
        self.view.render(model(results=(result(BERLIN), result(BERLIN_US))))
        self.assertEqual(self.view.results_list.count(), 2)
        self.assertEqual(self.view.results_list.currentRow(), -1)

        self.view.render(model(results=(result(PARIS),)))
        self.assertEqual(self.view.results_list.count(), 1)
        self.assertEqual(self.view.results_list.currentRow(), -1)

    def test_loading_and_error_do_not_remove_old_results_and_empty_is_explicit(self) -> None:
        self.view.render(
            model(
                results=(result(BERLIN),),
                loading_message=SEARCHING_MESSAGE,
                error_message="Unable to search for locations. Please try again.",
            )
        )

        self.assertEqual(self.view.results_list.count(), 1)
        self.assertTrue(self.view.loading_label.isVisible())
        self.assertTrue(self.view.error_label.isVisible())
        self.assertEqual(self.view.loading_label.text(), SEARCHING_MESSAGE)

        self.view.render(model(empty_message=NO_RESULTS_MESSAGE))
        self.assertEqual(self.view.results_list.count(), 0)
        self.assertTrue(self.view.empty_label.isVisible())
        self.assertEqual(self.view.empty_label.text(), NO_RESULTS_MESSAGE)

    def test_clicking_result_emits_the_complete_location_object(self) -> None:
        selections = []
        self.view.location_selected.connect(selections.append)
        self.view.render(model(results=(result(BERLIN), result(BERLIN_US))))
        item = self.view.results_list.item(1)

        self.view.results_list.itemClicked.emit(item)

        self.assertEqual(len(selections), 1)
        self.assertIs(selections[0], BERLIN_US)
        self.assertEqual(
            (selections[0].latitude, selections[0].longitude),
            (44.4687, -71.1851),
        )


if __name__ == "__main__":
    unittest.main()
