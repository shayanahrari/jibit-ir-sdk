"""High-level Direct Debit operations with status-only limitations preserved."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from jibit.engine import RequestOptions
from jibit.exceptions import JibitValidationError
from jibit.response import APIResponse, StatusResult
from jibit.retry import OperationSafety
from jibit.services.base import RequestExecutor, typed_request, validate_request
from jibit.services.direct_debit.models import (
    ActiveBankList,
    BlueBankCallback,
    CollectRequest,
    CreateMandateRequest,
    InitiateMandateResult,
    MandateResult,
    MandateType,
    TransactionList,
    TransactionResult,
)
from jibit.types import ServiceName

_SERVICE = ServiceName.DIRECT_DEBIT
_PREFIX = "/directdebit/api/v1"
ModelT = TypeVar("ModelT", bound=BaseModel)


class DirectDebitService:
    """Expose mandate lifecycle, collection, inquiry, and active-bank operations."""

    def __init__(self, executor: RequestExecutor) -> None:
        self._executor = executor

    def create_mandate(
        self,
        mandate_type: MandateType | str,
        request: CreateMandateRequest | None = None,
        **values: Any,
    ) -> APIResponse[InitiateMandateResult]:
        """Initiate one mandate once; the SDK never replays an uncertain result."""
        try:
            mandate_type = MandateType(mandate_type)
        except ValueError:
            raise self._invalid("create_mandate", "mandate_type is not supported") from None
        if request is not None and values:
            raise self._invalid("create_mandate", "Provide request or keyword values, not both")
        request = request or self._validate(
            CreateMandateRequest,
            values,
            operation="create_mandate",
            method="POST",
            path=f"{_PREFIX}/mandate/{mandate_type.value}",
        )
        if mandate_type is MandateType.ONE_TAP and request.frequency is None:
            raise self._invalid("create_mandate", "frequency is required for one-tap mandates")
        if mandate_type is MandateType.SUBSCRIPTION and request.retry is None:
            raise self._invalid("create_mandate", "retry is required for subscription mandates")
        if (
            mandate_type in {MandateType.ONE_TAP, MandateType.TIME_FRAME}
            and request.otp_requirement_status is None
        ):
            raise self._invalid(
                "create_mandate",
                "otp_requirement_status is required for this mandate type",
            )
        payload = request.to_payload()
        incompatible_fields = {
            MandateType.TIME_FRAME: {"frequency", "retry"},
            MandateType.SUBSCRIPTION: {
                "frequency",
                "otp_requirement_status",
                "otp_condition",
            },
            MandateType.ONE_TAP: {"retry"},
        }
        for field in incompatible_fields[mandate_type]:
            payload.pop(field, None)
        return self._typed(
            "create_mandate",
            "POST",
            f"{_PREFIX}/mandate/{mandate_type.value}",
            OperationSafety.UNSAFE,
            InitiateMandateResult,
            json=payload,
        )

    def collect(
        self,
        *,
        creditor_transaction_no: str,
        mandate_reference: str,
        amount: int,
        otp: str | None = None,
    ) -> APIResponse[TransactionResult]:
        """Submit one collection without automatic retry."""
        request = self._validate(
            CollectRequest,
            {
                "creditor_transaction_no": creditor_transaction_no,
                "mandate_reference": mandate_reference,
                "amount": amount,
                "otp": otp,
            },
            operation="collect",
            method="POST",
            path=f"{_PREFIX}/transaction/collect",
        )
        return self._typed(
            "collect",
            "POST",
            f"{_PREFIX}/transaction/collect",
            OperationSafety.UNSAFE,
            TransactionResult,
            json=request.to_payload(),
        )

    def revoke_mandate(
        self, mandate_reference: str, *, revoke_by: str, additional_info: str | None = None
    ) -> APIResponse[StatusResult]:
        """Revoke a mandate and return HTTP-status-only success."""
        reference = self._reference(mandate_reference, operation="revoke_mandate")
        if not revoke_by or (additional_info is not None and len(additional_info) > 500):
            raise self._invalid("revoke_mandate", "revoke parameters are invalid")
        return self._status(
            "revoke_mandate",
            "PUT",
            f"{_PREFIX}/mandate/revoke",
            {
                "mandate_reference": reference,
                "revoke_by": revoke_by,
                "additional_info": additional_info,
            },
        )

    def enable_mandate(
        self, mandate_reference: str, *, enable_by: str
    ) -> APIResponse[StatusResult]:
        """Enable a mandate and return HTTP-status-only success."""
        reference = self._reference(mandate_reference, operation="enable_mandate")
        if not enable_by:
            raise self._invalid("enable_mandate", "enable_by is required")
        return self._status(
            "enable_mandate",
            "PUT",
            f"{_PREFIX}/mandate/enable",
            {"mandate_reference": reference, "enable_by": enable_by},
        )

    def disable_mandate(
        self, mandate_reference: str, *, disable_by: str
    ) -> APIResponse[StatusResult]:
        """Disable a mandate and return HTTP-status-only success."""
        reference = self._reference(mandate_reference, operation="disable_mandate")
        if not disable_by:
            raise self._invalid("disable_mandate", "disable_by is required")
        return self._status(
            "disable_mandate",
            "PUT",
            f"{_PREFIX}/mandate/disable",
            {"mandate_reference": reference, "disable_by": disable_by},
        )

    def send_otp(self, mandate_number: str) -> APIResponse[StatusResult]:
        """Request one-tap OTP delivery and return HTTP-status-only success."""
        reference = self._reference(mandate_number, operation="send_otp")
        return self._status(
            "send_otp",
            "POST",
            f"{_PREFIX}/transaction/otp/{reference}",
            None,
        )

    def accept_blue_bank_callback(
        self, payload: BlueBankCallback | dict[str, Any]
    ) -> APIResponse[StatusResult]:
        """Forward a pre-verified callback to the documented provider callback operation."""
        callback = (
            payload
            if isinstance(payload, BlueBankCallback)
            else self._validate(
                BlueBankCallback,
                payload,
                operation="accept_blue_bank_callback",
                method="POST",
                path=f"{_PREFIX}/blue-bank-callback",
            )
        )
        return self._status(
            "accept_blue_bank_callback",
            "POST",
            f"{_PREFIX}/blue-bank-callback",
            callback.to_payload(),
        )

    def inquire_transaction(self, creditor_transaction_no: str) -> APIResponse[TransactionResult]:
        """Reconcile a collection by the creditor transaction reference."""
        reference = self._reference(creditor_transaction_no, operation="inquire_transaction")
        return self._typed(
            "inquire_transaction",
            "GET",
            f"{_PREFIX}/transaction/{reference}",
            OperationSafety.READ_ONLY,
            TransactionResult,
        )

    def list_subscription_transactions(self, mandate_number: str) -> APIResponse[TransactionList]:
        """Return transactions collected under a subscription mandate."""
        reference = self._reference(mandate_number, operation="list_subscription_transactions")
        return self._typed(
            "list_subscription_transactions",
            "GET",
            f"{_PREFIX}/subscription-mandate/{reference}/transactions",
            OperationSafety.READ_ONLY,
            TransactionList,
        )

    def inquire_mandate(self, mandate_reference: str) -> APIResponse[MandateResult]:
        """Reconcile a mandate using its provider reference."""
        reference = self._reference(mandate_reference, operation="inquire_mandate")
        return self._typed(
            "inquire_mandate",
            "GET",
            f"{_PREFIX}/mandates/mandate-reference/{reference}",
            OperationSafety.READ_ONLY,
            MandateResult,
        )

    def inquire_creditor_mandate(self, creditor_reference: str) -> APIResponse[MandateResult]:
        """Reconcile a mandate using the caller's creditor reference."""
        reference = self._reference(creditor_reference, operation="inquire_creditor_mandate")
        return self._typed(
            "inquire_creditor_mandate",
            "GET",
            f"{_PREFIX}/mandates/creditor-mandate-reference/{reference}",
            OperationSafety.READ_ONLY,
            MandateResult,
        )

    def get_active_banks(self) -> APIResponse[ActiveBankList]:
        """Return banks currently enabled for the configured creditor."""
        return self._typed(
            "get_active_banks",
            "GET",
            f"{_PREFIX}/creditor/active-banks",
            OperationSafety.READ_ONLY,
            ActiveBankList,
        )

    def _status(
        self, operation: str, method: str, path: str, payload: dict[str, Any] | None
    ) -> APIResponse[StatusResult]:
        raw = self._executor.execute(
            RequestOptions(
                service=_SERVICE,
                operation=operation,
                method=method,
                path=path,
                safety=OperationSafety.UNSAFE,
                json={key: value for key, value in payload.items() if value is not None}
                if payload is not None
                else None,
            )
        )
        return APIResponse(StatusResult(True, raw.status_code, raw.content or None), raw)

    def _typed(
        self,
        operation: str,
        method: str,
        path: str,
        safety: OperationSafety,
        model: type[ModelT],
        *,
        json: dict[str, Any] | None = None,
    ) -> APIResponse[ModelT]:
        return typed_request(
            self._executor,
            RequestOptions(_SERVICE, operation, method, path, safety, json=json),
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

    @staticmethod
    def _reference(value: str, *, operation: str) -> str:
        if not value or not all(character.isalnum() or character in "-_." for character in value):
            raise DirectDebitService._invalid(operation, "reference contains invalid characters")
        return value

    @staticmethod
    def _invalid(operation: str, message: str) -> JibitValidationError:
        from jibit.services.base import request_validation_error

        return request_validation_error(
            service=_SERVICE.value,
            operation=operation,
            method="POST",
            endpoint=_PREFIX,
            message=message,
        )
