"""Response container tests."""

import pytest

from jibit.exceptions import JibitResponseError
from jibit.response import APIResponse, RawResponse, StatusResult


def test_raw_and_typed_response_access() -> None:
    """Advanced users can inspect raw metadata alongside typed data."""
    raw = RawResponse(200, {"content-type": "application/json"}, b'{"value": 3}', "cid")
    typed = APIResponse({"value": 3}, raw)
    status = StatusResult(True, 200, b"optional")

    assert raw.text == '{"value": 3}'
    assert raw.json() == {"value": 3}
    assert typed.data["value"] == 3
    assert status.raw_body == b"optional"


def test_invalid_json_raises_structured_error() -> None:
    """Malformed upstream JSON retains status and correlation context."""
    raw = RawResponse(200, {}, b"not-json", "cid")

    with pytest.raises(JibitResponseError) as captured:
        raw.json()

    assert captured.value.context.status_code == 200
    assert captured.value.context.correlation_id == "cid"
