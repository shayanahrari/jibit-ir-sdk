"""Optional Redis token-store and distributed lock adapters."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from typing import Any, Protocol, cast

from jibit.auth.tokens import TokenState


class RedisClient(Protocol):
    """Minimal Redis client surface required by SDK adapters."""

    def get(self, name: str) -> bytes | str | None:
        """Return a serialized value."""

    def set(self, name: str, value: str) -> Any:
        """Persist a serialized value."""

    def delete(self, *names: str) -> Any:
        """Delete serialized values."""

    def lock(
        self,
        name: str,
        *,
        timeout: float,
        blocking_timeout: float,
    ) -> AbstractContextManager[Any]:
        """Return a Redis-backed distributed lock."""


class RedisTokenStore:
    """Persist token state as compact JSON in an application-owned Redis deployment."""

    def __init__(self, client: RedisClient, *, key_prefix: str = "jibit-token") -> None:
        self._client = client
        self._key_prefix = key_prefix

    def get(self, key: str) -> TokenState | None:
        """Read and validate serialized token state."""
        value = self._client.get(self._key(key))
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("Redis returned invalid token state")
        return TokenState.from_cache_data(parsed)

    def set(self, key: str, token: TokenState) -> None:
        """Store serialized token state."""
        self._client.set(self._key(key), json.dumps(token.to_cache_data(), separators=(",", ":")))

    def delete(self, key: str) -> None:
        """Remove serialized token state."""
        self._client.delete(self._key(key))

    def _key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"


class RedisLockProvider:
    """Coordinate token refresh across processes through Redis locks."""

    def __init__(
        self,
        client: RedisClient,
        *,
        key_prefix: str = "jibit-lock",
        timeout: float = 30,
        blocking_timeout: float = 35,
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix
        self._timeout = timeout
        self._blocking_timeout = blocking_timeout

    def lock(self, key: str) -> AbstractContextManager[None]:
        """Return a typed Redis lock context manager."""
        return cast(
            AbstractContextManager[None],
            self._client.lock(
                f"{self._key_prefix}:{key}",
                timeout=self._timeout,
                blocking_timeout=self._blocking_timeout,
            ),
        )
