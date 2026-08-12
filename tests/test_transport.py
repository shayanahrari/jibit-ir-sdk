"""Default HTTP transport tests."""

import httpx
import pytest
import respx

from jibit.config import TimeoutConfig
from jibit.transport import (
    HttpxTransport,
    TransportNetworkError,
    TransportRequest,
    TransportTimeoutError,
)


@respx.mock
def test_httpx_transport_sends_and_reads_response() -> None:
    """The default transport preserves status, headers, body, and user agent."""
    route = respx.get("https://example.test/resource").mock(
        return_value=httpx.Response(200, headers={"X-Request-ID": "req-1"}, json={"ok": True})
    )
    transport = HttpxTransport(verify_ssl=True, user_agent="test-sdk")

    result = transport.send(
        TransportRequest(
            "GET",
            "https://example.test/resource",
            {},
            timeout=TimeoutConfig(),
        )
    )
    transport.close()

    assert result.status_code == 200
    assert result.content == b'{"ok":true}'
    assert route.calls[0].request.headers["User-Agent"] == "test-sdk"


@pytest.mark.parametrize(
    ("upstream_error", "expected"),
    [
        (httpx.ReadTimeout("timeout"), TransportTimeoutError),
        (httpx.ConnectError("network"), TransportNetworkError),
    ],
)
@respx.mock
def test_httpx_transport_normalizes_failures(
    upstream_error: Exception,
    expected: type[Exception],
) -> None:
    """Transport-specific exceptions do not leak through the public engine."""
    respx.get("https://example.test/resource").mock(side_effect=upstream_error)
    transport = HttpxTransport(verify_ssl=True, user_agent="test-sdk")

    with pytest.raises(expected):
        transport.send(TransportRequest("GET", "https://example.test/resource", {}))
    transport.close()
