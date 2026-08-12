"""Payment Gateway request validation and response-model tests."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from jibit.services.payment_gateway import (
    CreatePurchaseRequest,
    PurchaseHistoryFilter,
    PurchaseState,
    RefundInquiryResult,
    TerminalSwitching,
)


def valid_purchase(**changes: object) -> dict[str, object]:
    """Return a valid purchase body with selective overrides."""
    values: dict[str, object] = {
        "amount": 100_000,
        "callback_url": "https://merchant.example/callback",
        "client_reference_number": "order-1",
    }
    values.update(changes)
    return values


def test_purchase_request_serializes_documented_aliases() -> None:
    """Pythonic names serialize to the exact PPG field casing."""
    request = CreatePurchaseRequest.model_validate(
        valid_purchase(
            payer_card_numbers=["6037990000000001", "6037990000000002"],
            switching=TerminalSwitching(terminal_ids=("terminal-1",)),
        )
    )

    assert request.to_payload() == {
        "amount": 100_000,
        "callbackUrl": "https://merchant.example/callback",
        "clientReferenceNumber": "order-1",
        "wage": 0,
        "currency": "IRR",
        "checkPayerMobileNumber": False,
        "payerCardNumbers": ["6037990000000001", "6037990000000002"],
        "switching": {"terminalIds": ["terminal-1"], "autoSwitching": True},
    }
    assert "6037990000000001" not in repr(request)


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": 4_999},
        {"wage": 15_001},
        {"check_payer_mobile_number": True},
        {
            "payer_card_number": "6037990000000001",
            "payer_card_numbers": ["6037990000000002"],
        },
        {"payer_card_numbers": ["6037990000000001", "6037990000000001"]},
    ],
)
def test_purchase_cross_field_constraints_are_enforced(changes: dict[str, object]) -> None:
    """Invalid financial and payer constraints fail before network I/O."""
    with pytest.raises(ValidationError):
        CreatePurchaseRequest.model_validate(valid_purchase(**changes))


def test_history_filter_requires_safe_bounded_criteria() -> None:
    """History filtering rejects empty and overlong time windows."""
    with pytest.raises(ValidationError, match="criterion"):
        PurchaseHistoryFilter()

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="three hours"):
        PurchaseHistoryFilter(from_=start, to=start + timedelta(hours=3))

    criteria = PurchaseHistoryFilter(
        from_=start,
        to=start + timedelta(hours=1),
        statuses=(PurchaseState.UNKNOWN,),
    )
    assert criteria.to_query()["from"] == "2026-01-01T00:00:00Z"


def test_refund_inquiry_handles_documented_irregular_aliases() -> None:
    """Legacy uppercase-ID fields parse without weakening Python naming."""
    result = RefundInquiryResult.model_validate(
        {
            "batchID": "batch-1",
            "refundedAmount": 25_000,
            "transfers": [
                {
                    "refundId": 7,
                    "notifyURL": "https://merchant.example/notify",
                    "transferID": "transfer-1",
                }
            ],
        }
    )

    assert result.batch_id == "batch-1"
    assert result.transfers[0].transfer_id == "transfer-1"
