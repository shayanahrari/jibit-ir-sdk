"""Conservative retry classification for financial and non-financial operations."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from jibit.config import RetryConfig

TRANSIENT_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


class OperationSafety(str, Enum):
    """Describe whether repeating an operation can duplicate side effects."""

    READ_ONLY = "read_only"
    IDEMPOTENT = "idempotent"
    IDEMPOTENCY_PROTECTED = "idempotency_protected"
    UNSAFE = "unsafe"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Describe whether and when the request engine may retry an attempt."""

    should_retry: bool
    delay: float = 0.0
    reason: str = "not_retryable"


class RetryPolicy:
    """Apply bounded exponential backoff only to explicitly repeatable requests."""

    def __init__(
        self,
        config: RetryConfig,
        *,
        random_source: Callable[[], float] = random.random,
    ) -> None:
        self._config = config
        self._random = random_source

    def decide(
        self,
        *,
        attempt: int,
        safety: OperationSafety,
        status_code: int | None = None,
        transport_error: bool = False,
        has_idempotency_key: bool = False,
    ) -> RetryDecision:
        """Return a retry decision for an already completed attempt."""
        if attempt >= self._config.max_attempts:
            return RetryDecision(False, reason="attempt_limit")
        if safety is OperationSafety.UNSAFE:
            return RetryDecision(False, reason="unsafe_operation")
        if safety is OperationSafety.IDEMPOTENCY_PROTECTED and not has_idempotency_key:
            return RetryDecision(False, reason="missing_idempotency_key")
        if not transport_error and status_code not in TRANSIENT_STATUS_CODES:
            return RetryDecision(False, reason="non_transient_response")
        base = min(self._config.max_delay, self._config.base_delay * (2 ** (attempt - 1)))
        jitter = base * self._config.jitter_ratio * self._random()
        reason = "transport_error" if transport_error else f"http_{status_code}"
        return RetryDecision(True, delay=min(self._config.max_delay, base + jitter), reason=reason)
