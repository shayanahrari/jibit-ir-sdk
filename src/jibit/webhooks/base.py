"""Framework-independent callback parsing and extension interfaces."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from jibit.exceptions import ErrorContext, JibitWebhookVerificationError
from jibit.logging import EventName, StructuredLogger

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class CallbackVerifier(Protocol):
    """Verify callback authenticity using an application-supplied mechanism."""

    def __call__(self, raw_body: bytes, headers: Mapping[str, str]) -> bool:
        """Return true only when the callback passes the configured trust mechanism."""


class DeduplicationStore(Protocol):
    """Claim a callback key atomically for idempotent application processing."""

    def claim(self, key: str) -> bool:
        """Return true for the first accepted key and false for duplicates."""


@dataclass(frozen=True, slots=True, repr=False)
class ParsedCallback(Generic[PayloadT]):
    """Contain validated callback data and explicit trust/deduplication state."""

    payload: PayloadT
    verified: bool
    duplicate: bool

    def __repr__(self) -> str:
        return (
            f"ParsedCallback(payload=[REDACTED], verified={self.verified}, "
            f"duplicate={self.duplicate})"
        )


def parse_callback(
    payload: Mapping[str, Any],
    model: type[PayloadT],
    *,
    service: str,
    raw_body: bytes,
    headers: Mapping[str, str],
    verifier: CallbackVerifier | None,
    deduplication_store: DeduplicationStore | None = None,
    deduplication_key: Callable[[PayloadT], str] | None = None,
    logger: StructuredLogger | None = None,
    correlation_id: str | None = None,
) -> ParsedCallback[PayloadT]:
    """Validate, explicitly verify, and optionally deduplicate untrusted callback data."""
    correlation_id = correlation_id or str(uuid.uuid4())
    if logger is not None:
        logger.emit(
            logging.INFO,
            EventName.WEBHOOK_RECEIVED,
            service=service,
            correlation_id=correlation_id,
        )
    try:
        parsed = model.model_validate(payload)
    except ValidationError:
        _log_rejection(logger, service, correlation_id, "invalid_payload")
        raise JibitWebhookVerificationError(
            "The callback payload is invalid",
            context=ErrorContext(
                service=service,
                operation="parse_callback",
                correlation_id=correlation_id,
            ),
        ) from None
    try:
        verified = verifier is not None and verifier(raw_body, headers)
    except Exception:
        verified = False
    if not verified:
        _log_rejection(logger, service, correlation_id, "authenticity_rejected")
        raise JibitWebhookVerificationError(
            "The callback authenticity could not be verified",
            context=ErrorContext(
                service=service,
                operation="verify_callback",
                correlation_id=correlation_id,
            ),
        )
    duplicate = False
    if deduplication_store is not None:
        if deduplication_key is None:
            _log_rejection(logger, service, correlation_id, "deduplication_misconfigured")
            raise JibitWebhookVerificationError(
                "A deduplication key function is required",
                context=ErrorContext(
                    service=service,
                    operation="deduplicate_callback",
                    correlation_id=correlation_id,
                ),
            )
        try:
            key = deduplication_key(parsed)
            duplicate = not deduplication_store.claim(key)
        except Exception:
            _log_rejection(logger, service, correlation_id, "deduplication_failed")
            raise JibitWebhookVerificationError(
                "The callback deduplication check failed",
                context=ErrorContext(
                    service=service,
                    operation="deduplicate_callback",
                    correlation_id=correlation_id,
                ),
            ) from None
    return ParsedCallback(payload=parsed, verified=True, duplicate=duplicate)


def _log_rejection(
    logger: StructuredLogger | None,
    service: str,
    correlation_id: str,
    reason: str,
) -> None:
    if logger is not None:
        logger.emit(
            logging.WARNING,
            EventName.WEBHOOK_REJECTED,
            service=service,
            correlation_id=correlation_id,
            reason=reason,
        )
