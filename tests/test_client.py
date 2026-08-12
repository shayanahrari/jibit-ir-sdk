"""Root client lifecycle and injection tests."""

from jibit import JibitClient
from jibit.config import JibitConfig
from jibit.types import ServiceName
from tests.helpers import FakeTransport


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
