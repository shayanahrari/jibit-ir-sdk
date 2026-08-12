"""Token-store protocol and thread-safe in-memory implementation."""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from jibit.auth.tokens import TokenState


class TokenStore(Protocol):
    """Persist service-scoped token state behind an application-selected backend."""

    def get(self, key: str) -> TokenState | None:
        """Return cached token state when available."""

    def set(self, key: str, token: TokenState) -> None:
        """Persist token state."""

    def delete(self, key: str) -> None:
        """Remove token state."""


class InMemoryTokenStore:
    """Store tokens safely within one process using a re-entrant lock."""

    def __init__(self) -> None:
        self._tokens: dict[str, TokenState] = {}
        self._lock = RLock()

    def get(self, key: str) -> TokenState | None:
        """Return the current token state for a cache key."""
        with self._lock:
            return self._tokens.get(key)

    def set(self, key: str, token: TokenState) -> None:
        """Replace the token state for a cache key."""
        with self._lock:
            self._tokens[key] = token

    def delete(self, key: str) -> None:
        """Remove token state without failing when it is already absent."""
        with self._lock:
            self._tokens.pop(key, None)
