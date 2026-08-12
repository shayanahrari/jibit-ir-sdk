"""Transferor models, safety classification, auth, and reconciliation tests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone

import pytest

from jibit import JibitClient
from jibit.engine import RequestOptions
from jibit.exceptions import JibitTimeoutError, JibitValidationError
from jibit.logging import AuditEvent
from jibit.response import RawResponse
from jibit.retry import OperationSafety
from jibit.services.transfer import TransferItemRequest, TransferService
from jibit.transport import TransportTimeoutError
from tests.helpers import FakeTransport, response


class StubExecutor:
    """Return deterministic Transferor responses and record request contracts."""

    def __init__(self, outcomes: Sequence[RawResponse]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RawResponse:
        """Record and resolve one request."""
        self.requests.append(options)
        return self.outcomes.pop(0)


class CollectingAuditSink:
    """Collect data-minimized transfer audit events."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        """Store one redacted event."""
        self.events.append(event)


def raw(value: object, *, status: int = 200) -> RawResponse:
    """Create one JSON response."""
    return RawResponse(status, {}, json.dumps(value).encode(), "cid-transfer")


def test_root_client_uses_transferor_v2_auth_and_emits_safe_audit() -> None:
    """Transferor credentials, path prefix, bearer token, and audit scope stay isolated."""
    transport = FakeTransport(
        [
            response(content=b'{"accessToken":"access","refreshToken":"refresh"}'),
            response(content=b'{"balance":100,"settleableBalance":80,"balances":[]}'),
        ]
    )
    audit = CollectingAuditSink()
    client = JibitClient.from_config(
        {"transfers": {"api_key": "key", "secret_key": "secret"}},
        transport=transport,
        audit_sink=audit,
    )

    result = client.transfers.get_balances()

    assert result.data.settleable_balance == 80
    assert transport.requests[0].url.endswith("/trf/v2/tokens/generate")
    assert transport.requests[1].url.endswith("/trf/v2/balances")
    assert transport.requests[1].headers["Authorization"] == "Bearer access"
    assert audit.events[0].name == "jibit.transfer.operation"


def test_submit_batch_has_no_automatic_retry_and_preserves_reconciliation_key() -> None:
    """A timeout on financial submission never causes a duplicate transport call."""
    transport = FakeTransport(
        [
            response(content=b'{"accessToken":"access","refreshToken":"refresh"}'),
            TransportTimeoutError("uncertain"),
        ]
    )
    client = JibitClient.from_config(
        {"transfers": {"api_key": "key", "secret_key": "secret"}},
        transport=transport,
    )

    with pytest.raises(JibitTimeoutError) as captured:
        client.transfers.submit_batch(
            batch_id="batch-unique-1",
            transfers=[
                {
                    "transfer_id": "transfer-unique-1",
                    "destination": "IR000000000000000000000000",
                    "amount": 100_000,
                    "description": "invoice settlement",
                }
            ],
        )

    assert len(transport.requests) == 2
    assert captured.value.context.operation == "submit_batch"
    request = transport.requests[1]
    assert request.json["batchID"] == "batch-unique-1"
    assert request.json["transfers"][0]["transferID"] == "transfer-unique-1"


def test_inquiry_cancel_and_retry_require_reference_and_use_correct_safety() -> None:
    """Reconciliation is retryable while explicit financial actions are status-only."""
    executor = StubExecutor([raw({"batchID": "batch-1", "transfers": []}), raw(None), raw(None)])
    service = TransferService(executor)

    inquiry = service.inquire(batch_id="batch-1")
    cancelled = service.cancel(transfer_id="transfer-1")
    retried = service.retry_failed(batch_id="batch-1", transfer_id="transfer-1")

    assert inquiry.data.batch_id == "batch-1"
    assert cancelled.data.success is True
    assert retried.data.raw_body == b"null"
    assert [request.safety for request in executor.requests] == [
        OperationSafety.READ_ONLY,
        OperationSafety.UNSAFE,
        OperationSafety.UNSAFE,
    ]
    assert executor.requests[2].json == {"state": "RETRY"}

    with pytest.raises(JibitValidationError):
        service.inquire()


def test_filter_reports_banks_receipts_and_generator_are_typed() -> None:
    """Read helpers validate inputs and preserve typed provider results."""
    executor = StubExecutor(
        [
            raw([{"transferID": "transfer-1", "state": "TRANSFERRED"}]),
            raw({"report": [{"state": "TRANSFERRED", "currency": "IRR", "sum": 10, "count": 1}]}),
            raw(["BKMTIR"]),
            raw(["BKMTIR"]),
            raw({"publicLink": "https://example.com/receipt"}),
            raw(
                {
                    "batchID": "generated",
                    "submissionMode": "BATCH",
                    "transfers": [
                        {
                            "transferID": "generated-1",
                            "destination": "IR000000000000000000000000",
                            "amount": 1,
                            "description": "generated",
                        }
                    ],
                }
            ),
        ]
    )
    service = TransferService(executor)

    assert service.filter_transfers().data.transfers[0].state == "TRANSFERRED"
    assert service.get_daily_usage_report("000708").data.report[0].count == 1
    assert service.get_supported_normal_banks().data.root == ["BKMTIR"]
    assert service.get_active_normal_banks().data.root == ["BKMTIR"]
    assert service.set_receipt_enabled(enabled=True, batch_id="batch").data.public_link
    assert executor.requests[4].json["newEnablementStatus"] == "true"
    assert executor.requests[4].safety is OperationSafety.UNSAFE
    assert (
        service.generate_batch(
            transfer_mode="ACH",
            destination="IR000000000000000000000000",
            amount=1,
        ).data.batch_id
        == "generated"
    )

    with pytest.raises(JibitValidationError):
        service.filter_transfers(page=0)
    with pytest.raises(JibitValidationError):
        service.filter_transfers(state="NOT_A_STATE")
    with pytest.raises(JibitValidationError):
        service.filter_transfers(
            from_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
            to_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    with pytest.raises(JibitValidationError):
        service.get_daily_usage_report("invalid")


def test_transfer_request_repr_hides_financial_data() -> None:
    """Request-model diagnostics never expose identifiers or destinations."""
    request = TransferItemRequest(
        transfer_id="private-transfer",
        destination="IR000000000000000000000000",
        amount=100,
        description="private description",
    )

    assert "private-transfer" not in repr(request)
    assert "IR000000000000000000000000" not in repr(request)
