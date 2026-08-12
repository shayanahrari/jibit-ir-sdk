"""Root client lifecycle and injection tests."""

import logging

from jibit import JibitClient
from jibit.config import JibitConfig, RetryConfig
from jibit.engine import RequestOptions
from jibit.logging import StructuredLogger
from jibit.retry import OperationSafety, RetryPolicy
from jibit.types import ServiceName
from tests.helpers import FakeTransport, response


def test_client_accepts_mapping_and_does_not_close_injected_transport() -> None:
    """Applications retain lifecycle control over injected shared transports."""
    transport = FakeTransport([])
    client = JibitClient.from_config({}, transport=transport)

    with client as entered:
        assert entered.config == JibitConfig()
        assert entered.request_engine is not None

    client.close()
    assert transport.close_calls == 0


def test_client_lazily_reuses_authenticated_engine() -> None:
    """Each configured service receives one isolated authentication coordinator."""
    client = JibitClient.from_config(
        {
            "payment_gateway": {"api_key": "key", "secret_key": "secret"},
        },
        transport=FakeTransport([]),
    )

    first = client.authenticated_engine(ServiceName.PAYMENT_GATEWAY)
    second = client.authenticated_engine(ServiceName.PAYMENT_GATEWAY)

    assert first is second


def test_client_accepts_deterministic_engine_dependencies() -> None:
    """The root client exposes retry, timing, logging, and correlation injection."""
    transport = FakeTransport([response(content=b'{"ok":true}')])
    logger = StructuredLogger(logging.getLogger("tests.client"))
    monotonic_values = iter((5.0, 5.125))
    sleep_calls: list[float] = []
    client = JibitClient.from_config(
        {},
        transport=transport,
        logger=logger,
        retry_policy=RetryPolicy(RetryConfig(max_attempts=1)),
        sleep=sleep_calls.append,
        clock=lambda: 1_700_000_000,
        monotonic=lambda: next(monotonic_values),
        correlation_id_factory=lambda: "deterministic-correlation-id",
    )

    result = client.request_engine.execute(
        RequestOptions(
            service=ServiceName.PAYMENT_GATEWAY,
            operation="health",
            method="GET",
            path="/ppg/v3/app/health",
            safety=OperationSafety.READ_ONLY,
        )
    )

    assert result.correlation_id == "deterministic-correlation-id"
    assert transport.requests[0].headers["X-Correlation-ID"] == result.correlation_id
    assert sleep_calls == []
