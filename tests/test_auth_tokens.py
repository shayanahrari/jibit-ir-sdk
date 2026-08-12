"""Token state, JWT expiry, and cache adapter tests."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from pydantic import SecretStr

from jibit.auth.django import DjangoCacheTokenStore
from jibit.auth.redis import RedisLockProvider, RedisTokenStore
from jibit.auth.tokens import TokenState, jwt_expiry


def make_jwt(expiry: int) -> str:
    """Create an unsigned JWT-like value for expiry scheduling tests."""
    payload = base64.urlsafe_b64encode(json.dumps({"exp": expiry}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


def token_state() -> TokenState:
    """Create predictable secret token state."""
    return TokenState(
        SecretStr("access-secret"),
        SecretStr("refresh-secret"),
        expires_at=200,
        refresh_expires_at=300,
        scopes=("READ",),
    )


def test_token_state_hides_values_and_tracks_expiry() -> None:
    """Token values remain secret while expiry and scopes remain inspectable."""
    token = token_state()

    assert "access-secret" not in repr(token)
    assert "refresh-secret" not in repr(token)
    assert token.access_value() == "access-secret"
    assert token.refresh_value() == "refresh-secret"
    assert token.is_access_valid(100, 60)
    assert not token.is_access_valid(150, 60)
    assert token.is_refresh_valid(200, 60)
    assert not token.is_refresh_valid(250, 60)


def test_token_cache_round_trip_and_validation() -> None:
    """Serialized cache values reconstruct an equivalent secret-safe token."""
    token = token_state()
    reconstructed = TokenState.from_cache_data(token.to_cache_data())

    assert reconstructed.access_value() == token.access_value()
    assert reconstructed.scopes == ("READ",)
    with pytest.raises(ValueError, match="no access token"):
        TokenState.from_cache_data({})


def test_jwt_expiry_is_only_a_parsing_hint() -> None:
    """Valid expiry claims are read while malformed tokens return no hint."""
    assert jwt_expiry(make_jwt(1_800_000_000)) == 1_800_000_000
    assert jwt_expiry("opaque-token") is None
    assert jwt_expiry("a.invalid-json.c") is None


class FakeCache:
    """Minimal cache backend for the Django adapter."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any, timeout: float | None = None) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


def test_django_cache_token_store_round_trip() -> None:
    """Django cache integration stores plain data rather than SDK implementation objects."""
    cache = FakeCache()
    store = DjangoCacheTokenStore(cache=cache, key_prefix="sdk")

    assert store.get("key") is None
    store.set("key", token_state())
    cached = store.get("key")
    assert cached is not None
    assert cached.access_value() == "access-secret"
    store.delete("key")
    assert store.get("key") is None
    cache.values["sdk:key"] = "invalid"
    with pytest.raises(ValueError, match="invalid token state"):
        store.get("key")


class FakeRedis:
    """Minimal Redis client with an inspectable distributed lock."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.lock_names: list[str] = []

    def get(self, name: str) -> bytes | None:
        value = self.values.get(name)
        return value.encode() if value is not None else None

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, *names: str) -> None:
        for name in names:
            self.values.pop(name, None)

    @contextmanager
    def lock(
        self,
        name: str,
        *,
        timeout: float,
        blocking_timeout: float,
    ) -> Iterator[None]:
        assert timeout == 10
        assert blocking_timeout == 12
        self.lock_names.append(name)
        yield


def test_redis_store_and_distributed_lock_round_trip() -> None:
    """Redis adapters serialize tokens and provide a namespaced lock."""
    redis = FakeRedis()
    store = RedisTokenStore(redis, key_prefix="sdk")

    assert store.get("key") is None
    store.set("key", token_state())
    cached = store.get("key")
    assert cached is not None
    assert cached.refresh_value() == "refresh-secret"
    store.delete("key")
    redis.values["sdk:key"] = "[]"
    with pytest.raises(ValueError, match="invalid token state"):
        store.get("key")

    locks = RedisLockProvider(redis, key_prefix="locks", timeout=10, blocking_timeout=12)
    with locks.lock("token"):
        pass
    assert redis.lock_names == ["locks:token"]
