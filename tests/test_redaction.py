"""Sensitive-data redaction tests."""

from jibit.redaction import REDACTED, is_sensitive_key, redact, redact_text


def test_sensitive_keys_are_removed_recursively() -> None:
    """Nested secrets, OTPs, and media are never retained in diagnostics."""
    payload = {
        "authorization": "Bearer top-secret",
        "customer": {
            "nationalId": "0013547891",
            "nested": [{"otpCode": "123456"}, {"safe": "visible"}],
        },
        "imageUrl": "https://private.example/image.jpg",
        "birthDate": "13600101",
        "fida": "foreign-id",
        "iban": "IR820540102680020817909002",
        "mediaFile": "private.jpg",
    }

    safe = redact(payload)

    assert safe["authorization"] == REDACTED
    assert safe["customer"]["nationalId"] == REDACTED
    assert safe["customer"]["nested"][0]["otpCode"] == REDACTED
    assert safe["customer"]["nested"][1]["safe"] == "visible"
    assert safe["imageUrl"] == REDACTED
    assert safe["birthDate"] == REDACTED
    assert safe["fida"] == REDACTED
    assert safe["iban"] == REDACTED
    assert safe["mediaFile"] == REDACTED


def test_free_text_identifiers_are_masked() -> None:
    """Known identifier shapes preserve only the minimum diagnostic suffix."""
    text = (
        "IBAN IR820540102680020817909002 card 6219-8610-2850-0042 "
        "mobile +989121234567 national 0013547891"
    )

    safe = redact_text(text)

    assert "IR820540102680020817909002" not in safe
    assert "6219-8610-2850-0042" not in safe
    assert "+989121234567" not in safe
    assert "0013547891" not in safe
    assert safe.count("9002") == 1
    assert "0042" in safe


def test_binary_and_scalar_values_have_predictable_representations() -> None:
    """Binary values are summarized while non-sensitive scalars remain useful."""
    assert redact(b"private") == "[BINARY:7 bytes]"
    assert redact([True, 3, None]) == [True, 3, None]
    assert is_sensitive_key("refreshToken")
    assert not is_sensitive_key("correlation_id")
    assert redact(object()).startswith("<object object at")
