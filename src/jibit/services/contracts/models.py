"""Typed MzaHub contract lifecycle models."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from enum import Enum
from ipaddress import IPv4Address, IPv6Address

from pydantic import Field, HttpUrl, field_validator, model_validator
from typing_extensions import Self

from jibit.models import JibitModel, JibitRequestModel


class ContractStatus(str, Enum):
    """Documented MzaHub contract states."""

    NOT_SIGNED = "NOT_SIGNED"
    SIGNED_BY_ALL_SIGNERS = "SIGNED_BY_ALL_SIGNERS"
    SUSPENDED_WAITING_FOR_BALANCE = "SUSPENDED_WAITING_FOR_BALANCE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class Signer(JibitRequestModel):
    """Represent one natural signer and optional legal-entity relationship."""

    national_code: str = Field(pattern=r"^\d{10}$")
    birth_date: str = Field(min_length=1)
    mobile_number: str | None = None
    priority: int | None = Field(default=None, ge=0)
    x1: int | None = Field(default=None, ge=0)
    x2: int | None = Field(default=None, ge=0)
    y1: int | None = Field(default=None, ge=0)
    y2: int | None = Field(default=None, ge=0)
    page_sign_selection: str | None = None
    dependent_legal_national_code: str | None = None
    dependent_legal_name: str | None = None

    @model_validator(mode="after")
    def validate_legal_dependency(self) -> Self:
        """Require both legal-entity fields or neither."""
        if (self.dependent_legal_national_code is None) != (self.dependent_legal_name is None):
            raise ValueError("both dependent legal entity fields are required")
        return self

    def to_provider_payload(self) -> dict[str, object]:
        """Build the provider's nested signer shape."""
        natural = self.to_payload()
        dependent_code = natural.pop("dependentLegalNationalCode", None)
        dependent_name = natural.pop("dependentLegalName", None)
        result: dict[str, object] = {"naturalSigner": natural}
        if dependent_code is not None and dependent_name is not None:
            result["dependentTo"] = {
                "nationalCode": dependent_code,
                "legalName": dependent_name,
            }
        return result


class InitiateContractRequest(JibitRequestModel):
    """Validate a base64 PDF contract and its reconciliation reference."""

    track_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    base64_file: str = Field(min_length=1, max_length=14_000_000)
    redirect_url: HttpUrl
    signers: tuple[Signer, ...] = Field(min_length=1, max_length=10)
    expire_at: datetime | None = None
    description: str | None = Field(default=None, max_length=1000)
    signature_appearance: str | None = None

    @field_validator("base64_file")
    @classmethod
    def require_valid_pdf(cls, value: str) -> str:
        """Reject malformed or non-PDF payloads before sending sensitive content."""
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("base64_file must contain valid base64") from None
        if not decoded.startswith(b"%PDF-"):
            raise ValueError("base64_file must contain a PDF document")
        return value

    def to_provider_payload(self) -> dict[str, object]:
        """Serialize the nested signer form documented by MzaHub."""
        payload = self.to_payload()
        payload["signers"] = [signer.to_provider_payload() for signer in self.signers]
        return payload


class ContractSummary(JibitModel):
    """Represent stable high-level contract state fields."""

    id: int | None = None
    track_id: str | None = None
    short_track_id: str | None = None
    status: ContractStatus | None = None
    receipt_code: str | None = None
    initiator: str | None = None
    expire_at: datetime | None = None
    redirect_url: str | None = None
    signature_appearance: str | None = None
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    version: int | None = None


class InitiateContractResult(JibitModel):
    """Return signing link and created contract summary."""

    link: str | None = None
    contract: ContractSummary | None = None


class ContractResult(ContractSummary):
    """Represent a contract inquiry with flexible signer details."""

    signs: list[dict[str, object]] = Field(default_factory=list)


class SignedDocument(JibitModel):
    """Contain signed-document bytes without exposing them in representations."""

    content: bytes = Field(repr=False)
    content_type: str | None = None
    filename: str | None = Field(default=None, repr=False)


class RealIp(JibitRequestModel):
    """Validate the real client IP required by MzaHub requests."""

    value: IPv4Address | IPv6Address
