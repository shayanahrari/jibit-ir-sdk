"""Typed and raw response containers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from jibit.exceptions import ErrorContext, JibitResponseError

ResponseT = TypeVar("ResponseT")


@dataclass(frozen=True, slots=True)
class RawResponse:
    """Expose transport-neutral response data for advanced consumers."""

    status_code: int
    headers: dict[str, str]
    content: bytes
    correlation_id: str

    @property
    def text(self) -> str:
        """Decode response bytes with a safe replacement strategy."""
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Decode JSON or raise a structured response error."""
        try:
            return json.loads(self.content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JibitResponseError(
                "The upstream response is not valid JSON",
                context=ErrorContext(
                    status_code=self.status_code,
                    correlation_id=self.correlation_id,
                ),
            ) from exc


@dataclass(frozen=True, slots=True)
class APIResponse(Generic[ResponseT]):
    """Pair a typed result with its raw HTTP response."""

    data: ResponseT
    raw: RawResponse


@dataclass(frozen=True, slots=True)
class StatusResult:
    """Represent success for an operation without a documented response schema."""

    success: bool
    status_code: int
    raw_body: bytes | None = None
