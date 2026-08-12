"""Shared public types used across the SDK."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ServiceName(str, Enum):
    """Identify a Jibit API service and its isolated authentication scope."""

    PAYMENT_GATEWAY = "payment_gateway"
    TRANSFERS = "transfers"
    COBANK = "cobank"
    IDENTICATOR = "identicator"
    KYC = "kyc"
    DIRECT_DEBIT = "direct_debit"
    SMS = "sms"
    CONTRACTS = "contracts"


class ContentPartType(str, Enum):
    """Describe one transport-neutral multipart form value."""

    FIELD = "field"
    FILE = "file"


@dataclass(frozen=True, slots=True, repr=False)
class MultipartPart:
    """Represent one text or file part without exposing its value in representations."""

    name: str
    kind: ContentPartType
    value: str | bytes
    filename: str | None = None
    content_type: str | None = None

    def __repr__(self) -> str:
        return (
            f"MultipartPart(name={self.name!r}, kind={self.kind.value!r}, "
            f"has_filename={self.filename is not None}, content_length={len(self.value)})"
        )
