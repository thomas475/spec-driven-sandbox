"""Shared signal-driven Qt HTTP transport."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from weather_forecast.application.ports import RequestHandle
from weather_forecast.domain.failures import (
    ConnectionFailure,
    HttpFailure,
    ServiceFailure,
    TimeoutFailure,
)


REQUEST_TIMEOUT_MS = 30_000
_DEFAULT = object()
_LOGGER = logging.getLogger(__name__)


class QtNetworkTransport:
    """Issue asynchronous GET requests through one supplied Qt network manager."""

    def __init__(
        self,
        network_manager: Any,
        *,
        timer_factory: Callable[[], Any] | None = None,
        request_factory: Callable[[str], Any] | None = None,
        status_attribute: Any = _DEFAULT,
    ) -> None:
        self._network_manager = network_manager
        self._timer_factory = timer_factory or self._default_timer_factory
        self._request_factory = request_factory or self._default_request_factory
        self._status_attribute = status_attribute

    def get(
        self,
        url: str,
        on_success: Callable[[bytes], None],
        on_failure: Callable[[ServiceFailure], None],
    ) -> RequestHandle:
        """Start a GET and return immediately with a cancellable handle."""
        request = self._request_factory(url)
        reply = self._network_manager.get(request)
        timer = self._timer_factory()
        handle = _QtNetworkRequest(
            reply,
            timer,
            on_success,
            on_failure,
            self._resolved_status_attribute(),
        )
        handle.start()
        return handle

    def _default_timer_factory(self) -> Any:
        from PySide6.QtCore import QTimer

        return QTimer(self._network_manager)

    @staticmethod
    def _default_request_factory(url: str) -> Any:
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkRequest

        return QNetworkRequest(QUrl(url))

    def _resolved_status_attribute(self) -> Any:
        if self._status_attribute is not _DEFAULT:
            return self._status_attribute
        from PySide6.QtNetwork import QNetworkRequest

        return QNetworkRequest.Attribute.HttpStatusCodeAttribute


class _QtNetworkRequest:
    """Exactly-once lifecycle for one reply and its timeout timer."""

    def __init__(
        self,
        reply: Any,
        timer: Any,
        on_success: Callable[[bytes], None],
        on_failure: Callable[[ServiceFailure], None],
        status_attribute: Any,
    ) -> None:
        self._reply = reply
        self._timer = timer
        self._on_success = on_success
        self._on_failure = on_failure
        self._status_attribute = status_attribute
        self._complete = False

    def start(self) -> None:
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._timed_out)
        self._reply.finished.connect(self._finished)
        self._timer.start(REQUEST_TIMEOUT_MS)

    def cancel(self) -> None:
        if not self._claim_completion():
            return
        self._reply.abort()
        self._cleanup()

    def _timed_out(self) -> None:
        if not self._claim_completion():
            return
        self._reply.abort()
        failure = TimeoutFailure()
        self._cleanup()
        self._report_failure(failure)

    def _finished(self) -> None:
        if not self._claim_completion():
            return

        try:
            failure = self._classify_failure()
            body = None if failure is not None else bytes(self._reply.readAll())
        except Exception:
            failure = ConnectionFailure()
            body = None

        self._cleanup()
        if failure is not None:
            self._report_failure(failure)
        else:
            self._on_success(body if body is not None else b"")

    def _claim_completion(self) -> bool:
        if self._complete:
            return False
        self._complete = True
        return True

    def _classify_failure(self) -> ServiceFailure | None:
        status = self._reply.attribute(self._status_attribute)
        if status is not None:
            try:
                status_code = _integer_value(status)
            except (TypeError, ValueError):
                return HttpFailure()
            if not 200 <= status_code < 300:
                return HttpFailure()

        try:
            network_error = _integer_value(self._reply.error())
        except (TypeError, ValueError):
            return ConnectionFailure()
        if network_error != 0:
            return ConnectionFailure()
        if status is None:
            return HttpFailure()
        return None

    def _report_failure(self, failure: ServiceFailure) -> None:
        _LOGGER.debug("Qt network request failed: %s", type(failure).__name__)
        self._on_failure(failure)

    def _cleanup(self) -> None:
        self._timer.stop()
        _disconnect(self._timer.timeout, self._timed_out)
        _disconnect(self._reply.finished, self._finished)
        self._timer.deleteLater()
        self._reply.deleteLater()


def _disconnect(signal: Any, callback: Callable[[], None]) -> None:
    try:
        signal.disconnect(callback)
    except (RuntimeError, TypeError):
        pass


def _integer_value(value: Any) -> int:
    """Read either a plain Qt value or a PySide enum value as an integer."""
    return int(getattr(value, "value", value))
