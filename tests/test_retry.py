"""Financial retry policy tests."""

import pytest

from jibit.config import RetryConfig
from jibit.retry import OperationSafety, RetryPolicy


def make_policy() -> RetryPolicy:
    """Create a deterministic policy without random jitter."""
    return RetryPolicy(
        RetryConfig(max_attempts=3, base_delay=0.5, max_delay=2, jitter_ratio=0.5),
        random_source=lambda: 0.0,
    )


@pytest.mark.parametrize("safety", [OperationSafety.READ_ONLY, OperationSafety.IDEMPOTENT])
def test_safe_transient_responses_are_retried(safety: OperationSafety) -> None:
    """Read-only and idempotent requests retry bounded transient responses."""
    decision = make_policy().decide(attempt=1, safety=safety, status_code=503)
    assert decision.should_retry
    assert decision.delay == 0.5
    assert decision.reason == "http_503"


def test_unsafe_and_unprotected_operations_are_never_retried() -> None:
    """Financial submissions require explicit idempotency protection."""
    policy = make_policy()
    assert (
        policy.decide(
            attempt=1,
            safety=OperationSafety.UNSAFE,
            transport_error=True,
        ).reason
        == "unsafe_operation"
    )
    assert (
        policy.decide(
            attempt=1,
            safety=OperationSafety.IDEMPOTENCY_PROTECTED,
            transport_error=True,
        ).reason
        == "missing_idempotency_key"
    )
    assert policy.decide(
        attempt=1,
        safety=OperationSafety.IDEMPOTENCY_PROTECTED,
        transport_error=True,
        has_idempotency_key=True,
    ).should_retry


def test_non_transient_and_exhausted_attempts_are_not_retried() -> None:
    """Retries stop for normal client errors and at the configured attempt limit."""
    policy = make_policy()
    assert (
        policy.decide(
            attempt=1,
            safety=OperationSafety.READ_ONLY,
            status_code=400,
        ).reason
        == "non_transient_response"
    )
    assert (
        policy.decide(
            attempt=3,
            safety=OperationSafety.READ_ONLY,
            status_code=503,
        ).reason
        == "attempt_limit"
    )
