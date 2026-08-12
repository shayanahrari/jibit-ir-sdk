"""Django settings integration and process-local client lifecycle."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any, cast

from jibit.auth.django import DjangoCacheTokenStore
from jibit.client import JibitClient
from jibit.exceptions import JibitConfigurationError

_lock = threading.RLock()
_client: JibitClient | None = None


def get_jibit_client() -> JibitClient:
    """Return one lazily configured Jibit client for the current Django process."""
    global _client
    with _lock:
        if _client is not None:
            return _client
        config, options = _load_settings()
        use_django_cache = options.pop("use_django_cache", False)
        if not isinstance(use_django_cache, bool):
            raise JibitConfigurationError("use_django_cache must be a boolean")
        cache_alias = options.pop("cache_alias", None)
        cache_key_prefix = options.pop("cache_key_prefix", None)
        if cache_alias is not None and (not isinstance(cache_alias, str) or not cache_alias):
            raise JibitConfigurationError("cache_alias must be a non-empty string")
        if cache_key_prefix is not None and (
            not isinstance(cache_key_prefix, str) or not cache_key_prefix
        ):
            raise JibitConfigurationError("cache_key_prefix must be a non-empty string")
        if options:
            unknown = ", ".join(sorted(options))
            raise JibitConfigurationError(f"Unknown Django integration options: {unknown}")
        token_store = None
        if use_django_cache:
            token_store = DjangoCacheTokenStore(
                alias=cache_alias or "default",
                key_prefix=cache_key_prefix or "jibit-token",
            )
        elif cache_alias is not None or cache_key_prefix is not None:
            raise JibitConfigurationError(
                "cache_alias and cache_key_prefix require use_django_cache=true"
            )
        _client = JibitClient.from_config(config, token_store=token_store)
        return _client


def close_jibit_client() -> None:
    """Close and clear the process-local client, primarily for shutdown and tests."""
    global _client
    with _lock:
        if _client is not None:
            _client.close()
            _client = None


def _load_settings() -> tuple[Mapping[str, Any], dict[str, Any]]:
    """Read and validate the application-owned `settings.JIBIT` mapping."""
    try:
        from django.conf import settings  # type: ignore[import-untyped]
        from django.core.exceptions import ImproperlyConfigured  # type: ignore[import-untyped]
    except ImportError:
        raise JibitConfigurationError(
            "Django integration requires the 'django' optional dependency"
        ) from None
    try:
        value = getattr(settings, "JIBIT", None)
    except ImproperlyConfigured:
        raise JibitConfigurationError("Django settings are not configured") from None
    if not isinstance(value, Mapping):
        raise JibitConfigurationError("Django setting JIBIT must be a mapping")
    raw = dict(value)
    integration = raw.pop("integration", {})
    if not isinstance(integration, Mapping):
        raise JibitConfigurationError("JIBIT['integration'] must be a mapping")
    return raw, cast(dict[str, Any], dict(integration))
