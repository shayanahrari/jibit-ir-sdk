"""Typed request and response models for Transferor v2."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, HttpUrl, RootModel, model_validator
from typing_extensions import Self

from jibit.models import JibitModel, JibitRequestModel


class TransferMode(str, Enum):
    """Documented bank transfer rails."""

    ACH = "ACH"
    NORMAL = "NORMAL"
    RTGS = "RTGS"


class SubmissionMode(str, Enum):
    """Documented batch acceptance modes."""

    BATCH = "BATCH"
    TRANSFER = "TRANSFER"


class TransferCurrency(str, Enum):
    """Currency labels accepted by the Transferor contract."""

    IRR = "IRR"
    RIALS = "RIALS"
    TOMAN = "TOMAN"


class TransferState(str, Enum):
    """Known Transferor lifecycle states across available contracts."""

    INITIALIZED = "INITIALIZED"
    FEE_COMPUTED = "FEE_COMPUTED"
    CORE_SUBMITTED = "CORE_SUBMITTED"
    ON_HOLD = "ON_HOLD"
    DESTINATION_IDENTIFIED = "DESTINATION_IDENTIFIED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    IN_PROGRESS = "IN_PROGRESS"
    TRANSFERRED = "TRANSFERRED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    ON_HOLD_BALANCES_NOT_ENOUGH = "ON_HOLD_BALANCES_NOT_ENOUGH"
    ON_HOLD_WAIT_FOR_MANUAL_SUBMISSION = "ON_HOLD_WAIT_FOR_MANUAL_SUBMISSION"
    ON_HOLD_WAIT_FOR_VERIFY = "ON_HOLD_WAIT_FOR_VERIFY"
    MANUALLY_FAILED = "MANUALLY_FAILED"


class TransferItemRequest(JibitRequestModel):
    """Describe one transfer in a Transferor batch submission."""

    transfer_id: str = Field(alias="transferID", min_length=1, max_length=100)
    transfer_mode: TransferMode = TransferMode.ACH
    destination: str = Field(pattern=r"^IR\d{24}$")
    destination_first_name: str | None = Field(default=None, max_length=100)
    destination_last_name: str | None = Field(default=None, max_length=100)
    amount: int = Field(gt=0)
    currency: TransferCurrency = TransferCurrency.IRR
    description: str = Field(min_length=1, max_length=250)
    metadata: str | None = Field(default=None, max_length=2000)
    notify_url: HttpUrl | None = Field(default=None, alias="notifyURL")
    cancellable: bool = True
    payment_id: str | None = Field(default=None, alias="paymentID", pattern=r"^\d+$")


class SubmitBatchRequest(JibitRequestModel):
    """Submit one non-empty Transferor batch with a caller-controlled reference."""

    batch_id: str = Field(alias="batchID", min_length=1, max_length=100)
    submission_mode: SubmissionMode = SubmissionMode.BATCH
    transfers: tuple[TransferItemRequest, ...] = Field(min_length=1)


class TransferRecord(JibitModel):
    """Represent a submitted Transferor transfer and its reconciliation state."""

    transfer_id: str | None = Field(default=None, alias="transferID")
    transfer_mode: TransferMode | None = None
    destination: str | None = None
    destination_first_name: str | None = None
    destination_last_name: str | None = None
    amount: int | None = None
    currency: str | None = None
    description: str | None = None
    metadata: str | None = None
    notify_url: str | None = Field(default=None, alias="notifyURL")
    cancellable: bool | None = None
    payment_id: str | None = Field(default=None, alias="paymentID")
    bank_transfer_id: str | None = Field(default=None, alias="bankTransferID")
    state: TransferState | None = None
    fail_reason: str | None = None
    channel_manager_processing_type: TransferMode | None = None
    bank_submitted_time: datetime | None = None
    fee_currency: str | None = None
    fee_amount: int | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None


class SubmitBatchResult(JibitModel):
    """Represent accepted and rejected portions of a Transferor submission."""

    submitted_count: int = 0
    total_amount_transferred: int = 0
    rejections: list[TransferRecord] = Field(default_factory=list)


class TransferInquiryResult(JibitModel):
    """Represent a reconciled batch or transfer inquiry."""

    batch_id: str | None = Field(default=None, alias="batchID")
    transfers: list[TransferRecord] = Field(default_factory=list)


class TransferFilterResult(JibitModel):
    """Normalize list and envelope forms returned by transfer filtering."""

    transfers: list[TransferRecord] = Field(default_factory=list)
    page: int | None = None
    size: int | None = None
    total: int | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_list_response(cls, value: Any) -> Any:
        """Accept the list form used by some Transferor deployments."""
        return {"transfers": value} if isinstance(value, list) else value


class ReceiptResult(JibitModel):
    """Expose the temporary public receipt link returned by Transferor."""

    public_link: str


class BalanceEntry(JibitModel):
    """Represent one service wallet balance."""

    balance_type: str
    currency: str
    amount: int


class BalanceResult(JibitModel):
    """Represent Transferor wallet totals and categorized balances."""

    balance: int | None = None
    settleable_balance: int | None = None
    balances: list[BalanceEntry] = Field(default_factory=list)


class UsageReportEntry(JibitModel):
    """Represent daily volume for one transfer state."""

    state: str
    currency: str
    sum: int
    count: int


class UsageReportResult(JibitModel):
    """Contain a Transferor daily usage report."""

    report: list[UsageReportEntry] = Field(default_factory=list)


class BankList(RootModel[list[str]]):
    """Represent supported or currently active bank identifiers."""

    def __repr__(self) -> str:
        return "BankList([REDACTED])"

    def __str__(self) -> str:
        return repr(self)


class BatchGeneratorRequest(JibitRequestModel):
    """Describe a transfer that the provider may split into generated batches."""

    submission_mode: SubmissionMode = SubmissionMode.BATCH
    transfer_mode: TransferMode
    destination: str = Field(pattern=r"^IR\d{24}$")
    amount: int = Field(gt=0)
    currency: TransferCurrency = TransferCurrency.IRR
    description: str | None = Field(default=None, max_length=250)
    metadata: str | None = Field(default=None, max_length=2000)
    notify_url: HttpUrl | None = Field(default=None, alias="notifyURL")
    cancellable: bool = True
    payment_id: str | None = Field(default=None, alias="paymentID", pattern=r"^\d+$")


class TransferSelector(JibitRequestModel):
    """Require a batch reference, a transfer reference, or both for reconciliation."""

    batch_id: str | None = Field(default=None, alias="batchID", min_length=1)
    transfer_id: str | None = Field(default=None, alias="transferID", min_length=1)

    @model_validator(mode="after")
    def require_reference(self) -> Self:
        """Reject requests that cannot identify any upstream transfer."""
        if self.batch_id is None and self.transfer_id is None:
            raise ValueError("batch_id or transfer_id is required")
        return self
