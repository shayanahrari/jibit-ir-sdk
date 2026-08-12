"""Exception hierarchy and safe upstream error context."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

from typing_extensions import Self

from jibit.redaction import redact_text


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Store safe diagnostic context for an SDK or upstream API failure."""

    service: str | None = None
    operation: str | None = None
    method: str | None = None
    endpoint: str | None = None
    status_code: int | None = None
    error_code: str | None = None
    upstream_message: str | None = None
    upstream_request_id: str | None = None
    fingerprint: str | None = None
    reference_number: str | None = None
    correlation_id: str | None = None
    retryable: bool = False

    def safe_dict(self) -> dict[str, Any]:
        """Return populated context fields with free-text identifiers redacted."""
        return {
            field: redact_text(value) if isinstance(value, str) else value
            for field in (item.name for item in fields(self))
            if (value := getattr(self, field)) is not None
        }


class JibitError(Exception):
    """Base class for predictable SDK and Jibit API failures."""

    default_message = "A Jibit SDK error occurred"

    def __init__(self, message: str | None = None, *, context: ErrorContext | None = None) -> None:
        self.message = redact_text(message or self.default_message)
        self.context = context or ErrorContext()
        super().__init__(self.message)

    def with_context(self, **changes: Any) -> Self:
        """Return an equivalent exception with additional immutable context."""
        return type(self)(self.message, context=replace(self.context, **changes))

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(message={self.message!r}, context={self.context.safe_dict()!r})"
        )


class JibitConfigurationError(JibitError):
    """Raised when local SDK configuration is invalid or incomplete."""


class JibitAuthenticationError(JibitError):
    """Raised when credentials or an access token cannot authenticate a request."""


class JibitAuthorizationError(JibitError):
    """Raised when an authenticated principal lacks permission for an operation."""


class JibitValidationError(JibitError):
    """Raised when local or upstream request validation fails."""


class JibitBusinessError(JibitError):
    """Raised when an API request violates a Jibit business rule."""


class JibitRateLimitError(JibitError):
    """Raised when the upstream service rate-limits a request."""


class JibitTimeoutError(JibitError):
    """Raised when a network operation exceeds a configured timeout."""


class JibitNetworkError(JibitError):
    """Raised when a request fails before a valid HTTP response is received."""


class JibitServerError(JibitError):
    """Raised when a Jibit service returns a server-side failure."""


class JibitResponseError(JibitError):
    """Raised when an upstream response cannot be safely interpreted."""


class JibitWebhookVerificationError(JibitError):
    """Raised when a callback fails configured authenticity checks."""


class JibitUnsupportedOperationError(JibitError):
    """Raised when an operation lacks enough contract information for safe use."""
