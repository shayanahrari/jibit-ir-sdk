"""Typed request and response models for biometric and KYC APIs."""

from __future__ import annotations

import json
from typing import Any

from pydantic import Field, model_validator

from jibit.exceptions import JibitValidationError
from jibit.models import JibitModel


class KycResponse(JibitModel):
    """Represent the common biometric response envelope without exposing payloads in repr."""

    error_code: str | int | None = None
    error_message: str | None = None
    data: dict[str, Any] | list[Any] | str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_string_contract(cls, value: Any) -> Any:
        """Accept the catalog's JSON-string shape and observed object envelope."""
        if not isinstance(value, str):
            return value
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {"data": value}
        return decoded if isinstance(decoded, dict) else {"data": decoded}


class OcrData(JibitModel):
    """Represent stable OCR fields shared by documented national-card responses."""

    message: str | None = None
    best_accuracy: float | None = None
    id_num: str | None = None
    name: str | None = None
    family_name: str | None = None
    birth_date: str | None = None
    father_name: str | None = None
    expiration_date: str | None = None


class ChequeOcrData(JibitModel):
    """Represent stable fields documented for cheque OCR."""

    best_accuracy: float | None = None
    cheque_number: str | None = None


class FaceVerificationData(JibitModel):
    """Represent stable face-verification and liveness result sections."""

    status: bool | None = None
    verification_result: dict[str, Any] | None = None
    liveness_result: dict[str, Any] | None = None


class VoiceVerificationData(JibitModel):
    """Represent stable fields documented for voice verification."""

    state: bool | None = None
    similarity: float | None = None
    distance: float | None = None
    duration: str | float | None = None


class MediaFile:
    """Hold validated upload bytes and metadata with a secret-safe representation."""

    def __init__(self, *, content: bytes, filename: str, content_type: str) -> None:
        if not content:
            raise JibitValidationError("Media content must not be empty")
        if not filename:
            raise JibitValidationError("Media filename must not be empty")
        if not content_type:
            raise JibitValidationError("Media content_type must not be empty")
        self.content = content
        self.filename = filename
        self.content_type = content_type

    def __repr__(self) -> str:
        return f"MediaFile(content_type={self.content_type!r}, content_length={len(self.content)})"


class BiometricThresholds(JibitModel):
    """Collect optional provider thresholds while leaving safe provider defaults intact."""

    verification_threshold: float | None = Field(default=None, ge=0)
    liveness_threshold: float | None = Field(default=None, ge=0)
    asr_threshold: float | None = Field(default=None, ge=0)
