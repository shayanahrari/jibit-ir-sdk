"""Recursive redaction for logs, exceptions, and diagnostic metadata."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEY_PARTS = frozenset(
    {
        "access_token",
        "authorization",
        "account",
        "birth_date",
        "card",
        "client_secret",
        "credential",
        "cvv",
        "identity",
        "iban",
        "image",
        "kyc",
        "national_id",
        "national_code",
        "fida",
        "face",
        "file",
        "media",
        "mobile",
        "otp",
        "password",
        "refresh_token",
        "secret",
        "token",
        "video",
    }
)
_IBAN_RE = re.compile(r"\bIR\d{24}\b", re.IGNORECASE)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){16}(?!\d)")
_MOBILE_RE = re.compile(r"(?<!\d)(?:\+98|0098|0)?9\d{9}(?!\d)")
_NATIONAL_ID_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")


def _normalize_key(key: object) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower().replace("-", "_")


def is_sensitive_key(key: object) -> bool:
    """Return whether a field name is unsafe to include in diagnostic output."""
    normalized = _normalize_key(key)
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def redact_text(value: str) -> str:
    """Mask common financial and identity identifiers embedded in free text."""
    value = _IBAN_RE.sub(lambda match: f"IR{'*' * 20}{match.group()[-4:]}", value)
    value = _CARD_RE.sub(lambda match: f"{'*' * 12}{_digits(match.group())[-4:]}", value)
    value = _MOBILE_RE.sub(lambda match: f"{'*' * 7}{match.group()[-4:]}", value)
    return _NATIONAL_ID_RE.sub(lambda match: f"{'*' * 6}{match.group()[-4:]}", value)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def redact(value: Any, *, key: object | None = None) -> Any:
    """Recursively create a logging-safe copy of an arbitrary value."""
    if key is not None and is_sensitive_key(key):
        return REDACTED
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, bytes):
        return f"[BINARY:{len(value)} bytes]"
    if isinstance(value, Mapping):
        return {
            str(item_key): redact(item_value, key=item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, Sequence):
        return [redact(item) for item in value]
    return redact_text(str(value))
