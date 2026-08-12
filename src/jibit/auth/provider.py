"""Service-aware token acquisition, caching, refresh, and recovery."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import SecretStr

from jibit.auth.locks import LockProvider
from jibit.auth.specs import AUTH_SPECS, AuthSpec
from jibit.auth.store import TokenStore
from jibit.auth.tokens import TokenState, jwt_expiry
from jibit.config import JibitConfig, ServiceConfig
from jibit.engine import RequestEngine, RequestOptions
from jibit.exceptions import (
    JibitAuthenticationError,
    JibitConfigurationError,
    JibitResponseError,
    JibitValidationError,
)
from jibit.logging import EventName, StructuredLogger
from jibit.retry import OperationSafety
from jibit.types import ServiceName


class ServiceAuthenticator:
    """Manage the complete token lifecycle for one Jibit service scope."""

    def __init__(
        self,
        *,
        service: ServiceName,
        config: JibitConfig,
        request_engine: RequestEngine,
        token_store: TokenStore,
        lock_provider: LockProvider,
        logger: StructuredLogger,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if service not in AUTH_SPECS:
            raise JibitConfigurationError(
                f"Automatic token authentication is not documented for '{service.value}'"
            )
        self.service = service
        self._config = config
        self._service_config = config.service(service)
        self._spec = AUTH_SPECS[service]
        self._request_engine = request_engine
        self._store = token_store
        self._locks = lock_provider
        self._logger = logger
        self._clock = clock
        self._cache_key = self._build_cache_key()

    def get_token(self) -> TokenState:
        """Return a valid cached token or safely refresh/acquire one."""
        now = self._clock()
        cached = self._safe_get()
        if cached is not None and cached.is_access_valid(
            now, self._config.auth.expiry_leeway_seconds
        ):
            return cached
        with self._locks.lock(self._cache_key):
            now = self._clock()
            cached = self._safe_get()
            if cached is not None and cached.is_access_valid(
                now, self._config.auth.expiry_leeway_seconds
            ):
                return cached
            return self._refresh_or_acquire(cached, now)

    def recover_from_unauthorized(self, rejected_access_token: str) -> TokenState:
        """Refresh once after 401 while reusing a token another worker already replaced."""
        with self._locks.lock(self._cache_key):
            cached = self._safe_get()
            now = self._clock()
            if (
                cached is not None
                and cached.access_value() != rejected_access_token
                and cached.is_access_valid(now, self._config.auth.expiry_leeway_seconds)
            ):
                return cached
            return self._refresh_or_acquire(cached, now)

    def invalidate(self) -> None:
        """Remove cached token state after a confirmed authentication rejection."""
        self._store.delete(self._cache_key)

    def _refresh_or_acquire(self, cached: TokenState | None, now: float) -> TokenState:
        if cached is not None and cached.is_refresh_valid(
            now, self._config.auth.expiry_leeway_seconds
        ):
            try:
                token = self._request_token(refresh=cached)
            except (JibitAuthenticationError, JibitValidationError):
                self._logger.emit(
                    logging.WARNING,
                    EventName.TOKEN_REFRESH_FAILED,
                    service=self.service.value,
                    reason="refresh_rejected",
                )
            else:
                self._store.set(self._cache_key, token)
                self._logger.emit(
                    logging.INFO,
                    EventName.TOKEN_REFRESHED,
                    service=self.service.value,
                    source="refresh_token",
                )
                return token
        token = self._request_token(refresh=None)
        self._store.set(self._cache_key, token)
        self._logger.emit(
            logging.INFO,
            EventName.TOKEN_ACQUIRED,
            service=self.service.value,
            source="credentials",
        )
        return token

    def _request_token(self, *, refresh: TokenState | None) -> TokenState:
        if refresh is None:
            body = self._generation_body(self._spec, self._service_config)
            path = self._spec.generate_path
            operation = "generate_token"
        else:
            refresh_value = refresh.refresh_value()
            if refresh_value is None:
                raise JibitAuthenticationError("No refresh token is available")
            body = {self._spec.refresh_token_field: refresh_value}
            if self._spec.refresh_access_token_field is not None:
                body[self._spec.refresh_access_token_field] = refresh.access_value()
            path = self._spec.refresh_path
            operation = "refresh_token"
        raw = self._request_engine.execute(
            RequestOptions(
                service=self.service,
                operation=operation,
                method="POST",
                path=path,
                safety=OperationSafety.IDEMPOTENT,
                json=body,
            )
        )
        parsed = raw.json()
        if not isinstance(parsed, dict):
            raise JibitResponseError("The token response must be a JSON object")
        return self._parse_token(parsed, previous=refresh)

    def _parse_token(self, body: dict[str, Any], *, previous: TokenState | None) -> TokenState:
        access = body.get(self._spec.access_response_field)
        refresh = body.get(self._spec.refresh_response_field)
        if not isinstance(access, str) or not access:
            raise JibitResponseError("The token response has no access token")
        if not isinstance(refresh, str) or not refresh:
            refresh = previous.refresh_value() if previous is not None else None
        now = self._clock()
        expires_at = jwt_expiry(access)
        if expires_at is None:
            ttl = self._integer_field(body, self._spec.expires_in_field)
            if ttl is None:
                ttl = (
                    self._spec.documented_access_ttl_seconds
                    or self._config.auth.unknown_access_token_ttl_seconds
                )
            expires_at = now + ttl if ttl is not None else None
        refresh_expires_at = None
        refresh_ttl = self._integer_field(body, self._spec.refresh_expires_in_field)
        if refresh_ttl is None:
            refresh_ttl = self._spec.documented_refresh_ttl_seconds
        if refresh_ttl is not None:
            refresh_expires_at = now + refresh_ttl
        elif previous is not None and refresh == previous.refresh_value():
            refresh_expires_at = previous.refresh_expires_at
        response_scopes = body.get("scopes")
        scopes = (
            response_scopes
            if isinstance(response_scopes, list | tuple | set)
            else self._service_config.scopes
        )
        return TokenState(
            access_token=SecretStr(access),
            refresh_token=SecretStr(refresh) if isinstance(refresh, str) else None,
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
            token_type=str(body.get("tokenType") or "Bearer"),
            scopes=tuple(str(scope) for scope in scopes),
        )

    @staticmethod
    def _integer_field(body: dict[str, Any], field_name: str | None) -> int | None:
        value = body.get(field_name) if field_name is not None else None
        return value if isinstance(value, int) and value > 0 else None

    @staticmethod
    def _generation_body(spec: AuthSpec, config: ServiceConfig) -> dict[str, Any]:
        credentials = config.credentials
        if credentials.api_key is None or credentials.secret_key is None:
            raise JibitConfigurationError(
                f"Service '{spec.service.value}' requires api_key and secret_key"
            )
        body: dict[str, Any] = {
            spec.api_key_field: credentials.api_key.get_secret_value(),
            spec.secret_key_field: credentials.secret_key.get_secret_value(),
        }
        if spec.scopes_field is not None and config.scopes:
            body[spec.scopes_field] = list(config.scopes)
        return body

    def _build_cache_key(self) -> str:
        credentials = self._service_config.credentials
        identifier = credentials.api_key or credentials.username
        if identifier is None:
            raise JibitConfigurationError(
                f"Service '{self.service.value}' has no cache-safe credential identifier"
            )
        service_base_url = self._service_config.base_url or self._config.base_url
        cache_identity = "\x00".join(
            (
                identifier.get_secret_value(),
                str(service_base_url).rstrip("/"),
                *sorted(self._service_config.scopes),
            )
        )
        digest = hashlib.sha256(cache_identity.encode()).hexdigest()[:20]
        return f"{self._config.auth.cache_key_prefix}:{self.service.value}:{digest}"

    def _safe_get(self) -> TokenState | None:
        try:
            return self._store.get(self._cache_key)
        except (TypeError, ValueError):
            self._store.delete(self._cache_key)
            return None
