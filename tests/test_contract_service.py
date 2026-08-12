"""MzaHub contract typing, IP validation, auth, document safety, and retry tests."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from jibit import JibitClient
from jibit.engine import RequestOptions
from jibit.exceptions import JibitTimeoutError, JibitValidationError
from jibit.response import RawResponse
from jibit.retry import OperationSafety
from jibit.services.contracts import ContractService
from jibit.transport import TransportTimeoutError
from tests.helpers import FakeTransport, response


class StubExecutor:
    """Capture MzaHub requests with deterministic responses."""

    def __init__(self, outcomes: Sequence[RawResponse]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RawResponse:
        """Record and resolve one request."""
        self.requests.append(options)
        return self.outcomes.pop(0)


def raw(value: object, *, content_type: str | None = None) -> RawResponse:
    """Create one MzaHub JSON or binary response."""
    content = value if isinstance(value, bytes) else json.dumps(value).encode()
    headers = {"Content-Type": content_type} if content_type else {}
    return RawResponse(200, headers, content, "cid-contract")


def test_root_client_authenticates_and_does_not_retry_contract_creation() -> None:
    """MzaHub login is automatic while uncertain contract creation remains single-attempt."""
    transport = FakeTransport(
        [
            response(
                content=(
                    b'{"accessToken":"access","refreshToken":"refresh",'
                    b'"expiresIn":3600,"refreshTokenExpiresIn":7200}'
                )
            ),
            TransportTimeoutError("uncertain"),
        ]
    )
    client = JibitClient.from_config(
        {"contracts": {"api_key": "key", "secret_key": "secret"}},
        transport=transport,
    )

    with pytest.raises(JibitTimeoutError):
        client.contracts.initiate(
            track_id="contract-1",
            pdf=b"%PDF-1.7 synthetic",
            redirect_url="https://example.com/return",
            signers=[{"national_code": "0013547891", "birth_date": "13600101"}],
            real_ip="192.0.2.10",
        )

    assert len(transport.requests) == 2
    assert transport.requests[0].url.endswith("/mzahub/v1/auth/login")
    assert transport.requests[1].headers["X-REAL-IP"] == "192.0.2.10"
    assert "%PDF" not in repr(transport.requests[1])


def test_contract_create_inquire_cancel_and_download_are_typed() -> None:
    """Contract lifecycle operations preserve typed metadata and raw signed bytes."""
    executor = StubExecutor(
        [
            raw({"link": "https://example.com/sign", "contract": {"trackId": "contract-1"}}),
            raw({"trackId": "contract-1", "status": "NOT_SIGNED", "signs": []}),
            raw({"trackId": "contract-1", "status": "CANCELLED"}),
            raw(b"%PDF-1.7 signed", content_type="application/pdf"),
        ]
    )
    service = ContractService(executor)

    created = service.initiate(
        track_id="contract-1",
        pdf=b"%PDF-1.7 source",
        redirect_url="https://example.com/return",
        signers=[{"national_code": "0013547891", "birth_date": "13600101"}],
        real_ip="192.0.2.10",
    )
    assert created.data.contract is not None
    assert created.data.contract.track_id == "contract-1"
    assert service.inquire("contract-1", real_ip="192.0.2.10").data.status == "NOT_SIGNED"
    assert service.cancel("contract-1", real_ip="192.0.2.10").data.status == "CANCELLED"
    signed = service.download_signed("contract-1", real_ip="192.0.2.10")
    assert signed.data.content == b"%PDF-1.7 signed"
    assert signed.data.content_type == "application/pdf"
    assert executor.requests[0].safety is OperationSafety.UNSAFE
    assert executor.requests[1].safety is OperationSafety.READ_ONLY
    assert executor.requests[2].safety is OperationSafety.UNSAFE
    assert executor.requests[3].safety is OperationSafety.READ_ONLY


def test_contract_validation_rejects_invalid_ip_document_track_and_signer() -> None:
    """Sensitive contract data is validated before any provider request."""
    service = ContractService(StubExecutor([]))
    with pytest.raises(JibitValidationError):
        service.initiate(
            track_id="contract-1",
            pdf=b"not a pdf",
            redirect_url="https://example.com/return",
            signers=[{"national_code": "0013547891", "birth_date": "13600101"}],
            real_ip="192.0.2.10",
        )
    with pytest.raises(JibitValidationError):
        service.inquire("bad/track", real_ip="192.0.2.10")
    with pytest.raises(JibitValidationError):
        service.inquire("contract-1", real_ip="not-an-ip")
