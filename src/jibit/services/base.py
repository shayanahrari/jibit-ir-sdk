"""Shared response parsing for typed service facades."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from jibit.exceptions import ErrorContext, JibitResponseError
from jibit.response import APIResponse, RawResponse

ModelT = TypeVar("ModelT", bound=BaseModel)


def parse_model_response(
    raw: RawResponse,
    model: type[ModelT],
    *,
    service: str,
    operation: str,
    method: str,
    endpoint: str,
) -> APIResponse[ModelT]:
    """Validate an upstream JSON result and preserve its raw response."""
    try:
        data = model.model_validate(raw.json())
    except (JibitResponseError, ValidationError, TypeError):
        raise JibitResponseError(
            "The upstream response does not match the documented contract",
            context=ErrorContext(
                service=service,
                operation=operation,
                method=method,
                endpoint=endpoint,
                status_code=raw.status_code,
                correlation_id=raw.correlation_id,
                retryable=False,
            ),
        ) from None
    return APIResponse(data=data, raw=raw)
