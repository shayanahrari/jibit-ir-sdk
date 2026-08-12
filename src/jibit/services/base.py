"""Shared response parsing for typed service facades."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from jibit.engine import RequestOptions
from jibit.exceptions import (
    ErrorContext,
    JibitError,
    JibitNetworkError,
    JibitResponseError,
    JibitServerError,
    JibitTimeoutError,
    JibitValidationError,
)
from jibit.logging import AuditEvent, AuditSink, EventName, StructuredLogger
from jibit.response import APIResponse, RawResponse

ModelT = TypeVar("ModelT", bound=BaseModel)


class RequestExecutor(Protocol):
    """Execute request options through authenticated or public infrastructure."""

    def execute(self, options: RequestOptions) -> RawResponse:
        """Execute one SDK request."""


class AuditedRequestExecutor:
    """Add safe application-owned audit events around a request executor."""

    def __init__(
        self,
        executor: RequestExecutor,
        *,
        audit_sink: AuditSink,
        logger: StructuredLogger,
        event_name: str,
    ) -> None:
        self._executor = executor
        self._audit_sink = audit_sink
        self._logger = logger
        self._event_name = event_name

    def execute(self, options: RequestOptions) -> RawResponse:
        """Execute a request and emit a data-minimized outcome event."""
        try:
            response = self._executor.execute(options)
        except JibitError as error:
            outcome = (
                "unknown"
                if isinstance(
                    error,
                    (JibitTimeoutError, JibitNetworkError, JibitServerError, JibitResponseError),
                )
                else "failed"
            )
            self._emit(
                options,
                correlation_id=error.context.correlation_id or "unavailable",
                outcome=outcome,
                metadata={
                    "error_type": type(error).__name__,
                    "error_code": error.context.error_code,
                    "status_code": error.context.status_code,
                },
            )
            raise
        self._emit(
            options,
            correlation_id=response.correlation_id,
            outcome="succeeded",
            metadata={"status_code": response.status_code},
        )
        return response

    def _emit(
        self,
        options: RequestOptions,
        *,
        correlation_id: str,
        outcome: str,
        metadata: Mapping[str, Any],
    ) -> None:
        event = AuditEvent(
            name=self._event_name,
            correlation_id=correlation_id,
            service=options.service.value,
            operation=options.operation,
            outcome=outcome,
            metadata=metadata,
        )
        try:
            self._audit_sink.emit(event)
        except Exception as exc:
            # Audit extensions must not alter an upstream operation's result.
            self._logger.emit(
                logging.ERROR,
                EventName.AUDIT_EMIT_FAILED,
                service=options.service.value,
                operation=options.operation,
                correlation_id=correlation_id,
                error_type=type(exc).__name__,
            )


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


def typed_request(
    executor: RequestExecutor,
    options: RequestOptions,
    model: type[ModelT],
) -> APIResponse[ModelT]:
    """Execute request options and validate their documented response model."""
    raw = executor.execute(options)
    return parse_model_response(
        raw,
        model,
        service=options.service.value,
        operation=options.operation,
        method=options.method,
        endpoint=options.path,
    )


def compact_values(values: Mapping[str, Any]) -> dict[str, Any]:
    """Remove optional query values without discarding explicit false or zero values."""
    return {key: value for key, value in values.items() if value is not None}


def validate_request(
    model: type[ModelT],
    values: Mapping[str, Any],
    *,
    service: str,
    operation: str,
    method: str,
    endpoint: str,
) -> ModelT:
    """Normalize Pydantic input errors into the public SDK exception hierarchy."""
    try:
        return model.model_validate(values)
    except ValidationError:
        raise JibitValidationError(
            "The request parameters are invalid",
            context=ErrorContext(
                service=service,
                operation=operation,
                method=method,
                endpoint=endpoint,
                retryable=False,
            ),
        ) from None


def request_validation_error(
    *, service: str, operation: str, method: str, endpoint: str, message: str
) -> JibitValidationError:
    """Create one structured local input error for a service facade."""
    return JibitValidationError(
        message,
        context=ErrorContext(
            service=service,
            operation=operation,
            method=method,
            endpoint=endpoint,
            retryable=False,
        ),
    )
