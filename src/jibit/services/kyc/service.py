"""High-level biometric and KYC operations with multipart payload isolation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jibit.engine import RequestOptions
from jibit.exceptions import ErrorContext, JibitValidationError
from jibit.response import APIResponse
from jibit.retry import OperationSafety
from jibit.services.base import RequestExecutor, typed_request
from jibit.services.kyc.models import KycResponse, MediaFile
from jibit.types import ContentPartType, MultipartPart, ServiceName

_SERVICE = ServiceName.KYC
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_OCR_BYTES = 4 * 1024 * 1024
_MAX_VIDEO_BYTES = 40 * 1024 * 1024


class KycService:
    """Expose biometric services using a configured static bearer token."""

    def __init__(self, executor: RequestExecutor) -> None:
        self._executor = executor

    def verify_video(
        self,
        *,
        national_id: str,
        video: MediaFile,
        line: str,
        birth_date: str | None = None,
        national_card_serial: str | None = None,
        spec_words: str | None = None,
        max_accepted_dist: int | None = None,
        asr_threshold: float | None = None,
        liveness_threshold: float | None = None,
        verification_threshold: float | None = None,
        check_liveness: bool | None = None,
    ) -> APIResponse[KycResponse]:
        """Perform documented one-step video identity verification."""
        if max_accepted_dist is not None and not 1 <= max_accepted_dist <= 10:
            raise self._invalid(
                "verify_video",
                "/alpha/v2/kyc",
                "max_accepted_dist must be between 1 and 10",
            )
        if len(national_id) != 10 or not national_id.isdigit():
            raise self._invalid(
                "verify_video", "/alpha/v2/kyc", "national_id must contain 10 digits"
            )
        if not line:
            raise self._invalid("verify_video", "/alpha/v2/kyc", "line must not be empty")
        self._validate_media(video, _MAX_VIDEO_BYTES, ("video/",), "verify_video", "/alpha/v2/kyc")
        fields = {
            "national_id": national_id,
            "line": line,
            "birth_date": birth_date,
            "national_card_serial": national_card_serial,
            "spec_words": spec_words,
            "max_accepted_dist": max_accepted_dist,
            "asr_threshold": asr_threshold,
            "liveness_threshold": liveness_threshold,
            "verification_threshold": verification_threshold,
            "check_liveness": check_liveness,
        }
        return self._post("verify_video", "/alpha/v2/kyc", fields, "video_file", video)

    def verify_photo(
        self,
        *,
        national_id: str,
        live_face: MediaFile,
        birth_date: str | None = None,
        serial: str | None = None,
        reference_face: MediaFile | None = None,
        liveness_threshold: float | None = None,
        verification_threshold: float | None = None,
    ) -> APIResponse[KycResponse]:
        """Compare a live face with civil or explicitly supplied reference data."""
        if len(national_id) != 10 or not national_id.isdigit():
            raise self._invalid(
                "verify_photo",
                "/alpha/v2/authorization",
                "national_id must contain 10 digits",
            )
        self._validate_media(
            live_face,
            _MAX_IMAGE_BYTES,
            ("image/",),
            "verify_photo",
            "/alpha/v2/authorization",
        )
        if reference_face is not None:
            self._validate_media(
                reference_face,
                _MAX_IMAGE_BYTES,
                ("image/",),
                "verify_photo",
                "/alpha/v2/authorization",
            )
        parts = self._fields(
            {
                "ssn": national_id,
                "birth_date": birth_date,
                "serial": serial,
                "liveness_threshold": liveness_threshold,
                "verification_threshold": verification_threshold,
            }
        )
        parts.append(self._file("live_face", live_face))
        if reference_face is not None:
            parts.append(self._file("api_face", reference_face))
        return self._execute("verify_photo", "/alpha/v2/authorization", parts)

    def ocr_national_card(
        self,
        image: MediaFile,
        *,
        is_back: bool | None = None,
        try_rotate: bool | None = None,
    ) -> APIResponse[KycResponse]:
        """Extract documented national-card fields from one image."""
        self._validate_media(image, _MAX_OCR_BYTES, ("image/",), "ocr_national_card", "/alpha/ocr")
        return self._post(
            "ocr_national_card",
            "/alpha/ocr",
            {"is_back": is_back, "try_rotate": try_rotate},
            "file",
            image,
        )

    def ocr_cheque(self, image: MediaFile) -> APIResponse[KycResponse]:
        """Extract the documented cheque number from one cheque image."""
        self._validate_media(image, _MAX_OCR_BYTES, ("image/",), "ocr_cheque", "/alpha/cheque")
        return self._post("ocr_cheque", "/alpha/cheque", {}, "file", image)

    def ocr_bank_card(self, image: MediaFile) -> APIResponse[KycResponse]:
        """Extract documented bank-card OCR data without logging the image."""
        self._validate_media(
            image, _MAX_OCR_BYTES, ("image/",), "ocr_bank_card", "/alpha/bank/card"
        )
        return self._post("ocr_bank_card", "/alpha/bank/card", {}, "file", image)

    def _post(
        self,
        operation: str,
        path: str,
        fields: Mapping[str, Any],
        file_name: str,
        media: MediaFile,
    ) -> APIResponse[KycResponse]:
        parts = self._fields(fields)
        parts.append(self._file(file_name, media))
        return self._execute(operation, path, parts)

    def _execute(
        self, operation: str, path: str, parts: list[MultipartPart]
    ) -> APIResponse[KycResponse]:
        return typed_request(
            self._executor,
            RequestOptions(
                service=_SERVICE,
                operation=operation,
                method="POST",
                path=path,
                safety=OperationSafety.UNSAFE,
                multipart=tuple(parts),
            ),
            KycResponse,
        )

    @staticmethod
    def _fields(values: Mapping[str, Any]) -> list[MultipartPart]:
        return [
            MultipartPart(
                name=name,
                kind=ContentPartType.FIELD,
                value=str(value).lower() if isinstance(value, bool) else str(value),
            )
            for name, value in values.items()
            if value is not None
        ]

    @staticmethod
    def _file(name: str, media: MediaFile) -> MultipartPart:
        return MultipartPart(
            name=name,
            kind=ContentPartType.FILE,
            value=media.content,
            filename=media.filename,
            content_type=media.content_type,
        )

    @staticmethod
    def _validate_media(
        media: MediaFile,
        limit: int,
        prefixes: tuple[str, ...],
        operation: str,
        path: str,
    ) -> None:
        if len(media.content) > limit:
            raise KycService._invalid(
                operation, path, f"media exceeds the documented {limit} byte limit"
            )
        if not media.content_type.startswith(prefixes):
            raise KycService._invalid(
                operation, path, "media content_type is not supported for this operation"
            )

    @staticmethod
    def _invalid(operation: str, path: str, message: str) -> JibitValidationError:
        return JibitValidationError(
            message,
            context=ErrorContext(
                service=_SERVICE.value,
                operation=operation,
                method="POST",
                endpoint=path,
                retryable=False,
            ),
        )
