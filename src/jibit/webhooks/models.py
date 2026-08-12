"""Typed payment callback payloads."""

from __future__ import annotations

from pydantic import AliasChoices, Field

from jibit.models import JibitModel


class PaymentCallback(JibitModel):
    """Parse the minimal documented payment callback identifiers."""

    purchase_id: int = Field(gt=0, validation_alias=AliasChoices("purchaseId", "purchase_id"))
    client_reference_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("clientReferenceNumber", "client_reference_number"),
    )
