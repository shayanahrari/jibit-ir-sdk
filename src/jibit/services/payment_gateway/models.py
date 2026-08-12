"""Typed request and response models for Payment Gateway v3."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator
from typing_extensions import Self

from jibit.models import JibitModel, JibitRequestModel


class Currency(str, Enum):
    """Currencies documented by Payment Gateway v3."""

    IRR = "IRR"


class PurchaseState(str, Enum):
    """Documented high-level purchase lifecycle states."""

    MANUALLY_SUCCESS = "MANUALLY_SUCCESS"
    SUCCESS = "SUCCESS"
    REVERSED = "REVERSED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    EXPIRED = "EXPIRED"
    IN_PROGRESS = "IN_PROGRESS"
    READY_TO_VERIFY = "READY_TO_VERIFY"


class PurchaseHistoryStatus(str, Enum):
    """States accepted by the purchase-history filtering endpoint."""

    MANUALLY_SUCCESS = "MANUALLY_SUCCESS"
    REVERSED = "REVERSED"
    UNKNOWN = "UNKNOWN"


class VerifyStatus(str, Enum):
    """Possible verification outcomes."""

    SUCCESSFUL = "SUCCESSFUL"
    ALREADY_VERIFIED = "ALREADY_VERIFIED"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ReverseStatus(str, Enum):
    """Possible purchase reversal outcomes."""

    SUCCESSFUL = "SUCCESSFUL"
    ALREADY_REVERSED = "ALREADY_REVERSED"
    NOT_REVERSIBLE = "NOT_REVERSIBLE"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class SettlementState(str, Enum):
    """Documented settlement lifecycle states."""

    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"
    SETTLED = "SETTLED"
    OBSOLETE = "OBSOLETE"
    EARLY_SETTLED = "EARLY_SETTLED"


class HealthStatus(str, Enum):
    """Documented health indicator values."""

    UP = "UP"
    DOWN = "DOWN"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class TerminalType(str, Enum):
    """Documented terminal operating modes."""

    NORMAL = "NORMAL"
    PAYMENT_FACILITATION = "PAYMENT_FACILITATION"
    AUTO_SETTLING_PF = "AUTO_SETTLING_PF"


class TerminalSwitching(JibitRequestModel):
    """Configure prioritized terminals for a purchase."""

    terminal_ids: tuple[str, ...] = Field(min_length=1)
    auto_switching: bool = True


class CreatePurchaseRequest(JibitRequestModel):
    """Validate values used to initialize a payment purchase."""

    amount: int = Field(ge=5_000)
    callback_url: HttpUrl = Field(max_length=1024)
    client_reference_number: str = Field(min_length=1, max_length=50)
    wage: int = Field(default=0, ge=0)
    currency: Currency = Currency.IRR
    payer_mobile_number: str | None = None
    check_payer_mobile_number: bool = False
    payer_card_number: str | None = None
    payer_card_numbers: tuple[str, ...] | None = None
    payer_national_code: str | None = None
    description: str | None = Field(default=None, max_length=256)
    switching: TerminalSwitching | None = None
    additional_data: dict[str, Any] | None = None
    user_identifier: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_purchase_constraints(self) -> Self:
        """Enforce cross-field rules published for purchase creation."""
        if self.wage * 100 > self.amount * 15:
            raise ValueError("wage must not exceed 15 percent of amount")
        if self.check_payer_mobile_number and not self.payer_mobile_number:
            raise ValueError("payer_mobile_number is required when mobile checking is enabled")
        if self.payer_card_number and self.payer_card_numbers:
            raise ValueError("payer_card_number and payer_card_numbers are mutually exclusive")
        if self.payer_card_numbers and len(set(self.payer_card_numbers)) != len(
            self.payer_card_numbers
        ):
            raise ValueError("payer_card_numbers must contain unique values")
        return self


class CreatePurchaseResult(JibitModel):
    """Return identifiers and the redirect URL for a created purchase."""

    purchase_id: int
    purchase_id_str: str | None = None
    client_reference_number: str
    psp_switching_url: HttpUrl
    fee: int | None = None
    affiliate_fee: int | None = None
    shaparak_fee: int | None = None
    net_amount: int | None = None
    payable_amount: int | None = None
    currency: Currency = Currency.IRR


class VerifyPurchaseResult(JibitModel):
    """Return the normalized outcome of purchase verification."""

    status: VerifyStatus


class _PurchaseIdentifierRequest(JibitRequestModel):
    """Require at least one supported purchase identifier."""

    client_reference_number: str | None = Field(default=None, min_length=1, max_length=50)
    purchase_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_purchase_identifier(self) -> Self:
        if self.client_reference_number is None and self.purchase_id is None:
            raise ValueError("client_reference_number or purchase_id is required")
        return self


class ReversePurchaseRequest(_PurchaseIdentifierRequest):
    """Identify a purchase that should be reversed."""


class ReversePurchaseResult(JibitModel):
    """Return the normalized outcome of purchase reversal."""

    status: ReverseStatus


class RefundPurchaseRequest(_PurchaseIdentifierRequest):
    """Identify a purchase and optional amount for a refund request."""

    amount: int | None = Field(default=None, gt=0)
    cancellable: bool = False


class RefundPurchaseResult(JibitModel):
    """Return transfer identifiers assigned to a refund submission."""

    refund_id: int
    partial_refund_index: int | None = Field(default=None, deprecated=True)
    batch_id: str | None = None
    transfer_id: str | None = None


class RefundActionRequest(JibitRequestModel):
    """Optionally select one partial refund transfer for an action."""

    transfer_id: str | None = Field(default=None, min_length=1)


class PspFailReason(JibitModel):
    """Describe a failure returned by a payment service provider."""

    code: int | None = None
    description: str | None = None
    psp_error: str | None = Field(default=None, deprecated=True)


class RefundTransfer(JibitModel):
    """Describe one transfer belonging to a payment refund."""

    refund_id: int | None = None
    partial_refund_index: int | None = Field(default=None, deprecated=True)
    transfer_mode: str | None = None
    destination: str | None = None
    destination_first_name: str | None = None
    destination_last_name: str | None = None
    amount: int | None = None
    currency: str | None = None
    description: str | None = None
    metadata: str | None = None
    cancellable: bool | None = None
    state: str | None = None
    fail_reason: str | None = None
    fee_currency: str | None = None
    fee_amount: int | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    notify_url: str | None = Field(default=None, alias="notifyURL")
    payment_id: str | None = Field(default=None, alias="paymentID")
    bank_transfer_id: str | None = Field(default=None, alias="bankTransferID")
    transfer_id: str | None = Field(default=None, alias="transferID")


class RefundInquiryResult(JibitModel):
    """Return the current transfer state for a payment refund."""

    transfers: list[RefundTransfer] = Field(default_factory=list)
    batch_id: str | None = Field(default=None, alias="batchID")
    refunded_amount: int | None = None


class DetailedPurchase(JibitModel):
    """Represent documented purchase inquiry fields without exposing them to logs."""

    purchase_id: int
    purchase_id_str: str | None = None
    client_code: str | None = None
    amount: int | None = None
    wage: int | None = None
    fee: int | None = None
    fee_payment_type: str | None = None
    shaparak_fee: int | None = None
    reseller_code: str | None = None
    affiliate_fee: int | None = None
    net_amount: int | None = None
    currency: Currency | None = None
    callback_url: str | None = None
    state: PurchaseState | None = None
    client_reference_number: str | None = None
    psp_name: str | None = None
    psp_rrn: str | None = None
    psp_reference_number: str | None = None
    psp_trace_number: str | None = None
    expiration_date: datetime | None = None
    user_identifier: str | None = None
    payer_mobile_number: str | None = None
    payer_card_number: str | None = None
    payer_national_code: str | None = None
    description: str | None = None
    additional_data: dict[str, Any] | None = None
    psp_masked_card_number: str | None = None
    psp_hashed_card_number: str | None = None
    psp_card_owner: str | None = None
    psp_fail_reason: str | None = Field(default=None, deprecated=True)
    psp_fail_reasons: list[PspFailReason] = Field(default_factory=list)
    init_payer_ip: str | None = None
    redirect_payer_ip: str | None = None
    psp_settled: bool | None = None
    refunded: bool | None = None
    refund_inquiry_result: RefundInquiryResult | None = None
    refundable_amount: int | None = None
    created_at: datetime | None = None
    billing_date: datetime | None = None
    verified_at: datetime | None = None
    psp_settled_at: datetime | None = None
    settlement_id: int | None = None
    has_contradiction: bool | None = None


class PurchasePage(JibitModel):
    """Represent one page returned by purchase filtering."""

    page_number: int
    size: int
    number_of_elements: int
    has_next: bool
    has_previous: bool
    elements: list[DetailedPurchase] = Field(default_factory=list)


class PurchaseFilter(JibitRequestModel):
    """Validate purchase filtering and page bounds before network I/O."""

    purchase_id: int | None = Field(default=None, gt=0)
    status: PurchaseState | None = None
    client_reference_number: str | None = None
    psp_reference_number: str | None = None
    psp_rrn: str | None = None
    psp_trace_number: str | None = None
    user_identifier: str | None = None
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    page: int | None = Field(default=None, ge=1, le=20)
    size: int | None = Field(default=None, ge=1, le=250)

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        """Require an ordered range when both date bounds are supplied."""
        if self.from_ is not None and self.to is not None and self.from_ >= self.to:
            raise ValueError("from_ must be earlier than to")
        return self


class DetailedPurchaseHistory(JibitModel):
    """Represent one documented purchase state transition."""

    purchase_id: int
    client_reference_number: str | None = Field(default=None, alias="clientRefNum")
    new_state: PurchaseState
    created_at: datetime


class PurchaseHistoryPage(JibitModel):
    """Represent identifier-based purchase-history pagination."""

    size: int
    total_count: int | None = None
    has_next: bool
    next_page_id: str | None = None
    elements: list[DetailedPurchaseHistory] = Field(default_factory=list)


class PurchaseHistoryFilter(JibitRequestModel):
    """Validate history criteria including its documented three-hour range limit."""

    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    purchase_id: int | None = Field(default=None, gt=0)
    statuses: tuple[PurchaseHistoryStatus, ...] | None = None
    next_page_id: int | None = Field(default=None, gt=0)
    page: int | None = Field(default=None, ge=1, le=10)
    size: int | None = Field(default=None, ge=1, le=20_000)

    @model_validator(mode="after")
    def validate_history_criteria(self) -> Self:
        """Reject empty, incomplete, reversed, or overlong time criteria."""
        if (self.from_ is None and self.to is not None) or (
            self.from_ is not None and self.to is None
        ):
            raise ValueError("from_ and to must be supplied together")
        if self.from_ is not None and self.to is not None:
            if self.from_ >= self.to:
                raise ValueError("from_ must be earlier than to")
            if self.to - self.from_ >= timedelta(hours=3):
                raise ValueError("the history date range must be shorter than three hours")
        if self.purchase_id is None and self.statuses is None and self.from_ is None:
            raise ValueError("at least one history criterion is required")
        if self.statuses is not None and not self.statuses:
            raise ValueError("statuses must not be empty")
        return self


class DetailedSettlement(JibitModel):
    """Represent a documented PPG settlement record."""

    client_code: str | None = None
    client_name: str | None = None
    settlement_id: int
    terminal_id: UUID | None = None
    file_name: str | None = None
    state: SettlementState | None = None
    amount: int | None = None
    wage: int | None = None
    direct_settlement: bool | None = None
    currency: Currency | None = None
    cutoff: str | None = None
    acceptor_code: str | None = None
    ledger_account: str | None = None
    iin: int | None = None
    payment_facilitator_iban: str | None = None
    settlement_iban: str | None = None
    reseller_code: str | None = None
    affiliate_fee: int | None = None
    shaparak_fail_reason: str | None = None
    shaparak_reference_number: str | None = None
    shaparak_tracking_number: str | None = None
    shaparak_transaction_id: str | None = None
    variance: int | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    settled_at: datetime | None = None


class SettlementPage(JibitModel):
    """Represent one page returned by settlement filtering."""

    page_number: int
    size: int
    number_of_elements: int
    has_next: bool
    has_previous: bool
    elements: list[DetailedSettlement] = Field(default_factory=list)


class SettlementFilter(JibitRequestModel):
    """Validate settlement filtering and page bounds."""

    settlement_id: int | None = Field(default=None, gt=0)
    page: int | None = Field(default=None, ge=1, le=20)
    size: int | None = Field(default=None, ge=1, le=250)


class Terminal(JibitModel):
    """Represent a PPG terminal available to the configured client."""

    natural_id: str
    client_code: str | None = None
    client_name: str | None = None
    psp_name: str | None = None
    psp_terminal_id: str | None = None
    psp_merchant_number: str | None = None
    type: TerminalType | None = None
    direct_settlement: bool | None = None
    priority: int | None = None
    is_auto_verify_enabled: bool | None = None
    is_check_payer_mobile_number_active: bool | None = None
    is_check_payer_national_code_active: bool | None = None
    is_single_card_freeze_active: bool | None = None
    created_at: datetime | None = None


class TerminalCollection(JibitModel):
    """Wrap terminals returned by the PPG terminal-list endpoint."""

    elements: list[Terminal] = Field(default_factory=list)


class Balance(JibitModel):
    """Represent one PPG ledger balance."""

    balance_type: str
    amount: int
    currency: Currency


class ClientBalances(JibitModel):
    """Wrap all ledger balances visible to the configured client."""

    balances: list[Balance] = Field(default_factory=list)


class HealthResult(JibitModel):
    """Represent PPG and downstream PSP health indicators."""

    status: HealthStatus
    psp_status_map: dict[str, HealthStatus] = Field(default_factory=dict)
