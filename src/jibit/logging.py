"""Structured operational logging and separate audit-event interfaces."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from jibit.redaction import redact


class EventName:
    """Stable English event names emitted by the SDK."""

    REQUEST_STARTED = "jibit.request.started"
    REQUEST_COMPLETED = "jibit.request.completed"
    REQUEST_FAILED = "jibit.request.failed"
    RETRY_SCHEDULED = "jibit.request.retry_scheduled"
    TOKEN_ACQUIRED = "jibit.token.acquired"  # noqa: S105
    TOKEN_REFRESHED = "jibit.token.refreshed"  # noqa: S105
    TOKEN_REFRESH_FAILED = "jibit.token.refresh_failed"  # noqa: S105
    AUDIT_EMIT_FAILED = "jibit.audit.emit_failed"
    WEBHOOK_RECEIVED = "jibit.webhook.received"
    WEBHOOK_REJECTED = "jibit.webhook.rejected"


class StructuredLogger:
    """Emit structured records through application-owned logging handlers."""

    def __init__(self, logger: logging.Logger, *, enabled: bool = True) -> None:
        self._logger = logger
        self._enabled = enabled

    def emit(self, level: int, event: str, **fields: Any) -> None:
        """Emit one redacted event without configuring global logging state."""
        if not self._enabled:
            return
        safe_fields = redact(fields)
        self._logger.log(level, event, extra={"event": event, "jibit": safe_fields})


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Represent an application-owned audit event without persistence behavior."""

    name: str
    correlation_id: str
    service: str
    operation: str
    outcome: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Redact metadata before it reaches an application-owned audit sink."""
        object.__setattr__(self, "metadata", cast(Mapping[str, Any], redact(self.metadata)))

    def safe_dict(self) -> dict[str, Any]:
        """Return a redacted representation suitable for an audit sink."""
        return cast(
            dict[str, Any],
            redact(
                {
                    "name": self.name,
                    "correlation_id": self.correlation_id,
                    "service": self.service,
                    "operation": self.operation,
                    "outcome": self.outcome,
                    "metadata": self.metadata,
                }
            ),
        )


class AuditSink(Protocol):
    """Receive redacted audit events for application-controlled persistence."""

    def emit(self, event: AuditEvent) -> None:
        """Handle an audit event; implementations should not raise exceptions."""


class NullAuditSink:
    """Discard audit events when the application has not configured a sink."""

    def emit(self, event: AuditEvent) -> None:
        """Discard an event intentionally."""


def get_structured_logger(name: str, *, enabled: bool = True) -> StructuredLogger:
    """Wrap an application-visible standard-library logger."""
    return StructuredLogger(logging.getLogger(name), enabled=enabled)
