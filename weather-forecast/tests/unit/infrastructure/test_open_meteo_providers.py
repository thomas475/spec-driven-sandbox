from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.application.ports import (  # noqa: E402
    LocationProvider,
    OperationId,
    RequestHandle,
    WeatherProvider,
)
from weather_forecast.domain.failures import (  # noqa: E402
    ConnectionFailure,
    InvalidResponseFailure,
    TimeoutFailure,
)
from weather_forecast.domain.location import Location  # noqa: E402
from weather_forecast.domain.weather import WeatherPayload  # noqa: E402
from weather_forecast.infrastructure.open_meteo_location import (  # noqa: E402
    OpenMeteoLocationProvider,
)
from weather_forecast.infrastructure.open_meteo_weather import (  # noqa: E402
    OpenMeteoWeatherProvider,
)


BERLIN = Location(52.52, 13.405, "Berlin", "Germany", "Berlin")


@dataclass(slots=True)
class FakeTransportHandle:
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


@dataclass(slots=True)
class PendingTransportRequest:
    url: str
    on_success: object
    on_failure: object
    handle: FakeTransportHandle = field(default_factory=FakeTransportHandle)
    completed: bool = False

    def succeed(self, body: bytes) -> None:
        if self.cancelled_or_completed:
            return
        self.completed = True
        self.on_success(body)

    def fail(self, failure) -> None:
        if self.cancelled_or_completed:
            return
        self.completed = True
        self.on_failure(failure)

    @property
    def cancelled_or_completed(self) -> bool:
        return self.handle.cancelled or self.completed


@dataclass(slots=True)
class FakeTransport:
    requests: list[PendingTransportRequest] = field(default_factory=list)

    def get(self, url, on_success, on_failure):
        request = PendingTransportRequest(url, on_success, on_failure)
        self.requests.append(request)
        return request.handle


class OpenMeteoProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeTransport()
        self.location_provider = OpenMeteoLocationProvider(self.transport)
        self.weather_provider = OpenMeteoWeatherProvider(self.transport)

    def test_providers_satisfy_ports_and_return_transport_handles(self) -> None:
        location_handle = self.location_provider.search(
            "Berlin", OperationId(1), lambda *_: None, lambda *_: None
        )
        weather_handle = self.weather_provider.fetch(
            BERLIN, OperationId(2), lambda *_: None, lambda *_: None
        )

        self.assertIsInstance(self.location_provider, LocationProvider)
        self.assertIsInstance(self.weather_provider, WeatherProvider)
        self.assertIsInstance(location_handle, RequestHandle)
        self.assertIsInstance(weather_handle, RequestHandle)
        self.assertIs(location_handle, self.transport.requests[0].handle)
        self.assertIs(weather_handle, self.transport.requests[1].handle)

    def test_location_success_returns_internal_models_and_original_operation(self) -> None:
        successes = []
        failures = []
        operation_id = OperationId(17)
        self.location_provider.search(
            " Berlin ",
            operation_id,
            lambda *args: successes.append(args),
            lambda *args: failures.append(args),
        )
        request = self.transport.requests[-1]

        request.succeed((FIXTURES / "location_valid.json").read_bytes())

        self.assertEqual(failures, [])
        callback_operation, locations = successes[0]
        self.assertEqual(callback_operation, operation_id)
        self.assertTrue(all(isinstance(location, Location) for location in locations))
        self.assertEqual(parse_qs(urlsplit(request.url).query)["name"], ["Berlin"])

    def test_weather_success_returns_internal_payload_and_original_operation(self) -> None:
        successes = []
        failures = []
        operation_id = OperationId(23)
        self.weather_provider.fetch(
            BERLIN,
            operation_id,
            lambda *args: successes.append(args),
            lambda *args: failures.append(args),
        )
        request = self.transport.requests[-1]

        request.succeed((FIXTURES / "weather_valid.json").read_bytes())

        self.assertEqual(failures, [])
        callback_operation, payload = successes[0]
        self.assertEqual(callback_operation, operation_id)
        self.assertIsInstance(payload, WeatherPayload)
        query = parse_qs(urlsplit(request.url).query)
        self.assertEqual(query["latitude"], ["52.52"])
        self.assertEqual(query["longitude"], ["13.405"])

    def test_transport_failures_propagate_unchanged_as_typed_failures(self) -> None:
        for provider_call, failure in (
            (
                lambda failures: self.location_provider.search(
                    "Berlin",
                    OperationId(31),
                    lambda *_: None,
                    lambda *args: failures.append(args),
                ),
                ConnectionFailure(),
            ),
            (
                lambda failures: self.weather_provider.fetch(
                    BERLIN,
                    OperationId(32),
                    lambda *_: None,
                    lambda *args: failures.append(args),
                ),
                TimeoutFailure(),
            ),
        ):
            with self.subTest(failure_type=type(failure)):
                failures = []
                provider_call(failures)
                self.transport.requests[-1].fail(failure)

                callback_operation, callback_failure = failures[0]
                self.assertIn(callback_operation, (OperationId(31), OperationId(32)))
                self.assertIs(callback_failure, failure)

    def test_parser_failures_are_reported_once_as_invalid_response(self) -> None:
        for provider_call in (
            lambda failures: self.location_provider.search(
                "Berlin",
                OperationId(41),
                lambda *_: None,
                lambda *args: failures.append(args),
            ),
            lambda failures: self.weather_provider.fetch(
                BERLIN,
                OperationId(42),
                lambda *_: None,
                lambda *args: failures.append(args),
            ),
        ):
            with self.subTest(provider=provider_call):
                failures = []
                provider_call(failures)
                request = self.transport.requests[-1]
                request.succeed(b"not json")
                request.succeed(b"not json")
                request.fail(ConnectionFailure())

                self.assertEqual(len(failures), 1)
                self.assertIsInstance(failures[0][1], InvalidResponseFailure)

    def test_cancellation_suppresses_late_success_and_failure(self) -> None:
        successes = []
        failures = []
        handle = self.weather_provider.fetch(
            BERLIN,
            OperationId(51),
            lambda *args: successes.append(args),
            lambda *args: failures.append(args),
        )
        request = self.transport.requests[-1]

        handle.cancel()
        request.succeed((FIXTURES / "weather_valid.json").read_bytes())
        request.fail(ConnectionFailure())

        self.assertTrue(handle.cancelled)
        self.assertEqual(successes, [])
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
