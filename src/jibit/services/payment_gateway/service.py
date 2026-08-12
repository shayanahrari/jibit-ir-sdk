"""High-level, authentication-aware Payment Gateway v3 operations."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from jibit.auth import AuthenticatedRequestEngine
from jibit.engine import RequestOptions
from jibit.exceptions import (
    ErrorContext,
    JibitError,
    JibitNetworkError,
    JibitResponseError,
    JibitServerError,
    JibitTimeoutError,
    JibitValidationError,
)
from jibit.logging import AuditEvent, AuditSink, EventName, StructuredLogger
from jibit.response import APIResponse, StatusResult
from jibit.retry import OperationSafety
from jibit.services.base import parse_model_response
from jibit.services.payment_gateway.models import (
    ClientBalances,
    CreatePurchaseRequest,
    CreatePurchaseResult,
    HealthResult,
    PurchaseFilter,
    PurchaseHistoryFilter,
    PurchaseHistoryPage,
    PurchasePage,
    RefundActionRequest,
    RefundInquiryResult,
    RefundPurchaseRequest,
    RefundPurchaseResult,
    ReversePurchaseRequest,
    ReversePurchaseResult,
    SettlementFilter,
    SettlementPage,
    TerminalCollection,
    TerminalSwitching,
    VerifyPurchaseResult,
)
from jibit.types import ServiceName

_SERVICE = ServiceName.PAYMENT_GATEWAY
ModelT = TypeVar("ModelT", bound=BaseModel)


class PaymentGatewayService:
    """Expose typed Payment Gateway operations with conservative retry semantics."""

    def __init__(
        self,
        engine: AuthenticatedRequestEngine,
        audit_sink: AuditSink,
        logger: StructuredLogger,
    ) -> None:
        self._engine = engine
        self._audit_sink = audit_sink
        self._logger = logger

    def create_purchase(
        self,
        *,
        amount: int,
        callback_url: str,
        client_reference_number: str,
        wage: int = 0,
        currency: str = "IRR",
        payer_mobile_number: str | None = None,
        check_payer_mobile_number: bool = False,
        payer_card_number: str | None = None,
        payer_card_numbers: Sequence[str] | None = None,
        payer_national_code: str | None = None,
        description: str | None = None,
        switching: TerminalSwitching | Mapping[str, Any] | None = None,
        additional_data: dict[str, Any] | None = None,
        user_identifier: str | None = None,
    ) -> APIResponse[CreatePurchaseResult]:
        """Create a purchase without retrying an uncertain financial submission."""
        request = self._request(
            CreatePurchaseRequest,
            {
                "amount": amount,
                "callback_url": callback_url,
                "client_reference_number": client_reference_number,
                "wage": wage,
                "currency": currency,
                "payer_mobile_number": payer_mobile_number,
                "check_payer_mobile_number": check_payer_mobile_number,
                "payer_card_number": payer_card_number,
                "payer_card_numbers": payer_card_numbers,
                "payer_national_code": payer_national_code,
                "description": description,
                "switching": switching,
                "additional_data": additional_data,
                "user_identifier": user_identifier,
            },
            operation="create_purchase",
            method="POST",
            path="/ppg/v3/purchases",
        )
        result = self._financial_typed(
            audit_name="jibit.payment.purchase_created",
            operation="create_purchase",
            method="POST",
            path="/ppg/v3/purchases",
            safety=OperationSafety.UNSAFE,
            model=CreatePurchaseResult,
            body=request.to_payload(),
        )
        self._audit(
            name="jibit.payment.purchase_created",
            operation="create_purchase",
            result=result,
            metadata={
                "purchase_id": result.data.purchase_id,
                "client_reference_number": result.data.client_reference_number,
            },
        )
        return result

    def filter_purchases(
        self,
        criteria: PurchaseFilter | None = None,
    ) -> APIResponse[PurchasePage]:
        """Filter purchases using validated criteria and bounded pagination."""
        query = (criteria or PurchaseFilter()).to_query()
        return self._typed(
            operation="filter_purchases",
            method="GET",
            path="/ppg/v3/purchases",
            safety=OperationSafety.READ_ONLY,
            model=PurchasePage,
            params=query,
        )

    def inquire_purchase(
        self,
        *,
        purchase_id: int | None = None,
        client_reference_number: str | None = None,
    ) -> APIResponse[PurchasePage]:
        """Reconcile a purchase by its provider or application reference."""
        if purchase_id is None and client_reference_number is None:
            raise self._validation_error(
                "inquire_purchase",
                "GET",
                "/ppg/v3/purchases",
                "purchase_id or client_reference_number is required",
            )
        criteria = self._request(
            PurchaseFilter,
            {
                "purchase_id": purchase_id,
                "client_reference_number": client_reference_number,
                "size": 1,
            },
            operation="inquire_purchase",
            method="GET",
            path="/ppg/v3/purchases",
        )
        return self.filter_purchases(criteria)

    def verify_purchase(self, purchase_id: int) -> APIResponse[VerifyPurchaseResult]:
        """Verify a callback purchase; repeated calls have documented stable outcomes."""
        if purchase_id <= 0:
            raise self._validation_error(
                "verify_purchase",
                "POST",
                f"/ppg/v3/purchases/{purchase_id}/verify",
                "purchase_id must be positive",
            )
        result = self._financial_typed(
            audit_name="jibit.payment.purchase_verified",
            operation="verify_purchase",
            method="POST",
            path=f"/ppg/v3/purchases/{purchase_id}/verify",
            safety=OperationSafety.IDEMPOTENT,
            model=VerifyPurchaseResult,
        )
        self._audit(
            name="jibit.payment.purchase_verified",
            operation="verify_purchase",
            result=result,
            metadata={"purchase_id": purchase_id, "status": result.data.status.value},
        )
        return result

    def reverse_purchase(
        self,
        *,
        purchase_id: int | None = None,
        client_reference_number: str | None = None,
    ) -> APIResponse[ReversePurchaseResult]:
        """Reverse a purchase through the endpoint's repeatable state transition."""
        request = self._request(
            ReversePurchaseRequest,
            {
                "purchase_id": purchase_id,
                "client_reference_number": client_reference_number,
            },
            operation="reverse_purchase",
            method="POST",
            path="/ppg/v3/purchases/reverse",
        )
        result = self._financial_typed(
            audit_name="jibit.payment.purchase_reversed",
            operation="reverse_purchase",
            method="POST",
            path="/ppg/v3/purchases/reverse",
            safety=OperationSafety.IDEMPOTENT,
            model=ReversePurchaseResult,
            body=request.to_payload(),
        )
        self._audit(
            name="jibit.payment.purchase_reversed",
            operation="reverse_purchase",
            result=result,
            metadata={"purchase_id": purchase_id, "status": result.data.status.value},
        )
        return result

    def refund_purchase(
        self,
        *,
        purchase_id: int | None = None,
        client_reference_number: str | None = None,
        amount: int | None = None,
        cancellable: bool = False,
    ) -> APIResponse[RefundPurchaseResult]:
        """Submit a refund once and require inquiry after an uncertain outcome."""
        request = self._request(
            RefundPurchaseRequest,
            {
                "purchase_id": purchase_id,
                "client_reference_number": client_reference_number,
                "amount": amount,
                "cancellable": cancellable,
            },
            operation="refund_purchase",
            method="POST",
            path="/ppg/v3/purchases/refund",
        )
        result = self._financial_typed(
            audit_name="jibit.payment.refund_submitted",
            operation="refund_purchase",
            method="POST",
            path="/ppg/v3/purchases/refund",
            safety=OperationSafety.UNSAFE,
            model=RefundPurchaseResult,
            body=request.to_payload(),
        )
        self._audit(
            name="jibit.payment.refund_submitted",
            operation="refund_purchase",
            result=result,
            metadata={
                "purchase_id": purchase_id,
                "refund_id": result.data.refund_id,
                "batch_id": result.data.batch_id,
                "transfer_id": result.data.transfer_id,
            },
        )
        return result

    def inquire_refund(self, refund_id: int) -> APIResponse[RefundInquiryResult]:
        """Return current refund-transfer state for reconciliation."""
        if refund_id <= 0:
            raise self._validation_error(
                "inquire_refund",
                "GET",
                f"/ppg/v3/purchases/refunds/{refund_id}",
                "refund_id must be positive",
            )
        return self._typed(
            operation="inquire_refund",
            method="GET",
            path=f"/ppg/v3/purchases/refunds/{refund_id}",
            safety=OperationSafety.READ_ONLY,
            model=RefundInquiryResult,
        )

    def verify_refund(
        self,
        refund_id: int,
        *,
        transfer_id: str | None = None,
    ) -> APIResponse[StatusResult]:
        """Verify a pending refund and interpret documented HTTP 204 as success."""
        return self._refund_action("verify_refund", refund_id, "verify", transfer_id)

    def retry_refund(
        self,
        refund_id: int,
        *,
        transfer_id: str | None = None,
    ) -> APIResponse[StatusResult]:
        """Request one retry of a failed refund without automatic network replay."""
        return self._refund_action("retry_refund", refund_id, "retry", transfer_id)

    def cancel_refund(
        self,
        refund_id: int,
        *,
        transfer_id: str | None = None,
    ) -> APIResponse[StatusResult]:
        """Cancel a cancellable refund without assuming a response-body schema."""
        return self._refund_action("cancel_refund", refund_id, "cancel", transfer_id)

    def ignore_refund_cancellable_delay(
        self,
        refund_id: int,
        *,
        transfer_id: str | None = None,
    ) -> APIResponse[StatusResult]:
        """Start a cancellable refund immediately using its status-only contract."""
        return self._refund_action(
            "ignore_refund_cancellable_delay", refund_id, "ignore-cancellable", transfer_id
        )

    def list_terminals(self) -> APIResponse[TerminalCollection]:
        """Return terminals and natural IDs available for purchase switching."""
        return self._typed(
            operation="list_terminals",
            method="GET",
            path="/ppg/v3/terminals/list",
            safety=OperationSafety.READ_ONLY,
            model=TerminalCollection,
        )

    def filter_settlements(
        self,
        criteria: SettlementFilter | None = None,
    ) -> APIResponse[SettlementPage]:
        """Filter PPG settlements using validated page bounds."""
        return self._typed(
            operation="filter_settlements",
            method="GET",
            path="/ppg/v3/settlements",
            safety=OperationSafety.READ_ONLY,
            model=SettlementPage,
            params=(criteria or SettlementFilter()).to_query(),
        )

    def filter_purchase_histories(
        self,
        criteria: PurchaseHistoryFilter,
    ) -> APIResponse[PurchaseHistoryPage]:
        """Return purchase state transitions for explicit, bounded criteria."""
        return self._typed(
            operation="filter_purchase_histories",
            method="GET",
            path="/ppg/v3/purchases/histories",
            safety=OperationSafety.READ_ONLY,
            model=PurchaseHistoryPage,
            params=criteria.to_query(),
        )

    def get_balances(self) -> APIResponse[ClientBalances]:
        """Return the configured client's documented PPG ledger balances."""
        return self._typed(
            operation="get_balances",
            method="GET",
            path="/ppg/v3/balances",
            safety=OperationSafety.READ_ONLY,
            model=ClientBalances,
        )

    def health(self) -> APIResponse[HealthResult]:
        """Return PPG and downstream PSP health indicators."""
        return self._typed(
            operation="health",
            method="GET",
            path="/ppg/v3/app/health",
            safety=OperationSafety.READ_ONLY,
            model=HealthResult,
        )

    def _refund_action(
        self,
        operation: str,
        refund_id: int,
        action: str,
        transfer_id: str | None,
    ) -> APIResponse[StatusResult]:
        if refund_id <= 0:
            raise self._validation_error(
                operation,
                "POST",
                f"/ppg/v3/purchases/refunds/{refund_id}/{action}",
                "refund_id must be positive",
            )
        path = f"/ppg/v3/purchases/refunds/{refund_id}/{action}"
        request = self._request(
            RefundActionRequest,
            {"transfer_id": transfer_id},
            operation=operation,
            method="POST",
            path=path,
        )
        try:
            raw = self._engine.execute(
                RequestOptions(
                    service=_SERVICE,
                    operation=operation,
                    method="POST",
                    path=path,
                    safety=OperationSafety.UNSAFE,
                    json=request.to_payload(),
                )
            )
        except JibitError as exc:
            self._audit_error(
                name=f"jibit.payment.{operation}",
                operation=operation,
                error=exc,
            )
            raise
        result = APIResponse(
            data=StatusResult(
                success=True,
                status_code=raw.status_code,
                raw_body=raw.content or None,
            ),
            raw=raw,
        )
        self._audit(
            name=f"jibit.payment.{operation}",
            operation=operation,
            result=result,
            metadata={"refund_id": refund_id, "transfer_id": transfer_id},
        )
        return result

    def _typed(
        self,
        *,
        operation: str,
        method: str,
        path: str,
        safety: OperationSafety,
        model: type[ModelT],
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> APIResponse[ModelT]:
        raw = self._engine.execute(
            RequestOptions(
                service=_SERVICE,
                operation=operation,
                method=method,
                path=path,
                safety=safety,
                json=body,
                params=params,
            )
        )
        return parse_model_response(
            raw,
            model,
            service=_SERVICE.value,
            operation=operation,
            method=method,
            endpoint=path,
        )

    def _financial_typed(
        self,
        *,
        audit_name: str,
        operation: str,
        method: str,
        path: str,
        safety: OperationSafety,
        model: type[ModelT],
        body: dict[str, Any] | None = None,
    ) -> APIResponse[ModelT]:
        """Execute a financial operation and audit failures or uncertain outcomes."""
        try:
            return self._typed(
                operation=operation,
                method=method,
                path=path,
                safety=safety,
                model=model,
                body=body,
            )
        except JibitError as exc:
            self._audit_error(name=audit_name, operation=operation, error=exc)
            raise

    def _audit(
        self,
        *,
        name: str,
        operation: str,
        result: APIResponse[Any],
        metadata: dict[str, Any],
    ) -> None:
        self._emit_audit(
            name=name,
            correlation_id=result.raw.correlation_id,
            operation=operation,
            outcome="succeeded",
            metadata=metadata,
        )

    def _audit_error(self, *, name: str, operation: str, error: JibitError) -> None:
        outcome = (
            "unknown"
            if isinstance(
                error,
                (JibitTimeoutError, JibitNetworkError, JibitServerError, JibitResponseError),
            )
            else "failed"
        )
        self._emit_audit(
            name=name,
            correlation_id=error.context.correlation_id or "unavailable",
            operation=operation,
            outcome=outcome,
            metadata={
                "error_type": type(error).__name__,
                "error_code": error.context.error_code,
                "status_code": error.context.status_code,
            },
        )

    def _emit_audit(
        self,
        *,
        name: str,
        correlation_id: str,
        operation: str,
        outcome: str,
        metadata: Mapping[str, Any],
    ) -> None:
        event = AuditEvent(
            name=name,
            correlation_id=correlation_id,
            service=_SERVICE.value,
            operation=operation,
            outcome=outcome,
            metadata=metadata,
        )
        try:
            self._audit_sink.emit(event)
        except Exception as exc:
            # An extension failure must never make a successful financial request look failed.
            self._logger.emit(
                logging.ERROR,
                EventName.AUDIT_EMIT_FAILED,
                service=_SERVICE.value,
                operation=operation,
                correlation_id=correlation_id,
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _request(
        model: type[ModelT],
        values: Mapping[str, Any],
        *,
        operation: str,
        method: str,
        path: str,
    ) -> ModelT:
        try:
            return model.model_validate(values)
        except ValidationError:
            raise PaymentGatewayService._validation_error(
                operation,
                method,
                path,
                "The request parameters are invalid",
            ) from None

    @staticmethod
    def _validation_error(
        operation: str,
        method: str,
        path: str,
        message: str,
    ) -> JibitValidationError:
        return JibitValidationError(
            message,
            context=ErrorContext(
                service=_SERVICE.value,
                operation=operation,
                method=method,
                endpoint=path,
                retryable=False,
            ),
        )
