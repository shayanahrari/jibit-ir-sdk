"""High-level Cobank settlement operations with explicit reconciliation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from jibit.engine import RequestOptions
from jibit.models import JibitRequestModel
from jibit.response import APIResponse
from jibit.retry import OperationSafety
from jibit.services.base import RequestExecutor, typed_request, validate_request
from jibit.services.cobank.models import (
    CobankTransferType,
    CreateSettlementRequest,
    MerchantAccountList,
    ReceiptLinkResult,
    ReceiptState,
    SettlementBatchResult,
    SettlementPage,
    SettlementResult,
    TransferReason,
)
from jibit.types import ServiceName

_SERVICE = ServiceName.COBANK
_SETTLEMENT_PATH = "/cobank/v1/orders/settlement"
ModelT = TypeVar("ModelT", bound=BaseModel)


class _BatchInquiryRequest(JibitRequestModel):
    """Validate the provider's settlement batch-inquiry size."""

    track_ids: tuple[UUID, ...] = Field(min_length=1, max_length=10_000)


class _Pagination(JibitRequestModel):
    """Validate conservative Cobank list pagination."""

    page_number: int = Field(default=0, ge=0)
    page_size: int = Field(default=50, ge=1, le=250)


class _Reference(JibitRequestModel):
    """Keep caller references inside one URL path segment."""

    value: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._-]+$")


class CobankService:
    """Expose Cobank settlement submission, inquiry, account, and receipt operations."""

    def __init__(self, executor: RequestExecutor) -> None:
        self._executor = executor

    def create_settlement(
        self,
        *,
        record_track_id: UUID | str,
        destination_iban: str,
        amount: int,
        transfer_type: CobankTransferType | str | None = None,
        transfer_reason: TransferReason | str | None = None,
        source_iban: str | None = None,
        payment_id: str | None = None,
        request_description: str | None = None,
    ) -> APIResponse[SettlementResult]:
        """Submit one settlement once; reconcile using record_track_id after uncertainty."""
        request = self._validate(
            CreateSettlementRequest,
            {
                "record_track_id": record_track_id,
                "destination_iban": destination_iban,
                "amount": amount,
                "transfer_type": transfer_type,
                "transfer_reason": transfer_reason,
                "source_iban": source_iban,
                "payment_id": payment_id,
                "request_description": request_description,
            },
            operation="create_settlement",
            method="POST",
            path=_SETTLEMENT_PATH,
        )
        return self._typed(
            "create_settlement",
            "POST",
            _SETTLEMENT_PATH,
            OperationSafety.UNSAFE,
            SettlementResult,
            json=request.to_payload(),
        )

    def inquire_settlement(
        self, track_id: UUID | str, *, show_archive: bool = False
    ) -> APIResponse[SettlementResult]:
        """Reconcile a settlement by the caller-provided UUID track ID."""
        track = self._track_id(track_id, operation="inquire_settlement")
        return self._typed(
            "inquire_settlement",
            "GET",
            f"{_SETTLEMENT_PATH}/{track}",
            OperationSafety.READ_ONLY,
            SettlementResult,
            params={"showArchive": show_archive},
        )

    def batch_inquire_settlements(
        self,
        track_ids: Sequence[UUID | str],
        *,
        show_archive: bool = False,
    ) -> APIResponse[SettlementBatchResult]:
        """Reconcile up to ten thousand settlements in one documented request."""
        request = self._validate(
            _BatchInquiryRequest,
            {"track_ids": track_ids},
            operation="batch_inquire_settlements",
            method="POST",
            path=f"{_SETTLEMENT_PATH}/batch-inquiry",
        )
        return self._typed(
            "batch_inquire_settlements",
            "POST",
            f"{_SETTLEMENT_PATH}/batch-inquiry",
            OperationSafety.IDEMPOTENT,
            SettlementBatchResult,
            params={"showArchive": show_archive},
            json=request.to_payload(),
        )

    def list_settlements(
        self, *, page_number: int = 0, page_size: int = 50
    ) -> APIResponse[SettlementPage]:
        """Return a bounded page of settlement summaries."""
        pagination = self._validate(
            _Pagination,
            {"page_number": page_number, "page_size": page_size},
            operation="list_settlements",
            method="GET",
            path=f"{_SETTLEMENT_PATH}/list",
        )
        return self._typed(
            "list_settlements",
            "GET",
            f"{_SETTLEMENT_PATH}/list",
            OperationSafety.READ_ONLY,
            SettlementPage,
            params=pagination.to_query(),
        )

    def get_merchant_accounts(self) -> APIResponse[MerchantAccountList]:
        """Return configured Cobank accounts in a secret-safe evolving container."""
        return self._typed(
            "get_merchant_accounts",
            "GET",
            "/cobank/v1/accounts/",
            OperationSafety.READ_ONLY,
            MerchantAccountList,
        )

    def set_settlement_receipt(
        self, reference_number: str, *, active: bool
    ) -> APIResponse[ReceiptLinkResult]:
        """Set the public receipt-link state for an entire settlement."""
        reference = self._reference(reference_number, operation="set_settlement_receipt")
        state = ReceiptState.ACTIVE if active else ReceiptState.INACTIVE
        return self._typed(
            "set_settlement_receipt",
            "PUT",
            f"/cobank/v2/orders/settlement/{reference}/receipt-link",
            OperationSafety.IDEMPOTENT,
            ReceiptLinkResult,
            json={"state": state.value},
        )

    def set_record_receipt(
        self,
        reference_number: str,
        record_reference_number: str,
        *,
        active: bool,
    ) -> APIResponse[ReceiptLinkResult]:
        """Set the public receipt-link state for one settlement record."""
        reference = self._reference(reference_number, operation="set_record_receipt")
        record_reference = self._reference(record_reference_number, operation="set_record_receipt")
        state = ReceiptState.ACTIVE if active else ReceiptState.INACTIVE
        path = f"/cobank/v2/orders/settlement/{reference}/records/{record_reference}/receipt-link"
        return self._typed(
            "set_record_receipt",
            "PUT",
            path,
            OperationSafety.IDEMPOTENT,
            ReceiptLinkResult,
            json={"state": state.value},
        )

    def _typed(
        self,
        operation: str,
        method: str,
        path: str,
        safety: OperationSafety,
        model: type[ModelT],
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> APIResponse[ModelT]:
        return typed_request(
            self._executor,
            RequestOptions(
                service=_SERVICE,
                operation=operation,
                method=method,
                path=path,
                safety=safety,
                params=params,
                json=json,
            ),
            model,
        )

    @staticmethod
    def _track_id(value: UUID | str, *, operation: str) -> UUID:
        request = CobankService._validate(
            _BatchInquiryRequest,
            {"track_ids": [value]},
            operation=operation,
            method="GET",
            path=_SETTLEMENT_PATH,
        )
        return request.track_ids[0]

    @staticmethod
    def _reference(value: str, *, operation: str) -> str:
        request = CobankService._validate(
            _Reference,
            {"value": value},
            operation=operation,
            method="PUT",
            path="/cobank/v2/orders/settlement/{reference}/receipt-link",
        )
        return request.value

    @staticmethod
    def _validate(model: type[ModelT], values: dict[str, Any], **context: str) -> ModelT:
        return validate_request(
            model,
            values,
            service=_SERVICE.value,
            endpoint=context.pop("path"),
            **context,
        )
