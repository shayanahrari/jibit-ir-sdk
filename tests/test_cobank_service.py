"""Cobank settlement validation, auth isolation, safety, and model tests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import UUID

import pytest

from jibit import JibitClient
from jibit.engine import RequestOptions
from jibit.exceptions import JibitTimeoutError, JibitValidationError
from jibit.response import RawResponse
from jibit.retry import OperationSafety
from jibit.services.cobank import CobankService
from jibit.transport import TransportTimeoutError
from tests.helpers import FakeTransport, response

TRACK_ID = "123e4567-e89b-12d3-a456-426614174000"


class StubExecutor:
    """Return deterministic Cobank responses and capture operation options."""

    def __init__(self, outcomes: Sequence[RawResponse]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RawResponse:
        """Record and resolve one request."""
        self.requests.append(options)
        return self.outcomes.pop(0)


def raw(value: object) -> RawResponse:
    """Create one Cobank JSON response."""
    return RawResponse(200, {}, json.dumps(value).encode(), "cid-cobank")


def test_root_client_uses_cobank_auth_scope_separately() -> None:
    """Cobank token paths and service configuration do not reuse Transferor scope."""
    transport = FakeTransport(
        [
            response(content=b'{"accessToken":"access","refreshToken":"refresh"}'),
            response(content=b"[]"),
        ]
    )
    client = JibitClient.from_config(
        {"cobank": {"api_key": "key", "secret_key": "secret", "scopes": ["SETTLEMENT"]}},
        transport=transport,
    )

    result = client.cobank.get_merchant_accounts()

    assert result.data.root == []
    assert transport.requests[0].url.endswith("/cobank/v1/tokens/generate")
    assert transport.requests[0].json["scopes"] == ["SETTLEMENT"]
    assert transport.requests[1].url.endswith("/cobank/v1/accounts/")


def test_settlement_timeout_is_not_retried_and_is_reconcilable() -> None:
    """An uncertain Cobank settlement raises once with its operation context."""
    transport = FakeTransport(
        [
            response(content=b'{"accessToken":"access","refreshToken":"refresh"}'),
            TransportTimeoutError("uncertain"),
        ]
    )
    client = JibitClient.from_config(
        {"cobank": {"api_key": "key", "secret_key": "secret"}},
        transport=transport,
    )

    with pytest.raises(JibitTimeoutError) as captured:
        client.cobank.create_settlement(
            record_track_id=TRACK_ID,
            destination_iban="IR000000000000000000000000",
            amount=100,
            transfer_type="ACH",
        )

    assert len(transport.requests) == 2
    assert captured.value.context.operation == "create_settlement"
    assert transport.requests[1].json["recordTrackId"] == TRACK_ID


def test_cobank_submission_and_inquiry_contracts_are_typed() -> None:
    """Creation and reconciliation use the documented paths, payload, and safety."""
    executor = StubExecutor(
        [
            raw({"referenceNumber": "ref", "trackId": TRACK_ID, "records": []}),
            raw({"referenceNumber": "ref", "trackId": TRACK_ID, "records": []}),
            raw([{"referenceNumber": "ref", "trackId": TRACK_ID, "records": []}]),
        ]
    )
    service = CobankService(executor)

    created = service.create_settlement(
        record_track_id=UUID(TRACK_ID),
        destination_iban="IR000000000000000000000000",
        amount=100,
        transfer_reason="KHARID_KALA",
    )
    inquiry = service.inquire_settlement(TRACK_ID, show_archive=True)
    batch = service.batch_inquire_settlements([TRACK_ID])

    assert created.data.reference_number == "ref"
    assert inquiry.data.track_id == TRACK_ID
    assert batch.data.root[0].reference_number == "ref"
    assert executor.requests[0].safety is OperationSafety.UNSAFE
    assert executor.requests[1].safety is OperationSafety.READ_ONLY
    assert executor.requests[2].safety is OperationSafety.IDEMPOTENT


def test_lists_receipts_and_invalid_values() -> None:
    """Cobank list and receipt APIs are typed and validate local contract inputs."""
    executor = StubExecutor(
        [
            raw({"pageNumber": 0, "size": 50, "numberOfElements": 0, "elements": []}),
            raw({"receiptLink": "https://example.com/r", "state": "ACTIVE"}),
            raw({"receiptLink": None, "state": "INACTIVE"}),
        ]
    )
    service = CobankService(executor)

    assert service.list_settlements().data.elements == []
    assert service.set_settlement_receipt("settlement-ref", active=True).data.state == "ACTIVE"
    assert (
        service.set_record_receipt("settlement-ref", "record-ref", active=False).data.state
        == "INACTIVE"
    )
    assert executor.requests[1].safety is OperationSafety.IDEMPOTENT

    with pytest.raises(JibitValidationError):
        service.list_settlements(page_number=-1)
    with pytest.raises(JibitValidationError):
        service.inquire_settlement("invalid-uuid")
    with pytest.raises(JibitValidationError):
        service.create_settlement(
            record_track_id=TRACK_ID,
            destination_iban="bad",
            amount=0,
        )
