from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
TEST_SUPPORT = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE_ROOT))
sys.path.insert(0, str(TEST_SUPPORT))

from fakes import FakeLocationProvider, StateRecorder  # noqa: E402
from weather_forecast.application.controller import ApplicationController  # noqa: E402
from weather_forecast.application.state import SearchResultState  # noqa: E402
from weather_forecast.domain.failures import (  # noqa: E402
    ConnectionFailure,
    HttpFailure,
    UserFacingError,
)
from weather_forecast.domain.location import Location  # noqa: E402


BERLIN = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")
BERLIN_US = Location(40.0, -75.0, "Berlin", "United States", "Pennsylvania")
MUNICH = Location(48.137, 11.575, "Munich", "Germany", "Bavaria")


class SearchWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = FakeLocationProvider()
        self.recorder = StateRecorder()
        self.controller = ApplicationController(self.provider, (self.recorder,))

    def submit(self, text: str) -> None:
        self.controller.update_search_input(text)
        self.controller.submit_search()

    def complete_success(self, locations: tuple[Location, ...]) -> None:
        self.provider.requests[-1].succeed(locations)

    def test_editing_updates_input_without_starting_search_or_changing_other_state(self) -> None:
        initial = self.controller.state

        self.controller.update_search_input("  Berlin  ")

        self.assertEqual(self.controller.state.search_input, "  Berlin  ")
        self.assertEqual(self.controller.state.search_results, initial.search_results)
        self.assertEqual(self.controller.state.search_error, initial.search_error)
        self.assertFalse(self.controller.state.search_loading)
        self.assertEqual(self.provider.requests, [])
        self.assertIs(self.recorder.latest, self.controller.state)

    def test_submission_trims_only_provider_query_and_preserves_visible_input(self) -> None:
        self.submit("  Berlin  ")

        self.assertEqual(self.provider.requests[0].query, "Berlin")
        self.assertEqual(self.controller.state.search_input, "  Berlin  ")
        self.assertTrue(self.controller.state.search_loading)

    def test_enter_and_button_paths_share_the_same_submission_action(self) -> None:
        enter_provider = FakeLocationProvider()
        button_provider = FakeLocationProvider()
        enter_controller = ApplicationController(enter_provider)
        button_controller = ApplicationController(button_provider)
        enter_controller.update_search_input("Berlin")
        button_controller.update_search_input("Berlin")

        enter_controller.submit_search()
        button_controller.submit_search()

        self.assertEqual(enter_provider.requests[0].query, button_provider.requests[0].query)
        self.assertEqual(enter_controller.state, button_controller.state)

    def test_whitespace_only_submission_is_a_complete_no_op(self) -> None:
        self.submit("Berlin")
        self.complete_success((BERLIN,))
        self.submit("failed")
        self.provider.requests[-1].fail(HttpFailure())
        self.controller.update_search_input("   \t")
        before = self.controller.state
        request_count = len(self.provider.requests)
        snapshot_count = len(self.recorder.snapshots)

        self.controller.submit_search()

        self.assertIs(self.controller.state, before)
        self.assertEqual(len(self.provider.requests), request_count)
        self.assertEqual(len(self.recorder.snapshots), snapshot_count)
        self.assertEqual(self.controller.state.search_results, (BERLIN,))
        self.assertIs(
            self.controller.state.search_error,
            UserFacingError.LOCATION_SEARCH_FAILED,
        )

    def test_starting_search_preserves_results_and_clears_previous_error(self) -> None:
        self.submit("Berlin")
        self.complete_success((BERLIN, BERLIN_US))
        self.submit("failed")
        self.provider.requests[-1].fail(HttpFailure())

        self.submit("Munich")

        self.assertEqual(self.controller.state.search_results, (BERLIN, BERLIN_US))
        self.assertIs(self.controller.state.search_result_state, SearchResultState.RESULTS)
        self.assertTrue(self.controller.state.search_loading)
        self.assertIsNone(self.controller.state.search_error)

    def test_current_success_replaces_results_without_selecting_location(self) -> None:
        self.submit("Berlin")
        self.complete_success((BERLIN, BERLIN_US))
        self.submit("Munich")

        self.complete_success((MUNICH,))

        self.assertEqual(self.controller.state.search_results, (MUNICH,))
        self.assertIs(self.controller.state.search_result_state, SearchResultState.RESULTS)
        self.assertFalse(self.controller.state.search_loading)
        self.assertIsNone(self.controller.state.search_error)
        self.assertIsNone(self.controller.state.requested_location)
        self.assertIsNone(self.controller.state.loaded_weather)

    def test_success_with_no_results_replaces_previous_results(self) -> None:
        self.submit("Berlin")
        self.complete_success((BERLIN,))
        self.submit("missing")

        self.complete_success(())

        self.assertEqual(self.controller.state.search_results, ())
        self.assertIs(
            self.controller.state.search_result_state,
            SearchResultState.NO_RESULTS,
        )
        self.assertFalse(self.controller.state.search_loading)

    def test_failure_preserves_successful_results_and_maps_understandable_error(self) -> None:
        self.submit("Berlin")
        self.complete_success((BERLIN,))
        self.submit("Munich")

        self.provider.requests[-1].fail(ConnectionFailure())

        self.assertEqual(self.controller.state.search_results, (BERLIN,))
        self.assertIs(self.controller.state.search_result_state, SearchResultState.RESULTS)
        self.assertFalse(self.controller.state.search_loading)
        self.assertIs(
            self.controller.state.search_error,
            UserFacingError.LOCATION_CONNECTION,
        )
        self.assertIsNone(self.controller.state.requested_location)
        self.assertIsNone(self.controller.state.loaded_weather)

    def test_older_callbacks_cannot_overwrite_newer_search_state(self) -> None:
        self.submit("Berlin")
        older = self.provider.requests[-1]
        self.submit("Munich")
        newer = self.provider.requests[-1]

        self.assertTrue(older.handle.cancelled)
        older.succeed((BERLIN,))
        older.fail(ConnectionFailure())

        self.assertTrue(self.controller.state.search_loading)
        self.assertEqual(self.controller.state.search_results, ())
        self.assertIsNone(self.controller.state.search_error)

        newer.succeed((MUNICH,))
        older.succeed((BERLIN, BERLIN_US))

        self.assertEqual(self.controller.state.search_results, (MUNICH,))
        self.assertFalse(self.controller.state.search_loading)
        self.assertIsNone(self.controller.state.search_error)

    def test_non_connection_failure_uses_generic_search_error(self) -> None:
        self.submit("Berlin")

        self.provider.requests[-1].fail(HttpFailure())

        self.assertIs(
            self.controller.state.search_error,
            UserFacingError.LOCATION_SEARCH_FAILED,
        )
        self.assertIsNone(self.controller.state.requested_location)
        self.assertIsNone(self.controller.state.loaded_weather)


if __name__ == "__main__":
    unittest.main()
