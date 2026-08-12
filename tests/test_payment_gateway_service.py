"""Payment Gateway service facade, safety, audit, and response tests."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from typing import Any, cast

import pytest

from jibit import JibitClient
from jibit.auth import AuthenticatedRequestEngine
from jibit.engine import RequestOptions
from jibit.exceptions import (
    ErrorContext,
    JibitResponseError,
    JibitTimeoutError,
    JibitValidationError,
)
from jibit.logging import AuditEvent, AuditSink, NullAuditSink, StructuredLogger
from jibit.response import RawResponse
from jibit.retry import OperationSafety
from jibit.services.payment_gateway import (
    PaymentGatewayService,
    PurchaseFilter,
    PurchaseHistoryFilter,
    SettlementFilter,
)
from jibit.transport import TransportResponse, TransportTimeoutError
from tests.helpers import FakeTransport, response


class StubAuthenticatedEngine:
    """Return typed raw outcomes while recording operation safety and contracts."""

    def __init__(self, outcomes: Sequence[RawResponse | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RawResponse:
        """Record and resolve one service request."""
        self.requests.append(options)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class CollectingAuditSink:
    """Collect emitted events for assertions."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        """Store one already-redacted event."""
        self.events.append(event)


class FailingAuditSink:
    """Represent an application audit extension that fails unexpectedly."""

    def emit(self, event: AuditEvent) -> None:
        """Raise to verify financial result isolation."""
        raise RuntimeError("audit storage unavailable")


def raw(value: object, *, status: int = 200, correlation_id: str = "cid-1") -> RawResponse:
    """Create a raw JSON response for a service-level test."""
    content = b"" if value is None else json.dumps(value).encode()
    return RawResponse(status, {}, content, correlation_id)


def service(
    outcomes: Sequence[RawResponse | Exception],
    audit_sink: AuditSink | None = None,
) -> tuple[PaymentGatewayService, StubAuthenticatedEngine]:
    """Build a facade with deterministic dependencies."""
    engine = StubAuthenticatedEngine(outcomes)
    facade = PaymentGatewayService(
        cast(AuthenticatedRequestEngine, engine),
        audit_sink or NullAuditSink(),
        StructuredLogger(logging.getLogger("tests.ppg")),
    )
    return facade, engine


def token_response() -> TransportResponse:
    """Return a documented PPG token response."""
    return response(content=b'{"accessToken":"access","refreshToken":"refresh"}')


def client(transport: FakeTransport) -> JibitClient:
    """Build a real root client around a deterministic transport."""
    return JibitClient.from_config(
        {
            "retry": {"base_delay": 0, "max_delay": 0, "jitter_ratio": 0},
            "payment_gateway": {"api_key": "key", "secret_key": "secret"},
        },
        transport=transport,
    )


def test_root_client_creates_typed_purchase_with_automatic_authentication() -> None:
    """The concise public flow obtains a token and returns typed plus raw data."""
    transport = FakeTransport(
        [
            token_response(),
            response(
                content=(
                    b'{"purchaseId":42,"purchaseIdStr":"42",'
                    b'"clientReferenceNumber":"order-42",'
                    b'"pspSwitchingUrl":"https://napi.jibit.ir/ppg/pay/42",'
                    b'"payableAmount":100000,"currency":"IRR"}'
                )
            ),
        ]
    )

    result = client(transport).payment_gateway.create_purchase(
        amount=100_000,
        callback_url="https://merchant.example/callback",
        client_reference_number="order-42",
    )

    assert result.data.purchase_id == 42
    assert result.raw.correlation_id
    assert transport.requests[0].url.endswith("/ppg/v3/tokens")
    assert transport.requests[1].headers["Authorization"] == "Bearer access"
    assert transport.requests[1].json["clientReferenceNumber"] == "order-42"


def test_uncertain_purchase_submission_is_never_automatically_retried() -> None:
    """A create timeout surfaces for inquiry instead of duplicating a purchase."""
    transport = FakeTransport([token_response(), TransportTimeoutError()])

    with pytest.raises(JibitTimeoutError):
        client(transport).payment_gateway.create_purchase(
            amount=100_000,
            callback_url="https://merchant.example/callback",
            client_reference_number="order-timeout",
        )

    assert len(transport.requests) == 2


def test_idempotent_verification_retries_a_transient_response() -> None:
    """Verification can safely retry because repeated outcomes are documented."""
    transport = FakeTransport(
        [
            token_response(),
            response(503),
            response(content=b'{"status":"SUCCESSFUL"}'),
        ]
    )

    result = client(transport).payment_gateway.verify_purchase(42)

    assert result.data.status.value == "SUCCESSFUL"
    assert len(transport.requests) == 3


def test_create_refund_and_reverse_assign_conservative_safety_and_audit() -> None:
    """Write operations expose explicit safety classifications and safe audit events."""
    audit = CollectingAuditSink()
    facade, engine = service(
        [
            raw({"status": "SUCCESSFUL"}),
            raw({"refundId": 9, "batchId": "batch-9", "transferId": "transfer-9"}),
        ],
        audit,
    )

    facade.reverse_purchase(purchase_id=42)
    facade.refund_purchase(purchase_id=42, amount=25_000)

    assert [request.safety for request in engine.requests] == [
        OperationSafety.IDEMPOTENT,
        OperationSafety.UNSAFE,
    ]
    assert [event.name for event in audit.events] == [
        "jibit.payment.purchase_reversed",
        "jibit.payment.refund_submitted",
    ]


def test_status_only_refund_actions_preserve_optional_body_and_do_not_retry() -> None:
    """All four empty-response refund operations share an explicit result contract."""
    facade, engine = service([raw(None, status=204), raw(None), raw({"accepted": True}), raw(None)])

    results = [
        facade.verify_refund(9),
        facade.retry_refund(9, transfer_id="transfer-1"),
        facade.cancel_refund(9),
        facade.ignore_refund_cancellable_delay(9),
    ]

    assert [result.data.status_code for result in results] == [204, 200, 200, 200]
    assert results[0].data.raw_body is None
    assert results[2].data.raw_body == b'{"accepted": true}'
    assert all(request.safety is OperationSafety.UNSAFE for request in engine.requests)
    assert [request.path.rsplit("/", 1)[-1] for request in engine.requests] == [
        "verify",
        "retry",
        "cancel",
        "ignore-cancellable",
    ]


def test_read_operations_use_documented_paths_and_typed_contracts() -> None:
    """Inquiry, pagination, terminal, balance, and health operations are covered."""
    outcomes = [
        raw(
            {
                "pageNumber": 1,
                "size": 1,
                "numberOfElements": 1,
                "hasNext": False,
                "hasPrevious": False,
                "elements": [{"purchaseId": 42, "state": "SUCCESS"}],
            }
        ),
        raw({"transfers": [], "batchID": "batch-1", "refundedAmount": 0}),
        raw({"elements": [{"naturalId": "terminal-1"}]}),
        raw(
            {
                "pageNumber": 1,
                "size": 1,
                "numberOfElements": 1,
                "hasNext": False,
                "hasPrevious": False,
                "elements": [{"settlementId": 5, "state": "SETTLED"}],
            }
        ),
        raw(
            {
                "size": 1,
                "totalCount": 1,
                "hasNext": False,
                "elements": [
                    {
                        "purchaseId": 42,
                        "newState": "SUCCESS",
                        "createdAt": "2026-01-01T00:00:00Z",
                    }
                ],
            }
        ),
        raw({"balances": [{"balanceType": "STL", "amount": 1000, "currency": "IRR"}]}),
        raw({"status": "UP", "pspStatusMap": {"provider": "UP"}}),
    ]
    facade, engine = service(outcomes)

    purchase = facade.filter_purchases(PurchaseFilter(purchase_id=42, page=1, size=1))
    refund = facade.inquire_refund(9)
    terminals = facade.list_terminals()
    settlements = facade.filter_settlements(SettlementFilter(settlement_id=5))
    histories = facade.filter_purchase_histories(PurchaseHistoryFilter(purchase_id=42))
    balances = facade.get_balances()
    health = facade.health()

    assert purchase.data.elements[0].purchase_id == 42
    assert refund.data.batch_id == "batch-1"
    assert terminals.data.elements[0].natural_id == "terminal-1"
    assert settlements.data.elements[0].settlement_id == 5
    assert histories.data.elements[0].purchase_id == 42
    assert balances.data.balances[0].amount == 1000
    assert health.data.status.value == "UP"
    assert all(request.safety is OperationSafety.READ_ONLY for request in engine.requests)
    assert [request.path for request in engine.requests] == [
        "/ppg/v3/purchases",
        "/ppg/v3/purchases/refunds/9",
        "/ppg/v3/terminals/list",
        "/ppg/v3/settlements",
        "/ppg/v3/purchases/histories",
        "/ppg/v3/balances",
        "/ppg/v3/app/health",
    ]


def test_invalid_local_input_and_upstream_response_raise_sdk_exceptions() -> None:
    """Callers receive stable SDK errors instead of transport or validation internals."""
    facade, engine = service([raw({"clientReferenceNumber": "missing-fields"})])

    with pytest.raises(JibitValidationError) as local_error:
        facade.create_purchase(
            amount=4_999,
            callback_url="https://merchant.example/callback",
            client_reference_number="invalid",
        )
    assert local_error.value.context.operation == "create_purchase"
    assert not engine.requests

    with pytest.raises(JibitResponseError) as response_error:
        facade.create_purchase(
            amount=100_000,
            callback_url="https://merchant.example/callback",
            client_reference_number="order-invalid-response",
        )
    assert response_error.value.context.correlation_id == "cid-1"
    assert response_error.value.__cause__ is None


def test_audit_extension_failure_does_not_hide_success(caplog: object) -> None:
    """Audit storage failures are logged without inviting duplicate financial writes."""
    facade, _ = service([raw({"status": "SUCCESSFUL"})], FailingAuditSink())

    with caplog.at_level(logging.ERROR, logger="tests.ppg"):  # type: ignore[attr-defined]
        result = facade.reverse_purchase(purchase_id=42)

    assert result.data.status.value == "SUCCESSFUL"
    assert caplog.records[-1].event == "jibit.audit.emit_failed"  # type: ignore[attr-defined]


def test_uncertain_financial_failure_emits_unknown_audit_outcome() -> None:
    """A timeout audit never inaccurately claims that the provider rejected a write."""
    audit = CollectingAuditSink()
    facade, _ = service(
        [
            JibitTimeoutError(
                "The request timed out",
                context=ErrorContext(correlation_id="cid-timeout"),
            )
        ],
        audit,
    )

    with pytest.raises(JibitTimeoutError):
        facade.create_purchase(
            amount=100_000,
            callback_url="https://merchant.example/callback",
            client_reference_number="order-timeout-audit",
        )

    assert audit.events[0].outcome == "unknown"
    assert audit.events[0].correlation_id == "cid-timeout"


@pytest.mark.parametrize(
    "operation",
    [
        lambda sdk: sdk.inquire_purchase(),
        lambda sdk: sdk.verify_purchase(0),
        lambda sdk: sdk.refund_purchase(),
        lambda sdk: sdk.verify_refund(0),
    ],
)
def test_high_level_validation_is_consistent(
    operation: Callable[[PaymentGatewayService], Any],
) -> None:
    """All facade validation failures use the public SDK exception hierarchy."""
    facade, engine = service([])
    with pytest.raises(JibitValidationError):
        operation(facade)
    assert not engine.requests
