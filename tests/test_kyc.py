"""KYC static authentication, multipart, validation, and contract tests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import cast

import pytest

from jibit import JibitClient
from jibit.auth import StaticBearerRequestEngine
from jibit.engine import RequestOptions
from jibit.exceptions import JibitConfigurationError, JibitValidationError
from jibit.logging import AuditEvent
from jibit.response import RawResponse
from jibit.retry import OperationSafety
from jibit.services.kyc import KycService, MediaFile
from jibit.types import ContentPartType
from tests.helpers import FakeTransport, response


class CollectingAuditSink:
    """Collect data-minimized KYC audit events for assertions."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        """Store one redacted event."""
        self.events.append(event)


class StubExecutor:
    """Return deterministic KYC responses while recording multipart requests."""

    def __init__(self, outcomes: Sequence[RawResponse]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RawResponse:
        """Record and resolve one request."""
        self.requests.append(options)
        return self.outcomes.pop(0)


def raw(value: object) -> RawResponse:
    """Create a raw JSON response."""
    return RawResponse(200, {}, json.dumps(value).encode(), "cid-kyc")


def service(outcomes: Sequence[RawResponse]) -> tuple[KycService, StubExecutor]:
    """Build a KYC facade around a deterministic executor."""
    executor = StubExecutor(outcomes)
    return KycService(cast(StaticBearerRequestEngine, executor)), executor


def image_file() -> MediaFile:
    """Return synthetic image bytes for boundary-mocked tests."""
    return MediaFile(content=b"synthetic-image", filename="identity.jpg", content_type="image/jpeg")


def test_root_client_attaches_static_kyc_bearer_without_refresh() -> None:
    """KYC uses the configured token directly because no refresh flow is documented."""
    transport = FakeTransport([response(content=b'{"errorCode":"","data":{}}')])
    audit_sink = CollectingAuditSink()
    client = JibitClient.from_config(
        {"kyc": {"access_token": "static-bearer"}},
        transport=transport,
        audit_sink=audit_sink,
    )

    result = client.kyc.ocr_national_card(image_file())

    assert result.data.error_code == ""
    assert len(transport.requests) == 1
    assert transport.requests[0].headers["Authorization"] == "Bearer static-bearer"
    assert transport.requests[0].url.endswith("/alpha/ocr")
    assert "static-bearer" not in repr(transport.requests[0])
    assert audit_sink.events[0].name == "jibit.kyc.operation"
    assert audit_sink.events[0].metadata == {"status_code": 200}


def test_missing_static_kyc_token_is_rejected_before_network_io() -> None:
    """The SDK never guesses KYC authentication from unrelated credentials."""
    client = JibitClient.from_config({}, transport=FakeTransport([]))

    with pytest.raises(JibitConfigurationError, match="kyc"):
        _ = client.kyc


def test_video_and_photo_operations_build_sensitive_multipart_without_payload_repr() -> None:
    """Biometric fields and media remain isolated in secret-safe multipart parts."""
    facade, executor = service([raw({"data": {"status": True}}), raw({"data": {}})])
    video = MediaFile(content=b"synthetic-video", filename="verify.mp4", content_type="video/mp4")

    facade.verify_video(
        national_id="0013547891",
        video=video,
        line="documented challenge",
        max_accepted_dist=5,
        check_liveness=True,
    )
    facade.verify_photo(national_id="0013547891", live_face=image_file())

    video_request = executor.requests[0]
    assert video_request.path == "/alpha/v2/kyc"
    assert video_request.safety is OperationSafety.UNSAFE
    assert video_request.multipart is not None
    assert any(part.name == "national_id" for part in video_request.multipart)
    upload = next(part for part in video_request.multipart if part.name == "video_file")
    assert upload.kind is ContentPartType.FILE
    assert "synthetic-video" not in repr(upload)
    assert executor.requests[1].path == "/alpha/v2/authorization"


def test_all_ocr_operations_use_documented_catalog_paths() -> None:
    """National-card, cheque, and bank-card OCR routes are operation-separated."""
    facade, executor = service([raw({"data": {}}), raw({"data": {}}), raw('{"data":{"ok":true}}')])

    facade.ocr_national_card(image_file(), is_back=True, try_rotate=True)
    facade.ocr_cheque(image_file())
    bank_card = facade.ocr_bank_card(image_file())

    assert [request.path for request in executor.requests] == [
        "/alpha/ocr",
        "/alpha/cheque",
        "/alpha/bank/card",
    ]
    assert bank_card.data.data == {"ok": True}
    assert all(request.safety is OperationSafety.UNSAFE for request in executor.requests)


@pytest.mark.parametrize(
    "action",
    [
        lambda facade: facade.verify_video(national_id="bad", video=image_file(), line="challenge"),
        lambda facade: facade.verify_video(
            national_id="0013547891",
            video=MediaFile(content=b"video", filename="video.mp4", content_type="video/mp4"),
            line="challenge",
            max_accepted_dist=11,
        ),
        lambda facade: facade.ocr_national_card(
            MediaFile(content=b"text", filename="identity.txt", content_type="text/plain")
        ),
    ],
)
def test_kyc_input_errors_are_structured_and_prevent_network_io(action: object) -> None:
    """Invalid identity media and thresholds fail through the public exception hierarchy."""
    facade, executor = service([])

    with pytest.raises(JibitValidationError):
        action(facade)  # type: ignore[operator]

    assert not executor.requests


def test_media_repr_never_contains_binary_data() -> None:
    """Incidental diagnostics show metadata and length, never biometric bytes."""
    media = MediaFile(
        content=b"person-sensitive-biometrics",
        filename="face.jpg",
        content_type="image/jpeg",
    )

    assert "person-sensitive-biometrics" not in repr(media)
    assert "face.jpg" not in repr(media)
    assert "content_length=27" in repr(media)
