"""Typed Cobank settlement request and response models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, RootModel

from jibit.models import JibitModel, JibitRequestModel


class CobankTransferType(str, Enum):
    """Transfer rails accepted by Cobank settlement creation."""

    NORMAL = "NORMAL"
    ACH = "ACH"
    RTGS = "RTGS"


class TransferReason(str, Enum):
    """Documented Central Bank transfer reason values."""

    SALARY = "VARIZ_HOGHOUGH"
    DEBT_PAYMENT = "TADIE_DOYOUN"
    MOVABLE_PROPERTY = "MOAMELAT_MANGHOUL"
    IMMOVABLE_PROPERTY = "MOAMELAT_GHEIR_MANGHOUL"
    CASH_MANAGEMENT = "MODIRIAT_NAGHDINEGI"
    CASH_MANAGEMENT_LEGACY = "MODIRIRAT_NAGHDINEGI"
    GOODS_PURCHASE = "KHARID_KALA"
    SERVICES_PURCHASE = "KHARID_KHADAMAT"


class CreateSettlementRequest(JibitRequestModel):
    """Validate one Cobank financial settlement submission."""

    record_track_id: UUID
    destination_iban: str = Field(pattern=r"^IR\d{24}$")
    amount: int = Field(gt=0)
    transfer_type: CobankTransferType | None = None
    transfer_reason: TransferReason | None = None
    source_iban: str | None = Field(default=None, pattern=r"^IR\d{24}$")
    payment_id: str | None = Field(default=None, max_length=100, pattern=r"^\d+$")
    request_description: str | None = Field(default=None, max_length=250)


class SettlementRecord(JibitModel):
    """Represent one bank-processing record within a settlement."""

    reference_number: str | None = None
    bank_reference_number: str | None = None
    track_id: str | None = None
    record_type: str | None = None
    source_account_iban: str | None = None
    destination_iban: str | None = None
    destination_account_number: str | None = None
    destination_first_name: str | None = None
    destination_last_name: str | None = None
    amount: int | None = None
    pay_id: str | None = None
    transfer_type: CobankTransferType | None = None
    request_channel: str | None = None
    process_mode: str | None = None
    state: str | None = None
    state_updated_at: datetime | None = None
    fail_reason: str | None = None
    fee_amount: int | None = None
    fee_status: str | None = None
    last_submit_success_at: datetime | None = None
    archived_record_reference_number: str | None = None
    estimated_settle_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SettlementResult(JibitModel):
    """Represent a Cobank settlement and all available processing records."""

    reference_number: str | None = None
    track_id: str | None = None
    owner_code: str | None = None
    request_channel: str | None = None
    type: str | None = None
    source_iban: str | None = None
    destination_iban: str | None = None
    total_amount: int | None = None
    prime_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    records: list[SettlementRecord] = Field(default_factory=list)


class SettlementBatchResult(RootModel[list[SettlementResult]]):
    """Represent a bounded batch-inquiry response."""

    def __repr__(self) -> str:
        return "SettlementBatchResult([REDACTED])"

    def __str__(self) -> str:
        return repr(self)


class SettlementSummary(JibitModel):
    """Represent one settlement without its detailed record list."""

    reference_number: str | None = None
    track_id: str | None = None
    owner_code: str | None = None
    request_channel: str | None = None
    type: str | None = None
    source_iban: str | None = None
    destination_iban: str | None = None
    total_amount: int | None = None
    prime_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SettlementPage(JibitModel):
    """Represent a page of Cobank settlements."""

    page_number: int = 0
    size: int = 0
    number_of_elements: int = 0
    has_next: bool = False
    has_previous: bool = False
    elements: list[SettlementSummary] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MerchantAccountList(RootModel[list[dict[str, Any]]]):
    """Keep evolving Cobank account configuration records in a secret-safe container."""

    def __repr__(self) -> str:
        return "MerchantAccountList([REDACTED])"

    def __str__(self) -> str:
        return repr(self)


class ReceiptState(str, Enum):
    """Cobank public receipt-link states."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ReceiptLinkResult(JibitModel):
    """Represent the state and URL of a Cobank public receipt."""

    receipt_link: str | None = None
    state: ReceiptState
