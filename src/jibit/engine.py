"""Central request execution, correlation, logging, retries, and error mapping."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from jibit.config import JibitConfig
from jibit.exceptions import (
    ErrorContext,
    JibitAuthenticationError,
    JibitAuthorizationError,
    JibitBusinessError,
    JibitError,
    JibitNetworkError,
    JibitRateLimitError,
    JibitResponseError,
    JibitServerError,
    JibitTimeoutError,
    JibitValidationError,
)
from jibit.logging import EventName, StructuredLogger
from jibit.response import RawResponse
from jibit.retry import OperationSafety, RetryPolicy
from jibit.transport import (
    HTTPTransport,
    TransportNetworkError,
    TransportRequest,
    TransportResponse,
    TransportTimeoutError,
)
from jibit.types import ServiceName


@dataclass(frozen=True, slots=True)
class RequestOptions:
    """Describe the operation-level behavior required by the request engine."""

    service: ServiceName
    operation: str
    method: str
    path: str
    safety: OperationSafety
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    params: Mapping[str, Any] | None = field(default=None, repr=False)
    json: Any = field(default=None, repr=False)
    content: bytes | None = field(default=None, repr=False)
    idempotency_key: str | None = None
    correlation_id: str | None = None


class RequestEngine:
    """Execute requests with conservative retries and structured diagnostics."""

    def __init__(
        self,
        *,
        config: JibitConfig,
        transport: HTTPTransport,
        logger: StructuredLogger,
        retry_policy: RetryPolicy,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        correlation_id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._config = config
        self._transport = transport
        self._logger = logger
        self._retry_policy = retry_policy
        self._sleep = sleep
        self._monotonic = monotonic
        self._correlation_id_factory = correlation_id_factory

    def execute(self, options: RequestOptions) -> RawResponse:
        """Execute one operation and return raw response data on success."""
        correlation_id = options.correlation_id or self._correlation_id_factory()
        endpoint = self._validated_endpoint(options.path)
        url = self._build_url(options.service, endpoint)
        headers = dict(options.headers)
        headers.setdefault("Accept", "application/json")
        headers.setdefault("X-Correlation-ID", correlation_id)
        if options.idempotency_key is not None:
            headers.setdefault("Idempotency-Key", options.idempotency_key)
        started = self._monotonic()
        self._logger.emit(
            logging.INFO,
            EventName.REQUEST_STARTED,
            service=options.service.value,
            operation=options.operation,
            method=options.method.upper(),
            endpoint=endpoint,
            correlation_id=correlation_id,
        )
        attempt = 1
        while True:
            try:
                response = self._transport.send(
                    TransportRequest(
                        method=options.method.upper(),
                        url=url,
                        headers=headers,
                        params=options.params,
                        json=options.json,
                        content=options.content,
                        timeout=self._config.timeout,
                    )
                )
            except (TransportTimeoutError, TransportNetworkError) as exc:
                decision = self._retry_policy.decide(
                    attempt=attempt,
                    safety=options.safety,
                    transport_error=True,
                    has_idempotency_key=options.idempotency_key is not None,
                )
                if decision.should_retry:
                    self._log_retry(
                        options, correlation_id, attempt, decision.reason, decision.delay
                    )
                    self._sleep(decision.delay)
                    attempt += 1
                    continue
                error_type = (
                    JibitTimeoutError
                    if isinstance(exc, TransportTimeoutError)
                    else JibitNetworkError
                )
                transport_failure = error_type(
                    "The request timed out"
                    if error_type is JibitTimeoutError
                    else "The request failed before receiving a response",
                    context=self._context(options, correlation_id, endpoint, retryable=False),
                )
                self._log_failure(transport_failure, started)
                raise transport_failure from exc

            if 200 <= response.status_code < 300:
                duration_ms = round((self._monotonic() - started) * 1000, 3)
                upstream_id = self._upstream_request_id(response.headers)
                self._logger.emit(
                    logging.INFO,
                    EventName.REQUEST_COMPLETED,
                    service=options.service.value,
                    operation=options.operation,
                    method=options.method.upper(),
                    endpoint=endpoint,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    correlation_id=correlation_id,
                    upstream_request_id=upstream_id,
                    attempts=attempt,
                )
                return RawResponse(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=response.content,
                    correlation_id=correlation_id,
                )

            decision = self._retry_policy.decide(
                attempt=attempt,
                safety=options.safety,
                status_code=response.status_code,
                has_idempotency_key=options.idempotency_key is not None,
            )
            if decision.should_retry:
                self._log_retry(options, correlation_id, attempt, decision.reason, decision.delay)
                self._sleep(decision.delay)
                attempt += 1
                continue
            error = self._map_error(options, correlation_id, endpoint, response)
            self._log_failure(error, started)
            raise error

    def _build_url(self, service: ServiceName, endpoint: str) -> str:
        service_config = self._config.services.get(service)
        base_url = (
            service_config.base_url
            if service_config and service_config.base_url
            else self._config.base_url
        )
        return f"{str(base_url).rstrip('/')}/{endpoint.lstrip('/')}"

    @staticmethod
    def _validated_endpoint(path: str) -> str:
        parsed = urlsplit(path)
        if not path.startswith("/") or parsed.scheme or parsed.netloc:
            raise JibitValidationError("Endpoint paths must be relative absolute paths")
        return path

    @staticmethod
    def _upstream_request_id(headers: Mapping[str, str]) -> str | None:
        lowered = {key.lower(): value for key, value in headers.items()}
        return lowered.get("x-request-id") or lowered.get("request-id") or lowered.get("trace-id")

    @staticmethod
    def _body_fields(response: TransportResponse) -> dict[str, Any]:
        if not response.content:
            return {}
        try:
            import json

            parsed = json.loads(response.content)
        except (UnicodeDecodeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _map_error(
        self,
        options: RequestOptions,
        correlation_id: str,
        endpoint: str,
        response: TransportResponse,
    ) -> JibitError:
        body = self._body_fields(response)
        nested_errors = body.get("errors")
        first_error = (
            nested_errors[0]
            if isinstance(nested_errors, list)
            and nested_errors
            and isinstance(nested_errors[0], dict)
            else {}
        )
        code = (
            body.get("code")
            or body.get("errorCode")
            or body.get("error")
            or first_error.get("code")
        )
        message = (
            body.get("message")
            or body.get("detail")
            or body.get("description")
            or first_error.get("message")
            or first_error.get("description")
        )
        fingerprint = body.get("fingerprint")
        reference = body.get("referenceNumber") or body.get("reference_number")
        request_id = (
            body.get("requestId")
            or body.get("request_id")
            or self._upstream_request_id(response.headers)
        )
        context = self._context(
            options,
            correlation_id,
            endpoint,
            status_code=response.status_code,
            error_code=str(code) if code is not None else None,
            upstream_message=str(message) if message is not None else None,
            upstream_request_id=str(request_id) if request_id is not None else None,
            fingerprint=str(fingerprint) if fingerprint is not None else None,
            reference_number=str(reference) if reference is not None else None,
            retryable=(
                response.status_code in {408, 425, 429, 500, 502, 503, 504}
                and (
                    options.safety in {OperationSafety.READ_ONLY, OperationSafety.IDEMPOTENT}
                    or (
                        options.safety is OperationSafety.IDEMPOTENCY_PROTECTED
                        and options.idempotency_key is not None
                    )
                )
            ),
        )
        error_message = str(message) if message else f"Jibit returned HTTP {response.status_code}"
        if response.status_code == 401:
            return JibitAuthenticationError(error_message, context=context)
        if response.status_code == 403:
            return JibitAuthorizationError(error_message, context=context)
        if response.status_code in {400, 422}:
            return JibitValidationError(error_message, context=context)
        if response.status_code == 429:
            return JibitRateLimitError(error_message, context=context)
        if response.status_code >= 500:
            return JibitServerError(error_message, context=context)
        if response.status_code in {402, 404, 409}:
            return JibitBusinessError(error_message, context=context)
        return JibitResponseError(error_message, context=context)

    @staticmethod
    def _context(
        options: RequestOptions,
        correlation_id: str,
        endpoint: str,
        **changes: Any,
    ) -> ErrorContext:
        return ErrorContext(
            service=options.service.value,
            operation=options.operation,
            method=options.method.upper(),
            endpoint=endpoint,
            correlation_id=correlation_id,
            **changes,
        )

    def _log_retry(
        self,
        options: RequestOptions,
        correlation_id: str,
        attempt: int,
        reason: str,
        delay: float,
    ) -> None:
        self._logger.emit(
            logging.WARNING,
            EventName.RETRY_SCHEDULED,
            service=options.service.value,
            operation=options.operation,
            correlation_id=correlation_id,
            attempt=attempt,
            reason=reason,
            delay_seconds=delay,
        )

    def _log_failure(self, error: JibitError, started: float) -> None:
        context = error.context.safe_dict()
        context.pop("upstream_message", None)
        self._logger.emit(
            logging.ERROR,
            EventName.REQUEST_FAILED,
            **context,
            error_type=type(error).__name__,
            duration_ms=round((self._monotonic() - started) * 1000, 3),
        )
