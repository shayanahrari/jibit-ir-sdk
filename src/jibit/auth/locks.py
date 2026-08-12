"""Local and distributed token-refresh lock protocols."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from threading import Lock, RLock
from typing import Protocol


class LockProvider(Protocol):
    """Coordinate token refresh for a service credential scope."""

    def lock(self, key: str) -> AbstractContextManager[None]:
        """Return a blocking context manager for one cache key."""


class ThreadLockProvider:
    """Prevent refresh stampedes between threads in one Python process."""

    def __init__(self) -> None:
        self._locks: dict[str, Lock] = {}
        self._guard = RLock()

    @contextmanager
    def lock(self, key: str) -> Iterator[None]:
        """Hold a stable per-key lock for the duration of token refresh."""
        with self._guard:
            token_lock = self._locks.setdefault(key, Lock())
        with token_lock:
            yield
