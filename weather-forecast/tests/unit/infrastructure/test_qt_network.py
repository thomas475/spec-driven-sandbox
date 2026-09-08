from __future__ import annotations

import sys
import unittest
from enum import Enum
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.application.ports import RequestHandle  # noqa: E402
from weather_forecast.domain.failures import (  # noqa: E402
    ConnectionFailure,
    HttpFailure,
    TimeoutFailure,
)
from weather_forecast.infrastructure.qt_network import (  # noqa: E402
    REQUEST_TIMEOUT_MS,
    QtNetworkTransport,
)


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def disconnect(self, callback) -> None:
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def emit(self) -> None:
        for callback in tuple(self.callbacks):
            callback()


class FakeTimer:
    def __init__(self) -> None:
        self.timeout = FakeSignal()
        self.single_shot = False
        self.interval = None
        self.running = False
        self.deleted = False

    def setSingleShot(self, single_shot: bool) -> None:
        self.single_shot = single_shot

    def start(self, interval: int) -> None:
        self.interval = interval
        self.running = True

    def stop(self) -> None:
        self.running = False

    def deleteLater(self) -> None:
        self.deleted = True

    def fire(self) -> None:
        self.timeout.emit()


class FakeReply:
    def __init__(self, *, status=200, network_error=0, body=b"response") -> None:
        self.finished = FakeSignal()
        self.status = status
        self.network_error = network_error
        self.body = body
        self.aborted = False
        self.deleted = False

    def attribute(self, attribute):
        if attribute != "http_status":
            raise AssertionError("unexpected status attribute")
        return self.status

    def error(self):
        return self.network_error

    def readAll(self):
        return self.body

    def abort(self) -> None:
        self.aborted = True

    def deleteLater(self) -> None:
        self.deleted = True

    def finish(self) -> None:
        self.finished.emit()


class FakeNetworkManager:
    def __init__(self, reply: FakeReply) -> None:
        self.reply = reply
        self.requests = []

    def get(self, request):
        self.requests.append(request)
        return self.reply


class TransportHarness:
    def __init__(self, reply: FakeReply) -> None:
        self.reply = reply
        self.timer = FakeTimer()
        self.manager = FakeNetworkManager(reply)
        self.successes = []
        self.failures = []
        self.transport = QtNetworkTransport(
            self.manager,
            timer_factory=lambda: self.timer,
            request_factory=lambda url: ("GET", url),
            status_attribute="http_status",
        )

    def start(self):
        return self.transport.get(
            "https://example.test/data",
            self.successes.append,
            self.failures.append,
        )


class QtNetworkTransportTests(unittest.TestCase):
    def test_starts_signal_driven_request_and_returns_without_waiting(self) -> None:
        harness = TransportHarness(FakeReply(body=b"ok"))

        handle = harness.start()

        self.assertIsInstance(handle, RequestHandle)
        self.assertEqual(
            harness.manager.requests,
            [("GET", "https://example.test/data")],
        )
        self.assertEqual(harness.successes, [])
        self.assertEqual(harness.failures, [])
        harness.reply.finish()
        self.assertEqual(harness.successes, [b"ok"])

    def test_classifies_connection_and_http_failures_without_raw_details(self) -> None:
        cases = (
            (FakeReply(status=200, network_error=7), ConnectionFailure),
            (FakeReply(status=404, network_error=203), HttpFailure),
            (FakeReply(status=None, network_error=0), HttpFailure),
        )
        for reply, expected_type in cases:
            with self.subTest(expected_type=expected_type):
                harness = TransportHarness(reply)
                harness.start()
                reply.finish()

                self.assertEqual(harness.successes, [])
                self.assertEqual(len(harness.failures), 1)
                failure = harness.failures[0]
                self.assertIsInstance(failure, expected_type)
                self.assertEqual(failure.args, ())
                self.assertEqual(str(failure), "")

    def test_accepts_pyside_style_enum_network_error_values(self) -> None:
        class NetworkError(Enum):
            NO_ERROR = 0

        harness = TransportHarness(FakeReply(network_error=NetworkError.NO_ERROR))
        harness.start()

        harness.reply.finish()

        self.assertEqual(harness.successes, [b"response"])
        self.assertEqual(harness.failures, [])

    def test_timeout_is_single_shot_aborts_and_reports_once(self) -> None:
        harness = TransportHarness(FakeReply())
        harness.start()

        self.assertTrue(harness.timer.single_shot)
        self.assertEqual(harness.timer.interval, REQUEST_TIMEOUT_MS)
        harness.timer.fire()
        harness.reply.finish()
        harness.timer.fire()

        self.assertTrue(harness.reply.aborted)
        self.assertEqual(len(harness.failures), 1)
        self.assertIsInstance(harness.failures[0], TimeoutFailure)
        self.assertEqual(harness.successes, [])

    def test_manual_cancellation_suppresses_racing_completion(self) -> None:
        harness = TransportHarness(FakeReply())
        handle = harness.start()

        handle.cancel()
        harness.reply.finish()
        harness.timer.fire()
        handle.cancel()

        self.assertTrue(harness.reply.aborted)
        self.assertEqual(harness.successes, [])
        self.assertEqual(harness.failures, [])

    def test_every_completion_path_stops_disconnects_and_disposes(self) -> None:
        for action in ("success", "failure", "timeout", "cancel"):
            with self.subTest(action=action):
                reply = FakeReply(status=500 if action == "failure" else 200)
                harness = TransportHarness(reply)
                handle = harness.start()

                if action in ("success", "failure"):
                    reply.finish()
                elif action == "timeout":
                    harness.timer.fire()
                else:
                    handle.cancel()

                self.assertFalse(harness.timer.running)
                self.assertEqual(harness.timer.timeout.callbacks, [])
                self.assertEqual(reply.finished.callbacks, [])
                self.assertTrue(harness.timer.deleted)
                self.assertTrue(reply.deleted)

    def test_success_callback_occurs_once_even_for_late_signals(self) -> None:
        harness = TransportHarness(FakeReply(body=b"complete"))
        harness.start()

        harness.reply.finish()
        harness.reply.finish()
        harness.timer.fire()

        self.assertEqual(harness.successes, [b"complete"])
        self.assertEqual(harness.failures, [])


if __name__ == "__main__":
    unittest.main()
