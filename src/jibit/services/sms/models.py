"""Typed Pulse SMS request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator
from typing_extensions import Self

from jibit.models import JibitModel, JibitRequestModel


class SimpleSmsRequest(JibitRequestModel):
    """Validate one simple SMS order."""

    receptor: str = Field(alias="receptor", min_length=10, max_length=20)
    message: str = Field(alias="message", min_length=1, max_length=2000)
    sender: str | None = Field(default=None, alias="sender", min_length=1, max_length=50)
    client_message_id: str | None = Field(
        default=None, alias="client_message_id", min_length=1, max_length=100
    )


class PatternSmsRequest(JibitRequestModel):
    """Validate one template-based SMS order."""

    receptor: str = Field(alias="receptor", min_length=10, max_length=20)
    template: str = Field(alias="template", min_length=1, max_length=100)
    params: dict[str, str] = Field(default_factory=dict, alias="params")
    sender: str | None = Field(default=None, alias="sender", min_length=1, max_length=50)
    client_message_id: str | None = Field(
        default=None, alias="client_message_id", min_length=1, max_length=100
    )


class SmsOrder(JibitModel):
    """Represent provider acceptance and status for one SMS."""

    message_id: UUID | str | None = None
    message: str | None = None
    status: str | None = None
    status_text: str | None = None
    segment_count: int | None = None
    sender: str | None = None
    receptor: str | None = None


class SmsOrderResult(JibitModel):
    """Contain provider results for a simple SMS order."""

    sms_orders: list[SmsOrder] = Field(default_factory=list)


class PatternSmsResult(SmsOrder):
    """Represent a pattern SMS result."""


class SmsStatusResult(JibitModel):
    """Represent inquiry state for one message."""

    message_id: str | None = None
    status: str | None = None
    status_text: str | None = None


class CreateBulkRequest(JibitRequestModel):
    """Validate a bounded bulk SMS submission."""

    bulk_name: str = Field(alias="bulk_name", min_length=1, max_length=200)
    sender: str = Field(alias="sender", min_length=1, max_length=50)
    receptors: tuple[str, ...] = Field(alias="receptors", min_length=1, max_length=1000)
    message: str | None = Field(default=None, alias="message", max_length=2000)
    predefined_message_id: UUID | None = Field(default=None, alias="predefined_message_id")
    client_bulk_reference: str | None = Field(
        default=None, alias="client_bulk_reference", max_length=100
    )

    @model_validator(mode="after")
    def require_message_source(self) -> Self:
        """Require exactly one bulk message source."""
        if (self.message is None) == (self.predefined_message_id is None):
            raise ValueError("provide exactly one of message or predefined_message_id")
        return self


class BulkResult(JibitModel):
    """Represent creation or inquiry state for a bulk SMS."""

    bulk_id: UUID | str | None = None
    bulk_name: str | None = None
    client_bulk_reference: str | None = None
    message: str | None = None
    sender: str | None = None
    status: str | None = None
    status_text: str | None = None
    total_recipients: int | None = None
    scheduled_time: datetime | None = None
    created_on: datetime | None = None
    sms_list: list[SmsOrder] = Field(default_factory=list)
    page: int | None = None
    page_size: int | None = None
    total_elements: int | None = None
    has_next: bool | None = None


class InboundMessage(JibitModel):
    """Represent one inbound mobile-originated message."""

    id: UUID | str | None = None
    sender: str | None = None
    receptor: str | None = None
    message: str | None = None
    received_date_time: datetime | None = None


class InboundMessageResult(JibitModel):
    """Contain inbound messages for a requested date page."""

    result: list[InboundMessage] = Field(default_factory=list)


class _InboundQuery(JibitRequestModel):
    """Validate an inbound-message query."""

    from_date: datetime = Field(alias="from_date")
    to_date: datetime = Field(alias="to_date")
    page: int = Field(default=0, alias="page", ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        """Reject reversed date ranges."""
        if self.from_date > self.to_date:
            raise ValueError("from_date must not be later than to_date")
        return self


def redacted_params(params: dict[str, str]) -> dict[str, Any]:
    """Return pattern parameter structure without values for safe diagnostics."""
    return dict.fromkeys(params, "[REDACTED]")
