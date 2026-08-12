"""Shared Pydantic model behavior for public SDK contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


def _to_camel(value: str) -> str:
    """Convert a Python snake-case field name to the API's camel-case form."""
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class JibitModel(BaseModel):
    """Provide alias-aware, forward-compatible behavior for API response models."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="allow",
        populate_by_name=True,
    )

    def __repr__(self) -> str:
        """Avoid exposing financial or identity fields in incidental diagnostics."""
        return f"{type(self).__name__}([REDACTED])"

    def __str__(self) -> str:
        """Avoid exposing model payloads through implicit string conversion."""
        return repr(self)


class JibitRequestModel(JibitModel):
    """Reject unknown request fields and serialize documented API aliases."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
    )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-compatible request body without unset optional values."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")

    def to_query(self) -> dict[str, Any]:
        """Return URL-query values using the API's documented field names."""
        return self.to_payload()
