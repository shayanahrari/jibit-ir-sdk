"""Pulse SMS typing, privacy, validation, auth, and retry-safety tests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone

import pytest

from jibit import JibitClient
from jibit.engine import RequestOptions
from jibit.exceptions import JibitTimeoutError, JibitValidationError
from jibit.response import RawResponse
from jibit.retry import OperationSafety
from jibit.services.sms import PulseSmsService
from jibit.transport import TransportTimeoutError
from tests.helpers import FakeTransport, response

MESSAGE_ID = "123e4567-e89b-12d3-a456-426614174000"


class StubExecutor:
    """Capture Pulse operations and return deterministic responses."""

    def __init__(self, outcomes: Sequence[RawResponse]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RawResponse:
        """Record and resolve one request."""
        self.requests.append(options)
        return self.outcomes.pop(0)


def raw(value: object) -> RawResponse:
    """Create one Pulse JSON response."""
    return RawResponse(200, {}, json.dumps(value).encode(), "cid-sms")


def test_root_client_authenticates_and_never_retries_uncertain_send() -> None:
    """Pulse auth is automatic but message submission is always single-attempt."""
    transport = FakeTransport(
        [
            response(content=b'{"access_token":"access","refresh_token":"refresh"}'),
            TransportTimeoutError("uncertain"),
        ]
    )
    client = JibitClient.from_config(
        {"sms": {"api_key": "key", "secret_key": "secret"}},
        transport=transport,
    )

    with pytest.raises(JibitTimeoutError):
        client.sms.send(receptor="09120000000", message="sensitive content")

    assert len(transport.requests) == 2
    assert transport.requests[0].url.endswith("/pulse/api/v1/auth/authenticate")
    assert "sensitive content" not in repr(transport.requests[1])


def test_send_pattern_bulk_and_status_operations_are_typed() -> None:
    """Pulse write and inquiry operations use separate paths and safety classes."""
    executor = StubExecutor(
        [
            raw({"sms_orders": [{"message_id": MESSAGE_ID, "status": "QUEUED"}]}),
            raw({"message_id": MESSAGE_ID, "status": "QUEUED"}),
            raw({"bulk_id": MESSAGE_ID, "status": "DRAFT"}),
            raw({"message_id": MESSAGE_ID, "status": "DELIVERED"}),
            raw({"message_id": MESSAGE_ID, "status": "DELIVERED"}),
        ]
    )
    service = PulseSmsService(executor)

    assert service.send(receptor="09120000000", message="hello").data.sms_orders
    assert (
        service.send_pattern(
            receptor="09120000000", template="login", params={"code": "secret"}
        ).data.status
        == "QUEUED"
    )
    assert (
        service.create_bulk(
            bulk_name="notice", sender="sender", receptors=["09120000000"], message="hello"
        ).data.status
        == "DRAFT"
    )
    assert service.get_status(MESSAGE_ID).data.status == "DELIVERED"
    assert service.get_status_by_client_id("client-message-1").data.status == "DELIVERED"
    assert all(request.safety is OperationSafety.UNSAFE for request in executor.requests[:3])
    assert all(request.safety is OperationSafety.READ_ONLY for request in executor.requests[3:])
    assert "clientMessageId" not in executor.requests[0].json
    assert "bulk_name" in executor.requests[2].json

    with pytest.raises(JibitValidationError):
        service.create_bulk(
            bulk_name="invalid",
            sender="sender",
            receptors=["09120000000"],
            message="text",
            predefined_message_id=MESSAGE_ID,
        )


def test_bulk_and_inbound_inquiries_validate_paging_and_range() -> None:
    """Read-oriented message APIs validate boundaries before network calls."""
    executor = StubExecutor([raw({"bulk_id": MESSAGE_ID, "sms_list": []}), raw({"result": []})])
    service = PulseSmsService(executor)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    assert service.get_bulk(MESSAGE_ID).data.sms_list == []
    assert service.fetch_inbound(from_date=start, to_date=end).data.result == []
    assert all(request.safety is OperationSafety.READ_ONLY for request in executor.requests)

    with pytest.raises(JibitValidationError):
        service.get_bulk(MESSAGE_ID, page=-1)
    with pytest.raises(JibitValidationError):
        service.fetch_inbound(from_date=end, to_date=start)
