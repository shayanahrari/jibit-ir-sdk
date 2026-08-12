"""Typed Direct Debit mandate and collection models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, RootModel, model_validator
from typing_extensions import Self

from jibit.models import JibitModel, JibitRequestModel


class PeriodUnit(str, Enum):
    """Documented recurring mandate period units."""

    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    YEAR = "YEAR"


class MandateType(str, Enum):
    """Mandate initiation workflows supported by the service."""

    TIME_FRAME = "time-frame"
    SUBSCRIPTION = "subscription"
    ONE_TAP = "one-tap"


class CreateMandateRequest(JibitRequestModel):
    """Validate shared and workflow-specific mandate initiation fields."""

    creditor_mandate_reference: str = Field(
        alias="creditor_mandate_reference", min_length=10, max_length=50
    )
    debtor_bank: str = Field(alias="debtor_bank", min_length=1)
    maximum_amount: int = Field(alias="maximum_amount", gt=0)
    period: int = Field(alias="period", ge=1)
    period_unit: PeriodUnit = Field(alias="period_unit")
    start_date: str = Field(alias="start_date", pattern=r"^\d{4}-\d{2}-\d{2}$")
    expire_date: str = Field(alias="expire_date", pattern=r"^\d{4}-\d{2}-\d{2}$")
    mandate_reason: str | None = Field(default=None, alias="mandate_reason")
    debtor_firstname: str | None = Field(default=None, alias="debtor_firstname")
    debtor_lastname: str | None = Field(default=None, alias="debtor_lastname")
    debtor_national_code: str | None = Field(
        default=None, alias="debtor_national_code", pattern=r"^\d{10}$"
    )
    debtor_id_number: str | None = Field(default=None, alias="debtor_id_number")
    debtor_mobile_number: str | None = Field(default=None, alias="debtor_mobile_number")
    debtor_postal_code: str | None = Field(default=None, alias="debtor_postal_code")
    debtor_birthdate: str | None = Field(default=None, alias="debtor_birthdate")
    debtor_deposit_number: str | None = Field(default=None, alias="debtor_deposit_number")
    debtor_iban: str | None = Field(default=None, alias="debtor_iban", pattern=r"^IR\d{24}$")
    otp_requirement_status: str | None = Field(default=None, alias="otp_requirement_status")
    otp_condition: str | None = Field(default=None, alias="otp_condition")
    frequency: int | None = Field(default=None, alias="frequency", ge=1)
    retry: bool | None = Field(default=None, alias="retry")

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        """Reject a mandate whose expiry precedes its start date."""
        if self.expire_date < self.start_date:
            raise ValueError("expire_date must not precede start_date")
        return self


class InitiateMandateResult(JibitModel):
    """Return the mandate reference and customer redirect URL."""

    mandate_reference: str | None = None
    redirect_url: str | None = None


class CollectRequest(JibitRequestModel):
    """Validate one collection request under an existing mandate."""

    creditor_transaction_no: str = Field(
        alias="creditor_transaction_no", min_length=1, max_length=100
    )
    mandate_reference: str = Field(alias="mandate_reference", min_length=10, max_length=50)
    amount: int = Field(alias="amount", gt=0)
    otp: str | None = Field(default=None, alias="otp", min_length=1)


class TransactionResult(JibitModel):
    """Represent Direct Debit transaction state and provider references."""

    transaction_no: str | None = None
    creditor_transaction_no: str | None = None
    mandate_reference: str | None = None
    bank: str | None = None
    amount: str | None = None
    currency: str | None = None
    status: str | None = None
    collection_date_time: str | None = None
    created_date_time: str | None = None
    transaction_type: str | None = None
    payment_type: str | None = None
    debtor_deposit: str | None = None
    destination_deposit: str | None = None
    wage: str | None = None
    vat: str | None = None
    wage_pay_method: str | None = None
    description: str | None = None


class MandateResult(JibitModel):
    """Represent an existing mandate while preserving evolving provider fields."""

    mandate_reference: str | None = None
    creditor_mandate_reference: str | None = None
    status: str | None = None
    maximum_amount: int | None = None
    period: int | None = None
    period_unit: str | None = None
    frequency: int | None = None
    start_date: str | None = None
    expiration_date: str | None = None
    debtor_bank: str | None = None
    debtor_iban: str | None = None


class TransactionList(RootModel[list[TransactionResult]]):
    """Represent transactions associated with a subscription mandate."""

    def __repr__(self) -> str:
        return "TransactionList([REDACTED])"

    def __str__(self) -> str:
        return repr(self)


class ActiveBank(JibitModel):
    """Represent one active creditor bank."""

    name: str | None = None
    persian_name: str | None = None


class ActiveBankList(RootModel[list[ActiveBank]]):
    """Represent banks currently enabled for Direct Debit."""

    def __repr__(self) -> str:
        return "ActiveBankList([REDACTED])"

    def __str__(self) -> str:
        return repr(self)


class BlueBankCallback(JibitRequestModel):
    """Parse the documented Blue Bank callback body without trusting its source."""

    request_id: str
    additional_information: str
    event_type: str
    mandate_number: str
    mandate_status: str
    event_category: str
    transaction_status: str | None = None
    amount: int | None = None
    core_reference_no: str | None = None
    core_transaction_time: str | None = None

    def to_callback_data(self) -> dict[str, Any]:
        """Return validated callback data for an application-controlled handler."""
        return self.to_payload()
