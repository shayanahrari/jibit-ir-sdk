"""Optional Django settings, cache, logging, and singleton integration tests."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from django.conf import settings  # type: ignore[import-untyped]
from django.core.cache import cache  # type: ignore[import-untyped]
from pydantic import SecretStr

from jibit.auth.tokens import TokenState
from jibit.django import close_jibit_client, get_jibit_client
from jibit.exceptions import JibitConfigurationError

if not settings.configured:
    settings.configure(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        JIBIT={},
    )


@pytest.fixture(autouse=True)
def reset_django_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Prevent settings and process-local client state from crossing test boundaries."""
    close_jibit_client()
    monkeypatch.setattr(settings, "JIBIT", {}, raising=False)
    yield
    close_jibit_client()


def test_get_client_uses_settings_cache_and_process_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Django settings create one client and a working application-owned token store."""
    monkeypatch.setattr(
        settings,
        "JIBIT",
        {
            "payment_gateway": {"api_key": "key", "secret_key": "secret"},
            "integration": {"use_django_cache": True},
        },
    )
    first = get_jibit_client()
    second = get_jibit_client()

    assert first is second
    assert first.config.logging.logger_name == "jibit_sdk"
    first._token_store.set(
        "test-key",
        TokenState(access_token=SecretStr("access"), expires_at=9999999999),
    )
    assert cache.get("jibit-token:test-key")["access_token"] == "access"


def test_core_uses_django_logger_without_configuring_handlers() -> None:
    """The Django facade reuses standard logging and never installs global handlers."""
    logger = logging.getLogger("jibit_sdk")
    before = tuple(logger.handlers)

    get_jibit_client()

    assert tuple(logger.handlers) == before


def test_invalid_django_setting_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid settings fail before creating network infrastructure."""
    monkeypatch.setattr(settings, "JIBIT", [])
    with pytest.raises(JibitConfigurationError, match="mapping"):
        get_jibit_client()


def test_cache_options_require_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cache alias cannot silently turn on token persistence."""
    monkeypatch.setattr(settings, "JIBIT", {"integration": {"cache_alias": "default"}})
    with pytest.raises(JibitConfigurationError, match="use_django_cache"):
        get_jibit_client()


@pytest.mark.parametrize(
    ("integration", "message"),
    [
        ({"use_django_cache": "false"}, "boolean"),
        ({"use_django_cache": True, "cache_alias": ""}, "cache_alias"),
        ({"unknown": "secret-like-value"}, "Unknown Django integration options: unknown"),
    ],
)
def test_integration_options_are_strict_and_error_safe(
    monkeypatch: pytest.MonkeyPatch,
    integration: dict[str, object],
    message: str,
) -> None:
    """Integration settings reject coercion and never echo unknown option values."""
    monkeypatch.setattr(settings, "JIBIT", {"integration": integration})

    with pytest.raises(JibitConfigurationError, match=message) as captured:
        get_jibit_client()

    assert "secret-like-value" not in str(captured.value)
