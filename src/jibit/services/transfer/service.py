"""High-level Transferor v2 operations with conservative financial safety."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, TypeVar

from pydantic import AwareDatetime, BaseModel, Field, model_validator
from typing_extensions import Self

from jibit.engine import RequestOptions
from jibit.models import JibitRequestModel
from jibit.response import APIResponse, StatusResult
from jibit.retry import OperationSafety
from jibit.services.base import (
    RequestExecutor,
    request_validation_error,
    typed_request,
    validate_request,
)
from jibit.services.transfer.models import (
    BalanceResult,
    BankList,
    BatchGeneratorRequest,
    ReceiptResult,
    SubmissionMode,
    SubmitBatchRequest,
    SubmitBatchResult,
    TransferFilterResult,
    TransferInquiryResult,
    TransferItemRequest,
    TransferSelector,
    TransferState,
    UsageReportResult,
)
from jibit.types import ServiceName

_SERVICE = ServiceName.TRANSFERS
_TRANSFERS_PATH = "/trf/v2/transfers"
ModelT = TypeVar("ModelT", bound=BaseModel)


class _FilterValidation(JibitRequestModel):
    """Validate Transferor filter state, UTC times, and paging constraints."""

    state: TransferState | None = None
    from_time: AwareDatetime | None = Field(default=None, alias="from")
    to_time: AwareDatetime | None = Field(default=None, alias="to")
    page: int = Field(ge=1)
    size: int = Field(ge=1, le=250)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        """Reject a reversed filter interval before sending it upstream."""
        if (
            self.from_time is not None
            and self.to_time is not None
            and self.from_time > self.to_time
        ):
            raise ValueError("from_time must not be later than to_time")
        return self


class _DailyUsageRequest(JibitRequestModel):
    """Validate the provider's six-digit local date representation."""

    year_month_day: str = Field(pattern=r"^\d{6}$")


class TransferService:
    """Expose Transferor batches, inquiries, balances, reports, and bank metadata."""

    def __init__(self, executor: RequestExecutor) -> None:
        self._executor = executor

    def submit_batch(
        self,
        *,
        batch_id: str,
        transfers: Sequence[TransferItemRequest | dict[str, Any]],
        submission_mode: SubmissionMode | str = SubmissionMode.BATCH,
    ) -> APIResponse[SubmitBatchResult]:
        """Submit a financial batch once; reconcile by batch ID after an uncertain failure."""
        request = self._validate(
            SubmitBatchRequest,
            {
                "batch_id": batch_id,
                "submission_mode": submission_mode,
                "transfers": transfers,
            },
            operation="submit_batch",
            method="POST",
            path=_TRANSFERS_PATH,
        )
        return self._typed(
            "submit_batch",
            "POST",
            _TRANSFERS_PATH,
            OperationSafety.UNSAFE,
            SubmitBatchResult,
            json=request.to_payload(),
        )

    def inquire(
        self,
        *,
        batch_id: str | None = None,
        transfer_id: str | None = None,
    ) -> APIResponse[TransferInquiryResult]:
        """Reconcile a batch, one transfer, or a transfer within a batch."""
        selector = self._selector(batch_id, transfer_id, operation="inquire", method="GET")
        return self._typed(
            "inquire",
            "GET",
            _TRANSFERS_PATH,
            OperationSafety.READ_ONLY,
            TransferInquiryResult,
            params=selector.to_query(),
        )

    def cancel(
        self,
        *,
        batch_id: str | None = None,
        transfer_id: str | None = None,
    ) -> APIResponse[StatusResult]:
        """Request cancellation once and return status-only success information."""
        selector = self._selector(batch_id, transfer_id, operation="cancel", method="DELETE")
        raw = self._executor.execute(
            RequestOptions(
                service=_SERVICE,
                operation="cancel",
                method="DELETE",
                path=_TRANSFERS_PATH,
                safety=OperationSafety.UNSAFE,
                params=selector.to_query(),
            )
        )
        return APIResponse(
            data=StatusResult(True, raw.status_code, raw.content or None),
            raw=raw,
        )

    def retry_failed(
        self,
        *,
        batch_id: str | None = None,
        transfer_id: str | None = None,
    ) -> APIResponse[StatusResult]:
        """Explicitly retry a failed provider transfer without SDK-level replay."""
        selector = self._selector(batch_id, transfer_id, operation="retry_failed", method="PATCH")
        raw = self._executor.execute(
            RequestOptions(
                service=_SERVICE,
                operation="retry_failed",
                method="PATCH",
                path=_TRANSFERS_PATH,
                safety=OperationSafety.UNSAFE,
                params=selector.to_query(),
                json={"state": "RETRY"},
            )
        )
        return APIResponse(
            data=StatusResult(True, raw.status_code, raw.content or None),
            raw=raw,
        )

    def filter_transfers(
        self,
        *,
        state: TransferState | str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        page: int = 1,
        size: int = 50,
    ) -> APIResponse[TransferFilterResult]:
        """Filter submitted transfers using bounded pagination and optional UTC times."""
        pagination = self._validate(
            _FilterValidation,
            {
                "state": state,
                "from_time": from_time,
                "to_time": to_time,
                "page": page,
                "size": size,
            },
            operation="filter_transfers",
            method="GET",
            path=f"{_TRANSFERS_PATH}/filter",
        )
        return self._typed(
            "filter_transfers",
            "GET",
            f"{_TRANSFERS_PATH}/filter",
            OperationSafety.READ_ONLY,
            TransferFilterResult,
            params=pagination.to_query(),
        )

    def set_receipt_enabled(
        self,
        *,
        enabled: bool,
        batch_id: str | None = None,
        transfer_id: str | None = None,
    ) -> APIResponse[ReceiptResult]:
        """Enable or disable the temporary provider-hosted public receipt link."""
        selector = self._selector(
            batch_id, transfer_id, operation="set_receipt_enabled", method="POST"
        )
        body = selector.to_payload()
        body["newEnablementStatus"] = str(enabled).lower()
        return self._typed(
            "set_receipt_enabled",
            "POST",
            "/trf/v2/receipts",
            OperationSafety.UNSAFE,
            ReceiptResult,
            json=body,
        )

    def get_balances(self) -> APIResponse[BalanceResult]:
        """Return main, settleable, and categorized Transferor wallet balances."""
        return self._typed(
            "get_balances",
            "GET",
            "/trf/v2/balances",
            OperationSafety.READ_ONLY,
            BalanceResult,
        )

    def get_daily_usage_report(self, year_month_day: str) -> APIResponse[UsageReportResult]:
        """Return daily usage for the provider's documented six-digit date."""
        request = self._validate(
            _DailyUsageRequest,
            {"year_month_day": year_month_day},
            operation="get_daily_usage_report",
            method="GET",
            path="/trf/v2/reports/daily",
        )
        return self._typed(
            "get_daily_usage_report",
            "GET",
            "/trf/v2/reports/daily",
            OperationSafety.READ_ONLY,
            UsageReportResult,
            params=request.to_query(),
        )

    def get_supported_normal_banks(self) -> APIResponse[BankList]:
        """Return provider identifiers for banks supporting normal transfers."""
        return self._typed(
            "get_supported_normal_banks",
            "GET",
            "/trf/v2/banks/normal",
            OperationSafety.READ_ONLY,
            BankList,
        )

    def get_active_normal_banks(self) -> APIResponse[BankList]:
        """Return provider identifiers for currently active normal-transfer banks."""
        return self._typed(
            "get_active_normal_banks",
            "GET",
            "/trf/v2/banks/status",
            OperationSafety.READ_ONLY,
            BankList,
        )

    def generate_batch(
        self, request: BatchGeneratorRequest | None = None, **values: Any
    ) -> APIResponse[SubmitBatchRequest]:
        """Ask Transferor to split a large transfer into a submission-ready batch."""
        if request is not None and values:
            raise request_validation_error(
                service=_SERVICE.value,
                operation="generate_batch",
                method="POST",
                endpoint="/trf/v2/batch/generate",
                message="Provide request or keyword values, not both",
            )
        request = request or self._validate(
            BatchGeneratorRequest,
            values,
            operation="generate_batch",
            method="POST",
            path="/trf/v2/batch/generate",
        )
        return self._typed(
            "generate_batch",
            "POST",
            "/trf/v2/batch/generate",
            OperationSafety.IDEMPOTENT,
            SubmitBatchRequest,
            json=request.to_payload(),
        )

    def _selector(
        self,
        batch_id: str | None,
        transfer_id: str | None,
        *,
        operation: str,
        method: str,
    ) -> TransferSelector:
        return self._validate(
            TransferSelector,
            {"batch_id": batch_id, "transfer_id": transfer_id},
            operation=operation,
            method=method,
            path=_TRANSFERS_PATH,
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
    def _validate(model: type[ModelT], values: dict[str, Any], **context: str) -> ModelT:
        return validate_request(
            model,
            values,
            service=_SERVICE.value,
            endpoint=context.pop("path"),
            **context,
        )
