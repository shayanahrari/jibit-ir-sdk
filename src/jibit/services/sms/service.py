"""High-level Pulse SMS operations with message-safe diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from jibit.engine import RequestOptions
from jibit.models import JibitRequestModel
from jibit.response import APIResponse
from jibit.retry import OperationSafety
from jibit.services.base import RequestExecutor, typed_request, validate_request
from jibit.services.sms.models import (
    BulkResult,
    CreateBulkRequest,
    InboundMessageResult,
    PatternSmsRequest,
    PatternSmsResult,
    SimpleSmsRequest,
    SmsOrderResult,
    SmsStatusResult,
    _InboundQuery,
)
from jibit.types import ServiceName

_SERVICE = ServiceName.SMS
_PREFIX = "/pulse/api/v1/message/sms"
ModelT = TypeVar("ModelT", bound=BaseModel)


class _Page(JibitRequestModel):
    """Validate Pulse zero-based page options."""

    page: int = Field(default=0, alias="page", ge=0)
    page_size: int = Field(default=20, alias="page_size", ge=1, le=1000)


class PulseSmsService:
    """Expose simple, pattern, bulk, status, and inbound SMS operations."""

    def __init__(self, executor: RequestExecutor) -> None:
        self._executor = executor

    def send(
        self,
        *,
        receptor: str,
        message: str,
        sender: str | None = None,
        client_message_id: str | None = None,
    ) -> APIResponse[SmsOrderResult]:
        """Send a simple message once without automatic replay."""
        request = self._validate(
            SimpleSmsRequest,
            locals(),
            operation="send",
            method="POST",
            path=f"{_PREFIX}/send",
        )
        return self._typed(
            "send",
            "POST",
            f"{_PREFIX}/send",
            OperationSafety.UNSAFE,
            SmsOrderResult,
            json=request.to_payload(),
        )

    def send_pattern(
        self,
        *,
        receptor: str,
        template: str,
        params: dict[str, str],
        sender: str | None = None,
        client_message_id: str | None = None,
    ) -> APIResponse[PatternSmsResult]:
        """Send a pattern message once without logging template values."""
        request = self._validate(
            PatternSmsRequest,
            locals(),
            operation="send_pattern",
            method="POST",
            path=f"{_PREFIX}/pattern/send",
        )
        return self._typed(
            "send_pattern",
            "POST",
            f"{_PREFIX}/pattern/send",
            OperationSafety.UNSAFE,
            PatternSmsResult,
            json=request.to_payload(),
        )

    def create_bulk(
        self,
        *,
        bulk_name: str,
        sender: str,
        receptors: list[str] | tuple[str, ...],
        message: str | None = None,
        predefined_message_id: UUID | str | None = None,
        client_bulk_reference: str | None = None,
    ) -> APIResponse[BulkResult]:
        """Create one bounded bulk SMS submission without automatic replay."""
        request = self._validate(
            CreateBulkRequest,
            locals(),
            operation="create_bulk",
            method="POST",
            path=f"{_PREFIX}/bulk",
        )
        return self._typed(
            "create_bulk",
            "POST",
            f"{_PREFIX}/bulk",
            OperationSafety.UNSAFE,
            BulkResult,
            json=request.to_payload(),
        )

    def get_status(self, message_id: UUID | str) -> APIResponse[SmsStatusResult]:
        """Inquire an SMS using its provider message ID."""
        message_uuid = self._uuid(message_id, operation="get_status")
        return self._typed(
            "get_status",
            "GET",
            f"{_PREFIX}/status/{message_uuid}",
            OperationSafety.READ_ONLY,
            SmsStatusResult,
        )

    def get_status_by_client_id(self, client_message_id: str) -> APIResponse[SmsStatusResult]:
        """Inquire an SMS using the caller's client message reference."""
        reference = self._reference(client_message_id, operation="get_status_by_client_id")
        return self._typed(
            "get_status_by_client_id",
            "GET",
            f"{_PREFIX}/status/client-message-id/{reference}",
            OperationSafety.READ_ONLY,
            SmsStatusResult,
        )

    def get_bulk(
        self, bulk_id: UUID | str, *, page: int = 0, page_size: int = 20
    ) -> APIResponse[BulkResult]:
        """Return one page of individual messages for a bulk order."""
        bulk_uuid = self._uuid(bulk_id, operation="get_bulk")
        pagination = self._validate(
            _Page,
            {"page": page, "page_size": page_size},
            operation="get_bulk",
            method="GET",
            path=f"{_PREFIX}/bulk/{bulk_uuid}",
        )
        return self._typed(
            "get_bulk",
            "GET",
            f"{_PREFIX}/bulk/{bulk_uuid}",
            OperationSafety.READ_ONLY,
            BulkResult,
            params=pagination.to_query(),
        )

    def fetch_inbound(
        self, *, from_date: datetime, to_date: datetime, page: int = 0
    ) -> APIResponse[InboundMessageResult]:
        """Return inbound messages for a bounded page and explicit date interval."""
        query = self._validate(
            _InboundQuery,
            {"from_date": from_date, "to_date": to_date, "page": page},
            operation="fetch_inbound",
            method="GET",
            path=f"{_PREFIX}/mo-messages",
        )
        return self._typed(
            "fetch_inbound",
            "GET",
            f"{_PREFIX}/mo-messages",
            OperationSafety.READ_ONLY,
            InboundMessageResult,
            params=query.to_query(),
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
            RequestOptions(_SERVICE, operation, method, path, safety, params=params, json=json),
            model,
        )

    @staticmethod
    def _uuid(value: UUID | str, *, operation: str) -> UUID:
        class _UUIDValue(JibitRequestModel):
            value: UUID

        return PulseSmsService._validate(
            _UUIDValue,
            {"value": value},
            operation=operation,
            method="GET",
            path=_PREFIX,
        ).value

    @staticmethod
    def _reference(value: str, *, operation: str) -> str:
        class _Reference(JibitRequestModel):
            value: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._-]+$")

        return PulseSmsService._validate(
            _Reference,
            {"value": value},
            operation=operation,
            method="GET",
            path=_PREFIX,
        ).value

    @staticmethod
    def _validate(model: type[ModelT], values: dict[str, Any], **context: str) -> ModelT:
        values.pop("self", None)
        return validate_request(
            model,
            values,
            service=_SERVICE.value,
            endpoint=context.pop("path"),
            **context,
        )
