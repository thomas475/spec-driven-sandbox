from __future__ import annotations

import sys
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.domain.failures import (  # noqa: E402
    ConnectionFailure,
    HttpFailure,
    InvalidResponseFailure,
    ServiceFailure,
    TimeoutFailure,
    UserFacingError,
)


class FailureTests(unittest.TestCase):
    def test_service_failures_are_distinct_expected_failure_types(self) -> None:
        failures = (
            ConnectionFailure(),
            TimeoutFailure(),
            HttpFailure(),
            InvalidResponseFailure(),
        )

        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                self.assertIsInstance(failure, ServiceFailure)
                self.assertEqual(str(failure), "")
        self.assertEqual(len({type(failure) for failure in failures}), 4)

    def test_service_failures_do_not_accept_raw_technical_details(self) -> None:
        for failure_type in (
            ConnectionFailure,
            TimeoutFailure,
            HttpFailure,
            InvalidResponseFailure,
        ):
            with self.subTest(failure_type=failure_type.__name__):
                with self.assertRaises(TypeError):
                    failure_type("raw provider detail")  # type: ignore[call-arg]

    def test_user_facing_categories_are_semantic_and_distinct(self) -> None:
        self.assertEqual(
            set(UserFacingError),
            {
                UserFacingError.LOCATION_CONNECTION,
                UserFacingError.LOCATION_SEARCH_FAILED,
                UserFacingError.WEATHER_UPDATE_FAILED,
            },
        )
        for error in UserFacingError:
            with self.subTest(error=error):
                self.assertNotIn("http", error.value)
                self.assertNotIn("open-meteo", error.value)


if __name__ == "__main__":
    unittest.main()
