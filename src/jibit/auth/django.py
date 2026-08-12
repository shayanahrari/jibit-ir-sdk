"""Optional token-store adapter for Django's configured cache backend."""

from __future__ import annotations

from typing import Any, Protocol

from jibit.auth.tokens import TokenState


class DjangoCacheBackend(Protocol):
    """Minimal Django cache surface required by the token store."""

    def get(self, key: str, default: Any = None) -> Any:
        """Return a cached value."""

    def set(self, key: str, value: Any, timeout: float | None = None) -> Any:
        """Persist a cached value."""

    def delete(self, key: str) -> Any:
        """Delete a cached value."""


class DjangoCacheTokenStore:
    """Persist token dictionaries in an application-selected Django cache."""

    def __init__(
        self,
        *,
        alias: str = "default",
        cache: DjangoCacheBackend | None = None,
        key_prefix: str = "jibit-token",
    ) -> None:
        if cache is None:
            from django.core.cache import caches  # type: ignore[import-untyped]

            cache = caches[alias]
        self._cache = cache
        self._key_prefix = key_prefix

    def get(self, key: str) -> TokenState | None:
        """Read and validate cached token data."""
        value = self._cache.get(self._key(key))
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("Django cache returned invalid token state")
        return TokenState.from_cache_data(value)

    def set(self, key: str, token: TokenState) -> None:
        """Store token data using the backend's normal security and retention policy."""
        self._cache.set(self._key(key), token.to_cache_data(), timeout=None)

    def delete(self, key: str) -> None:
        """Remove cached token data."""
        self._cache.delete(self._key(key))

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"
