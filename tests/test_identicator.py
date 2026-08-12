"""Identicator models, contracts, safety, and root-client tests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import cast

import pytest

from jibit import JibitClient
from jibit.auth import AuthenticatedRequestEngine
from jibit.engine import RequestOptions
from jibit.exceptions import JibitValidationError
from jibit.logging import AuditEvent
from jibit.response import RawResponse
from jibit.retry import OperationSafety
from jibit.services.identicator import IdenticatorService, MatchingRequest
from tests.helpers import FakeTransport, response


class CollectingAuditSink:
    """Collect identity audit events without persisting sensitive input."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        """Store one redacted event for assertions."""
        self.events.append(event)


class StubExecutor:
    """Return deterministic responses while recording Identicator requests."""

    def __init__(self, outcomes: Sequence[RawResponse]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RawResponse:
        """Record and resolve one request."""
        self.requests.append(options)
        return self.outcomes.pop(0)


def raw(value: object) -> RawResponse:
    """Create one JSON response."""
    return RawResponse(200, {}, json.dumps(value).encode(), "cid-identicator")


def service(outcomes: Sequence[RawResponse]) -> tuple[IdenticatorService, StubExecutor]:
    """Build a deterministic Identicator facade."""
    executor = StubExecutor(outcomes)
    return IdenticatorService(cast(AuthenticatedRequestEngine, executor)), executor


def test_root_client_automatically_authenticates_identicator() -> None:
    """The root client obtains and attaches Identicator tokens automatically."""
    transport = FakeTransport(
        [
            response(content=b'{"accessToken":"access","refreshToken":"refresh"}'),
            response(
                content=(
                    b'{"value":"IR000000000000000000000000",'
                    b'"ibanInfo":{"bank":"example","owners":[]}}'
                )
            ),
        ]
    )
    audit_sink = CollectingAuditSink()
    client = JibitClient.from_config(
        {"identicator": {"api_key": "key", "secret_key": "secret"}},
        transport=transport,
        audit_sink=audit_sink,
    )

    result = client.identicator.inquire_iban(
        "IR000000000000000000000000", track_id="business-track-1"
    )

    assert result.data.iban_info is not None
    assert result.data.iban_info.bank == "example"
    assert transport.requests[0].url.endswith("/ide/v1/tokens/generate")
    assert transport.requests[1].headers["Authorization"] == "Bearer access"
    assert transport.requests[1].headers["X-TRACK-ID"] == "business-track-1"
    assert audit_sink.events[0].name == "jibit.identicator.operation"
    assert audit_sink.events[0].outcome == "succeeded"
    assert "business-track-1" not in repr(audit_sink.events[0])


def test_banking_and_postal_inquiries_use_read_only_contracts() -> None:
    """Banking and postal inquiry paths, queries, aliases, and models are covered."""
    facade, executor = service(
        [
            raw({"number": "123", "depositToIBANInfo": {"bank": "bank", "iban": "IR1"}}),
            raw({"number": "6037990000000001", "type": "DEBIT"}),
            raw({"code": "1234567890", "addressInfo": {"city": "city"}}),
            raw({"code": "1234567890", "wgsInfo": {"latitude": 35.7, "longitude": 51.4}}),
        ]
    )

    deposit = facade.inquire_deposit(bank="example", number="123", include_iban=True)
    card = facade.inquire_card("6037990000000001", include_iban=True)
    postal = facade.inquire_postal_address("1234567890")
    wgs = facade.inquire_postal_coordinates("1234567890")

    assert deposit.data.deposit_to_iban_info is not None
    assert deposit.data.deposit_to_iban_info.iban == "IR1"
    assert card.data.type == "DEBIT"
    assert postal.data.address_info is not None
    assert postal.data.address_info.city == "city"
    assert wgs.data.wgs_info is not None
    assert wgs.data.wgs_info.latitude == 35.7
    assert all(item.safety is OperationSafety.READ_ONLY for item in executor.requests)
    assert executor.requests[0].params == {"bank": "example", "number": "123", "iban": True}


def test_identity_defaults_to_without_photo_and_response_repr_is_safe() -> None:
    """Identity queries omit photos by default and models do not reveal identity data."""
    facade, executor = service(
        [
            raw(
                {
                    "nationalCode": "0013547891",
                    "birthDate": "13600101",
                    "identityInfo": {"firstName": "Sensitive", "photo": "base64-image"},
                }
            )
        ]
    )

    result = facade.inquire_identity(national_code="0013547891", birth_date="13600101")

    assert executor.requests[0].params is not None
    assert executor.requests[0].params["withoutPhoto"] is True
    assert "Sensitive" not in repr(result.data)
    assert "base64-image" not in repr(result.data)


def test_matching_and_similarity_validate_inputs_and_use_idempotent_post() -> None:
    """Typed POST inquiries allow only documented identity combinations."""
    facade, executor = service([raw({"matched": True}), raw({"fullNameSimilarityPercentage": 95})])

    matched = facade.match(iban="IR000000000000000000000000", national_code="0013547891")
    similarity = facade.compare_identity_names(
        national_code="0013547891", birth_date="13600101", full_name="Example Name"
    )

    assert matched.data.matched is True
    assert similarity.data.full_name_similarity_percentage == 95
    assert all(item.safety is OperationSafety.IDEMPOTENT for item in executor.requests)
    assert executor.requests[0].json["nationalCode"] == "0013547891"

    with pytest.raises(JibitValidationError):
        facade.match(iban="IR000000000000000000000000")
    with pytest.raises(JibitValidationError):
        facade.compare_identity_names(national_code="0013547891", birth_date="13600101")


def test_remaining_inquiries_and_operational_models_are_covered() -> None:
    """Flexible nested responses remain accessible without losing typed envelopes."""
    facade, executor = service(
        [
            raw({"fida": "fida-1", "foreignerIdentityInfo": {"firstName": "name"}}),
            raw({"nationalCode": "legal", "legalIdentityInfo": {"name": "company"}}),
            raw({"nationalCode": "legal", "legalIdentityInfo": {"name": "company"}}),
            raw({"nationalCode": "id", "militaryServiceQualificationInfo": {"qualified": True}}),
            raw({"nationalCode": "id", "registered": True}),
            raw({"code": "guild", "corporationIdentityInfo": {"code": "guild"}}),
            raw({"nationalCode": "id", "chequeInfo": {"sayadId": "sayad"}}),
            raw({"balances": [{"balanceType": "WLT", "amount": 100, "currency": "IRR"}]}),
            raw({"report": [{"clientCode": "client", "services": []}]}),
            raw({"availabilityReport": {"provider": True}}),
            raw({"outcome": "UP", "checks": []}),
        ]
    )

    assert facade.inquire_foreigner_identity("fida-1").data.fida == "fida-1"
    assert facade.inquire_legal_identity("legal").data.legal_identity_info == {"name": "company"}
    assert facade.inquire_legal_sign_holders("legal").data.national_code == "legal"
    assert facade.inquire_military_qualification("id").data.national_code == "id"
    assert facade.inquire_sana("id").data.registered is True
    assert facade.inquire_corporation("guild").data.code == "guild"
    assert facade.inquire_cheque(national_code="id", sayad_id="sayad").data.cheque_info == {
        "sayadId": "sayad"
    }
    assert facade.get_balances().data.balances[0].amount == 100
    assert facade.get_daily_usage_report("14050101").data.report[0]["clientCode"] == "client"
    assert facade.service_availability().data.availability_report == {"provider": True}
    assert facade.health().data.outcome == "UP"
    assert len(executor.requests) == 11


def test_invalid_card_flags_use_public_validation_exception() -> None:
    """Facade validation never leaks an unstructured value error."""
    facade, executor = service([])

    with pytest.raises(JibitValidationError) as captured:
        facade.inquire_card("6037990000000001", include_deposit=True, include_iban=True)

    assert captured.value.context.operation == "inquire_card"
    assert not executor.requests


def test_matching_request_repr_redacts_identity_payload() -> None:
    """Typed request objects do not expose bank or identity identifiers in repr."""
    request = MatchingRequest(iban="IR000000000000000000000000", national_code="0013547891")

    assert "0013547891" not in repr(request)
    assert "IR000000000000000000000000" not in repr(request)
