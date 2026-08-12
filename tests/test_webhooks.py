"""Callback validation, explicit verification, and deduplication tests."""

from __future__ import annotations

import pytest

from jibit.exceptions import JibitWebhookVerificationError
from jibit.services.direct_debit import BlueBankCallback
from jibit.webhooks import PaymentCallback, parse_callback


class MemoryDeduplicationStore:
    """Atomically model first-use callback keys for tests."""

    def __init__(self) -> None:
        self.keys: set[str] = set()

    def claim(self, key: str) -> bool:
        """Claim a key once."""
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


def test_callback_requires_explicit_verification() -> None:
    """Reaching a callback route never establishes authenticity by itself."""
    with pytest.raises(JibitWebhookVerificationError):
        parse_callback(
            {"purchaseId": 1},
            PaymentCallback,
            service="payment_gateway",
            raw_body=b'{"purchaseId":1}',
            headers={},
            verifier=None,
        )


def test_payment_callback_parses_and_deduplicates_after_verification() -> None:
    """Verified callback identifiers can use an application-owned idempotency store."""
    store = MemoryDeduplicationStore()
    values = {"purchaseId": 1, "clientReferenceNumber": "order-1"}
    first = parse_callback(
        values,
        PaymentCallback,
        service="payment_gateway",
        raw_body=b"opaque",
        headers={"X-Signature": "test"},
        verifier=lambda body, headers: body == b"opaque" and bool(headers),
        deduplication_store=store,
        deduplication_key=lambda payload: str(payload.purchase_id),
    )
    second = parse_callback(
        values,
        PaymentCallback,
        service="payment_gateway",
        raw_body=b"opaque",
        headers={"X-Signature": "test"},
        verifier=lambda body, headers: body == b"opaque" and bool(headers),
        deduplication_store=store,
        deduplication_key=lambda payload: str(payload.purchase_id),
    )

    assert first.verified is True
    assert first.duplicate is False
    assert second.duplicate is True
    assert "order-1" not in repr(first)


def test_direct_debit_callback_is_typed_but_not_implicitly_trusted() -> None:
    """Blue Bank callback parsing enforces shape and the supplied verifier."""
    result = parse_callback(
        {
            "requestId": "request",
            "additionalInformation": "information",
            "eventType": "event",
            "mandateNumber": "mandate",
            "mandateStatus": "SIGNED",
            "eventCategory": "MANDATE",
        },
        BlueBankCallback,
        service="direct_debit",
        raw_body=b"opaque",
        headers={},
        verifier=lambda body, headers: body == b"opaque",
    )

    assert result.payload.mandate_status == "SIGNED"

    with pytest.raises(JibitWebhookVerificationError):
        parse_callback(
            {},
            BlueBankCallback,
            service="direct_debit",
            raw_body=b"",
            headers={},
            verifier=lambda body, headers: True,
        )


def test_callback_deduplication_failure_is_fail_closed() -> None:
    """Storage failures never permit untracked callback processing."""

    class FailingStore:
        def claim(self, key: str) -> bool:
            raise RuntimeError("storage unavailable")

    with pytest.raises(JibitWebhookVerificationError) as captured:
        parse_callback(
            {"purchaseId": 1, "futureProviderField": "accepted"},
            PaymentCallback,
            service="payment_gateway",
            raw_body=b"opaque",
            headers={},
            verifier=lambda body, headers: True,
            deduplication_store=FailingStore(),
            deduplication_key=lambda payload: str(payload.purchase_id),
        )

    assert captured.value.context.operation == "deduplicate_callback"
