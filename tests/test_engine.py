"""Request engine safety, correlation, retry, and error-mapping tests."""

import logging
from collections.abc import Iterator

import pytest

from jibit.config import JibitConfig, RetryConfig
from jibit.engine import RequestEngine, RequestOptions
from jibit.exceptions import (
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
from jibit.logging import StructuredLogger
from jibit.retry import OperationSafety, RetryPolicy
from jibit.transport import TransportNetworkError, TransportTimeoutError
from jibit.types import ServiceName
from tests.helpers import FakeTransport, response


def make_engine(
    transport: FakeTransport,
    *,
    times: Iterator[float] | None = None,
    delays: list[float] | None = None,
    config: JibitConfig | None = None,
) -> RequestEngine:
    """Create a deterministic request engine."""
    sdk_config = config or JibitConfig(retry=RetryConfig(jitter_ratio=0))
    clock = times or iter([1.0, 1.1])
    recorded_delays = delays if delays is not None else []
    return RequestEngine(
        config=sdk_config,
        transport=transport,
        logger=StructuredLogger(logging.getLogger("tests.engine")),
        retry_policy=RetryPolicy(sdk_config.retry, random_source=lambda: 0),
        sleep=recorded_delays.append,
        monotonic=lambda: next(clock),
        correlation_id_factory=lambda: "cid-1",
    )


def options(**changes: object) -> RequestOptions:
    """Create common request options with selective overrides."""
    values: dict[str, object] = {
        "service": ServiceName.PAYMENT_GATEWAY,
        "operation": "get_purchase",
        "method": "GET",
        "path": "/ppg/v3/purchases/1",
        "safety": OperationSafety.READ_ONLY,
    }
    values.update(changes)
    return RequestOptions(**values)  # type: ignore[arg-type]


def test_success_adds_correlation_and_preserves_request_id(caplog: object) -> None:
    """Successful requests expose correlation and upstream tracing identifiers."""
    transport = FakeTransport([response(headers={"X-Request-ID": "upstream-1"})])
    engine = make_engine(transport)

    with caplog.at_level(logging.INFO, logger="tests.engine"):  # type: ignore[attr-defined]
        result = engine.execute(options())

    assert result.correlation_id == "cid-1"
    assert transport.requests[0].headers["X-Correlation-ID"] == "cid-1"
    assert transport.requests[0].url == "https://napi.jibit.ir/ppg/v3/purchases/1"
    assert caplog.records[-1].jibit["upstream_request_id"] == "upstream-1"  # type: ignore[attr-defined]


def test_service_url_override_and_idempotency_header() -> None:
    """A service can target an authorized environment without changing other services."""
    config = JibitConfig.from_mapping(
        {
            "payment_gateway": {
                "api_key": "key",
                "secret_key": "secret",
                "base_url": "https://sandbox.example.test",
            }
        }
    )
    transport = FakeTransport([response()])

    make_engine(transport, config=config).execute(
        options(
            method="POST",
            safety=OperationSafety.IDEMPOTENCY_PROTECTED,
            idempotency_key="idem-1",
        )
    )

    request = transport.requests[0]
    assert request.url.startswith("https://sandbox.example.test/")
    assert request.headers["Idempotency-Key"] == "idem-1"


def test_transient_safe_request_is_retried() -> None:
    """A safe request retries a transient response with bounded delay."""
    transport = FakeTransport([response(503), response(200)])
    delays: list[float] = []

    result = make_engine(transport, delays=delays).execute(options())

    assert result.status_code == 200
    assert len(transport.requests) == 2
    assert delays == [0.25]


def test_safe_transport_failure_is_retried() -> None:
    """Read-only transport failures can be retried without duplicating side effects."""
    transport = FakeTransport([TransportTimeoutError(), response(200)])
    delays: list[float] = []

    result = make_engine(transport, delays=delays).execute(options())

    assert result.status_code == 200
    assert delays == [0.25]


@pytest.mark.parametrize(
    ("transport_error", "expected"),
    [
        (TransportTimeoutError(), JibitTimeoutError),
        (TransportNetworkError(), JibitNetworkError),
    ],
)
def test_unsafe_transport_failure_is_not_retried(
    transport_error: Exception,
    expected: type[JibitError],
) -> None:
    """An uncertain financial outcome is surfaced immediately for reconciliation."""
    transport = FakeTransport([transport_error])

    with pytest.raises(expected) as captured:
        make_engine(transport).execute(options(method="POST", safety=OperationSafety.UNSAFE))

    assert len(transport.requests) == 1
    assert captured.value.context.retryable is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, JibitAuthenticationError),
        (403, JibitAuthorizationError),
        (400, JibitValidationError),
        (422, JibitValidationError),
        (402, JibitBusinessError),
        (404, JibitBusinessError),
        (409, JibitBusinessError),
        (429, JibitRateLimitError),
        (500, JibitServerError),
        (418, JibitResponseError),
    ],
)
def test_http_errors_map_to_structured_exception_types(
    status: int,
    expected: type[JibitError],
) -> None:
    """Upstream statuses have stable exception categories and safe context."""
    transport = FakeTransport(
        [
            response(
                status,
                content=(
                    b'{"code":"provider.error","message":"Failed for 6219861028500042",'
                    b'"fingerprint":"fp-1","requestId":"request-1",'
                    b'"referenceNumber":"ref-1"}'
                ),
            )
        ]
    )
    engine = make_engine(
        transport,
        config=JibitConfig(retry=RetryConfig(max_attempts=1)),
    )

    with pytest.raises(expected) as captured:
        engine.execute(options())

    error = captured.value
    assert "6219861028500042" not in str(error)
    assert error.context.error_code == "provider.error"
    assert error.context.safe_dict()["upstream_message"] == "[REDACTED]"
    assert error.context.upstream_message == "[REDACTED]"
    assert error.context.fingerprint == "fp-1"
    assert error.context.reference_number == "ref-1"


def test_non_json_error_and_header_request_id_are_supported() -> None:
    """Malformed error bodies do not hide useful upstream tracing headers."""
    transport = FakeTransport([response(418, content=b"not-json", headers={"Trace-ID": "trace-1"})])

    with pytest.raises(JibitResponseError) as captured:
        make_engine(transport).execute(options())

    assert captured.value.context.upstream_request_id == "trace-1"


def test_json_array_error_body_is_treated_as_unstructured() -> None:
    """Unexpected JSON shapes cannot break generic HTTP error mapping."""
    transport = FakeTransport([response(418, content=b"[]")])

    with pytest.raises(JibitResponseError, match="HTTP 418"):
        make_engine(transport).execute(options())


def test_ppg_nested_error_contract_is_mapped_to_safe_context() -> None:
    """PPG's errors array supplies its first code and message for diagnostics."""
    transport = FakeTransport(
        [
            response(
                409,
                content=(
                    b'{"fingerprint":"fp-2","errors":['
                    b'{"code":"purchase.duplicated",'
                    b'"message":"Rejected card 6037991111222233"}]}'
                ),
            )
        ]
    )

    with pytest.raises(JibitBusinessError) as captured:
        make_engine(transport).execute(options())

    assert captured.value.context.error_code == "purchase.duplicated"
    assert "6037991111222233" not in str(captured.value)
    assert captured.value.context.fingerprint == "fp-2"


@pytest.mark.parametrize("path", ["https://evil.example/path", "relative/path"])
def test_absolute_or_non_rooted_endpoint_is_rejected(path: str) -> None:
    """Service operations cannot redirect credentials to arbitrary hosts."""
    with pytest.raises(JibitValidationError):
        make_engine(FakeTransport([])).execute(options(path=path))
