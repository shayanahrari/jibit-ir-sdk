"""Structured logging and audit-event tests."""

import logging

from jibit.logging import AuditEvent, NullAuditSink, StructuredLogger


def test_structured_logger_emits_redacted_fields(caplog: object) -> None:
    """Application handlers receive stable event names and redacted metadata."""
    logger = logging.getLogger("tests.jibit")
    structured = StructuredLogger(logger)

    with caplog.at_level(logging.INFO, logger="tests.jibit"):  # type: ignore[attr-defined]
        structured.emit(
            logging.INFO,
            "jibit.request.completed",
            correlation_id="cid",
            access_token="secret-token",
        )

    record = caplog.records[0]  # type: ignore[attr-defined]
    assert record.event == "jibit.request.completed"
    assert record.jibit["correlation_id"] == "cid"
    assert record.jibit["access_token"] == "[REDACTED]"


def test_disabled_logger_and_null_audit_sink_are_noops(caplog: object) -> None:
    """Disabled diagnostics do not emit records or require persistence."""
    structured = StructuredLogger(logging.getLogger("tests.disabled"), enabled=False)
    structured.emit(logging.ERROR, "jibit.request.failed", password="secret")
    NullAuditSink().emit(
        AuditEvent("payment.created", "cid", "payment_gateway", "create", "success")
    )
    assert not caplog.records  # type: ignore[attr-defined]


def test_audit_event_is_redacted_before_persistence() -> None:
    """Audit metadata follows the same deny-by-default redaction policy."""
    event = AuditEvent(
        "identity.checked",
        "cid",
        "identicator",
        "identity",
        "success",
        {"national_id": "0013547891", "provider_status": "matched"},
    )

    assert event.safe_dict()["metadata"] == {
        "national_id": "[REDACTED]",
        "provider_status": "matched",
    }
