"""Direct Debit mandate, collection, status-only, auth, and safety tests."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from jibit import JibitClient
from jibit.engine import RequestOptions
from jibit.exceptions import JibitTimeoutError, JibitValidationError
from jibit.response import RawResponse
from jibit.retry import OperationSafety
from jibit.services.direct_debit import DirectDebitService
from jibit.transport import TransportTimeoutError
from tests.helpers import FakeTransport, response


class StubExecutor:
    """Capture Direct Debit request contracts with deterministic responses."""

    def __init__(self, outcomes: Sequence[RawResponse]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RawResponse:
        """Record and resolve one request."""
        self.requests.append(options)
        return self.outcomes.pop(0)


def raw(value: object, status: int = 200) -> RawResponse:
    """Create one JSON response."""
    return RawResponse(status, {}, json.dumps(value).encode(), "cid-dd")


def test_root_client_authenticates_direct_debit_and_collection_is_not_retried() -> None:
    """Direct Debit auth is automatic while an uncertain collection is sent once."""
    transport = FakeTransport(
        [
            response(content=b'{"access_token":"access","refresh_token":"refresh"}'),
            TransportTimeoutError("uncertain"),
        ]
    )
    client = JibitClient.from_config(
        {"direct_debit": {"api_key": "key", "secret_key": "secret"}},
        transport=transport,
    )

    with pytest.raises(JibitTimeoutError) as captured:
        client.direct_debit.collect(
            creditor_transaction_no="collection-unique-1",
            mandate_reference="mandate-000001",
            amount=100,
        )

    assert len(transport.requests) == 2
    assert transport.requests[0].url.endswith("/directdebit/api/v1/auth/authenticate")
    assert captured.value.context.operation == "collect"


def test_mandate_types_and_collection_are_typed_and_unsafe() -> None:
    """Mandate-specific validation and collection contracts preserve financial safety."""
    executor = StubExecutor(
        [
            raw({"mandateReference": "mandate", "redirectUrl": "https://example.com"}),
            raw({"transaction_no": "tx", "status": "SUCCESS"}),
        ]
    )
    service = DirectDebitService(executor)

    mandate = service.create_mandate(
        "one-tap",
        creditor_mandate_reference="creditor-00001",
        debtor_bank="BANK",
        maximum_amount=1000,
        period=1,
        period_unit="MONTH",
        start_date="1405-01-01",
        expire_date="1406-01-01",
        frequency=1,
        otp_requirement_status="REQUIRED",
    )
    transaction = service.collect(
        creditor_transaction_no="client-tx",
        mandate_reference="mandate-000001",
        amount=100,
        otp="12345",
    )

    assert mandate.data.mandate_reference == "mandate"
    assert transaction.data.transaction_no == "tx"
    assert all(request.safety is OperationSafety.UNSAFE for request in executor.requests)
    assert "12345" not in repr(executor.requests[1])
    assert executor.requests[0].json["creditor_mandate_reference"] == "creditor-00001"
    assert executor.requests[1].json["creditor_transaction_no"] == "client-tx"

    with pytest.raises(JibitValidationError):
        service.create_mandate(
            "one-tap",
            creditor_mandate_reference="creditor-00001",
            debtor_bank="BANK",
            maximum_amount=100,
            period=1,
            period_unit="MONTH",
            start_date="1405-01-01",
            expire_date="1406-01-01",
            otp_requirement_status="REQUIRED",
        )


def test_five_limited_operations_are_status_only_and_optional_body() -> None:
    """Known response-less operations never infer undocumented success fields."""
    executor = StubExecutor([raw(None), raw({"ignored": True}), raw(None), raw(None), raw(None)])
    service = DirectDebitService(executor)

    results = [
        service.revoke_mandate("mandate-1", revoke_by="merchant"),
        service.enable_mandate("mandate-1", enable_by="merchant"),
        service.disable_mandate("mandate-1", disable_by="merchant"),
        service.send_otp("mandate-1"),
        service.accept_blue_bank_callback(
            {
                "request_id": "request",
                "additional_information": "event",
                "event_type": "event",
                "mandate_number": "mandate-1",
                "mandate_status": "SIGNED",
                "event_category": "MANDATE",
            }
        ),
    ]

    assert all(result.data.success for result in results)
    assert results[1].data.raw_body == b'{"ignored": true}'
    assert all(request.safety is OperationSafety.UNSAFE for request in executor.requests)


def test_direct_debit_inquiries_are_read_only_and_typed() -> None:
    """Transactions, mandates, and active-bank inquiry models are available."""
    executor = StubExecutor(
        [
            raw({"creditor_transaction_no": "tx", "status": "SUCCESS"}),
            raw([]),
            raw({"mandate_reference": "m", "status": "SIGNED"}),
            raw({"creditor_mandate_reference": "c", "status": "SIGNED"}),
            raw([{"name": "BANK", "persianName": "localized"}]),
        ]
    )
    service = DirectDebitService(executor)

    assert service.inquire_transaction("tx-1").data.status == "SUCCESS"
    assert service.list_subscription_transactions("mandate-1").data.root == []
    assert service.inquire_mandate("mandate-1").data.status == "SIGNED"
    assert service.inquire_creditor_mandate("creditor-1").data.status == "SIGNED"
    assert service.get_active_banks().data.root[0].name == "BANK"
    assert all(request.safety is OperationSafety.READ_ONLY for request in executor.requests)

    with pytest.raises(JibitValidationError):
        service.inquire_transaction("bad/reference")
