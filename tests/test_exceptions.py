"""Structured exception tests."""

from jibit.exceptions import ErrorContext, JibitBusinessError


def test_exception_context_is_safe_and_enrichable() -> None:
    """Exceptions expose useful context without leaking identifiers."""
    error = JibitBusinessError(
        "Failure for 6219861028500042",
        context=ErrorContext(service="payment_gateway", correlation_id="cid-1"),
    )

    enriched = error.with_context(status_code=409, error_code="duplicate")

    assert "6219861028500042" not in str(error)
    assert enriched.context.status_code == 409
    assert enriched.context.error_code == "duplicate"
    assert enriched.context.safe_dict() == {
        "service": "payment_gateway",
        "status_code": 409,
        "error_code": "duplicate",
        "correlation_id": "cid-1",
        "retryable": False,
    }
    assert "JibitBusinessError" in repr(enriched)
