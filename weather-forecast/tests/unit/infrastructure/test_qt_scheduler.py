from __future__ import annotations

import sys
import unittest
from datetime import timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from weather_forecast.application.ports import RefreshScheduler, TimerHandle  # noqa: E402
from weather_forecast.infrastructure.qt_scheduler import QtRefreshScheduler  # noqa: E402


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
        self.interval_ms = None
        self.running = False
        self.deleted = False

    def setSingleShot(self, value: bool) -> None:
        self.single_shot = value

    def start(self, interval_ms: int) -> None:
        self.interval_ms = interval_ms
        self.running = True

    def stop(self) -> None:
        self.running = False

    def deleteLater(self) -> None:
        self.deleted = True

    def fire(self) -> None:
        self.timeout.emit()


class TimerFactory:
    def __init__(self) -> None:
        self.timers = []

    def __call__(self) -> FakeTimer:
        timer = FakeTimer()
        self.timers.append(timer)
        return timer


class QtRefreshSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = TimerFactory()
        self.scheduler = QtRefreshScheduler(timer_factory=self.factory)

    def test_callback_fires_once_after_requested_delay_and_cleans_up(self) -> None:
        calls = []

        handle = self.scheduler.schedule_once(
            timedelta(minutes=15),
            lambda: calls.append("fired"),
        )
        timer = self.factory.timers[0]

        self.assertIsInstance(self.scheduler, RefreshScheduler)
        self.assertIsInstance(handle, TimerHandle)
        self.assertTrue(timer.single_shot)
        self.assertEqual(timer.interval_ms, 900_000)
        self.assertEqual(calls, [])

        timer.fire()
        timer.fire()

        self.assertEqual(calls, ["fired"])
        self.assertFalse(timer.running)
        self.assertEqual(timer.timeout.callbacks, [])
        self.assertTrue(timer.deleted)

    def test_cancellation_prevents_firing_and_cleans_up_idempotently(self) -> None:
        calls = []
        handle = self.scheduler.schedule_once(
            timedelta(seconds=10),
            lambda: calls.append("fired"),
        )
        timer = self.factory.timers[0]

        self.scheduler.cancel(handle)
        self.scheduler.cancel(handle)
        timer.fire()

        self.assertEqual(calls, [])
        self.assertFalse(timer.running)
        self.assertEqual(timer.timeout.callbacks, [])
        self.assertTrue(timer.deleted)

    def test_scheduler_adds_no_repetition_or_concurrency_policy(self) -> None:
        calls = []
        first = self.scheduler.schedule_once(
            timedelta(seconds=1), lambda: calls.append("first")
        )
        second = self.scheduler.schedule_once(
            timedelta(seconds=2), lambda: calls.append("second")
        )

        self.assertIsNot(first, second)
        self.assertEqual(len(self.factory.timers), 2)
        self.assertTrue(all(timer.single_shot for timer in self.factory.timers))
        self.factory.timers[1].fire()
        self.factory.timers[0].fire()
        self.factory.timers[0].fire()

        self.assertEqual(calls, ["second", "first"])
        self.assertEqual(len(self.factory.timers), 2)


if __name__ == "__main__":
    unittest.main()
