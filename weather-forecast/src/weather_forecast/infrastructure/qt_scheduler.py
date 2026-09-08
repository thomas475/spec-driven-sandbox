"""Qt implementation of the framework-neutral one-shot scheduler port."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from weather_forecast.application.ports import TimerHandle


class QtRefreshScheduler:
    """Create independently cancellable single-shot Qt timers."""

    def __init__(
        self,
        parent: Any = None,
        *,
        timer_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._parent = parent
        self._timer_factory = timer_factory or self._default_timer_factory

    def schedule_once(
        self,
        delay: timedelta,
        callback: Callable[[], None],
    ) -> TimerHandle:
        if not isinstance(delay, timedelta):
            raise TypeError("delay must be a timedelta")
        if delay < timedelta(0):
            raise ValueError("delay must not be negative")

        timer = self._timer_factory()
        handle = _QtTimerHandle(timer, callback)
        handle.start(_milliseconds(delay))
        return handle

    def cancel(self, handle: TimerHandle) -> None:
        if not isinstance(handle, _QtTimerHandle):
            raise TypeError("handle was not created by this scheduler")
        handle.cancel()

    def _default_timer_factory(self) -> Any:
        from PySide6.QtCore import QTimer

        return QTimer(self._parent)


class _QtTimerHandle:
    def __init__(self, timer: Any, callback: Callable[[], None]) -> None:
        self._timer = timer
        self._callback = callback
        self._complete = False

    def start(self, delay_ms: int) -> None:
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fire)
        self._timer.start(delay_ms)

    def cancel(self) -> None:
        if not self._claim_completion():
            return
        self._cleanup()

    def _fire(self) -> None:
        if not self._claim_completion():
            return
        self._cleanup()
        self._callback()

    def _claim_completion(self) -> bool:
        if self._complete:
            return False
        self._complete = True
        return True

    def _cleanup(self) -> None:
        self._timer.stop()
        try:
            self._timer.timeout.disconnect(self._fire)
        except (RuntimeError, TypeError):
            pass
        self._timer.deleteLater()


def _milliseconds(delay: timedelta) -> int:
    return delay // timedelta(milliseconds=1)
