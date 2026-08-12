"""Typed request and response models for Identicator inquiry APIs."""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator
from typing_extensions import Self

from jibit.models import JibitModel, JibitRequestModel


class IbanOwner(JibitModel):
    """Represent one documented IBAN owner."""

    first_name: str | None = None
    last_name: str | None = None


class IbanInfo(JibitModel):
    """Represent documented IBAN, bank, account, status, and owner details."""

    bank: str | None = None
    deposit_number: str | None = None
    iban: str | None = None
    status: str | None = None
    owners: list[IbanOwner] = Field(default_factory=list)


class DepositToIbanInfo(JibitModel):
    """Represent the result of converting an account number to an IBAN."""

    bank: str | None = None
    iban: str | None = None


class DepositInquiryResponse(JibitModel):
    """Return account and optional IBAN details for a deposit inquiry."""

    number: str
    deposit_to_iban_info: DepositToIbanInfo | None = Field(default=None, alias="depositToIBANInfo")
    iban_info: IbanInfo | None = Field(default=None, alias="ibanInfo")


class IbanInquiryResponse(JibitModel):
    """Return documented owner and account details for an IBAN."""

    value: str
    iban_info: IbanInfo | None = Field(default=None, alias="ibanInfo")


class CardInfo(JibitModel):
    """Represent documented bank-card inquiry details."""

    bank: str | None = None
    type: str | None = None
    owner_name: str | None = None
    owners: list[IbanOwner] = Field(default_factory=list)
    deposit_number: str | None = None
    iban: str | None = None
    status: str | None = None


class DepositInfo(JibitModel):
    """Represent account data returned during card conversion."""

    bank: str | None = None
    deposit_number: str | None = None
    card_info: CardInfo | None = None


class CardInquiryResponse(JibitModel):
    """Return card metadata and requested conversion details."""

    number: str
    type: str | None = None
    card_info: CardInfo | None = None
    deposit_info: DepositInfo | None = None
    iban_info: IbanInfo | None = Field(default=None, alias="ibanInfo")


class MatchingRequest(JibitRequestModel):
    """Select one documented pair of identifiers for ownership matching."""

    iban: str | None = None
    card_number: str | None = None
    bank: str | None = None
    deposit_number: str | None = None
    national_code: str | None = None
    legal_national_code: str | None = None
    birth_date: str | None = None
    name: str | None = None
    mobile_number: str | None = None
    fida: str | None = None
    passport_number: str | None = None

    @model_validator(mode="after")
    def validate_documented_combination(self) -> Self:
        """Reject combinations the matching router does not document."""
        present = {
            name for name in type(self).model_fields if getattr(self, name, None) is not None
        }
        allowed = (
            {"iban", "name"},
            {"iban", "national_code"},
            {"iban", "national_code", "birth_date"},
            {"iban", "legal_national_code"},
            {"card_number", "name"},
            {"card_number", "national_code"},
            {"card_number", "national_code", "birth_date"},
            {"deposit_number", "bank", "name"},
            {"deposit_number", "bank", "national_code"},
            {"deposit_number", "bank", "national_code", "birth_date"},
            {"national_code", "mobile_number"},
            {"fida", "passport_number"},
        )
        if present not in allowed:
            raise ValueError("the identifier combination is not documented for matching")
        return self


class MatchingResponse(JibitModel):
    """Return whether the two supplied identifiers match."""

    matched: bool


class AddressInfo(JibitModel):
    """Represent the documented address fields for a postal code."""

    postal_code: str | None = None
    address: str | None = None
    province: str | None = None
    district: str | None = None
    city: str | None = None
    street: str | None = None
    floor: str | None = None
    number: str | None = None


class PostalResponse(JibitModel):
    """Return address information for a postal code."""

    code: str
    address_info: AddressInfo | None = None


class WgsInfo(JibitModel):
    """Represent documented coordinates for a postal code."""

    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class WgsResponse(JibitModel):
    """Return WGS coordinates for a postal code."""

    code: str
    wgs_info: WgsInfo | None = None


class IdentityInfo(JibitModel):
    """Represent documented civil identity information."""

    national_code: str | None = None
    birth_date: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    father_name: str | None = None
    gender: str | None = None
    identification_number: int | None = None
    identification_serial_code: str | None = None
    identification_serial_number: int | None = None
    birth_place_code: int | None = None
    birth_place: str | None = None
    alive: bool | None = None
    death_date: str | None = None
    provider_tracker_id: str | None = None
    photo: str | None = None


class IdentityResponse(JibitModel):
    """Return civil identity information for a national code and birth date."""

    national_code: str
    birth_date: str
    identity_info: IdentityInfo | None = None


class IdentitySimilarityRequest(JibitRequestModel):
    """Validate a civil identity name-similarity request."""

    national_code: str = Field(min_length=10, max_length=10)
    birth_date: str = Field(min_length=8, max_length=10)
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    father_name: str | None = None

    @model_validator(mode="after")
    def require_name(self) -> Self:
        """Require at least one name value for a meaningful comparison."""
        if not any((self.first_name, self.last_name, self.full_name, self.father_name)):
            raise ValueError("at least one name field is required")
        return self


class IdentitySimilarityResponse(JibitModel):
    """Return documented name similarity percentages."""

    first_name_similarity_percentage: int | None = Field(default=None, ge=0, le=100)
    last_name_similarity_percentage: int | None = Field(default=None, ge=0, le=100)
    full_name_similarity_percentage: int | None = Field(default=None, ge=0, le=100)
    father_name_similarity_percentage: int | None = Field(default=None, ge=0, le=100)


class FlexibleInquiryResponse(JibitModel):
    """Preserve documented but deeply nested inquiry results as typed envelope data."""

    national_code: str | None = None
    fida: str | None = None
    code: str | None = None
    registered: bool | None = None
    legal_identity_info: dict[str, Any] | None = None
    foreigner_identity_info: dict[str, Any] | None = None
    military_service_qualification_info: dict[str, Any] | None = None
    corporation_identity_info: dict[str, Any] | None = None
    cheque_info: dict[str, Any] | None = None


class IdenticatorBalance(JibitModel):
    """Represent one Identicator ledger balance."""

    balance_type: str
    amount: int
    currency: str


class BalancesResponse(JibitModel):
    """Return all Identicator balances visible to the configured client."""

    balances: list[IdenticatorBalance] = Field(default_factory=list)


class DailyUsageReportResponse(JibitModel):
    """Preserve documented daily service usage rows for operational reporting."""

    report: list[dict[str, Any]] = Field(default_factory=list)


class ServiceAvailabilityResponse(JibitModel):
    """Preserve the provider availability report without inventing dynamic keys."""

    availability_report: dict[str, Any] = Field(default_factory=dict)


class IdenticatorHealthResponse(JibitModel):
    """Represent documented service health and component checks."""

    outcome: str
    checks: list[dict[str, Any]] = Field(default_factory=list)
