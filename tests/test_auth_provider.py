"""Service authentication, refresh, concurrency, and recovery tests."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import cast

import pytest

from jibit.auth.authenticated import AuthenticatedRequestEngine
from jibit.auth.locks import ThreadLockProvider
from jibit.auth.provider import ServiceAuthenticator
from jibit.auth.store import InMemoryTokenStore
from jibit.config import AuthConfig, JibitConfig
from jibit.engine import RequestEngine, RequestOptions
from jibit.exceptions import (
    ErrorContext,
    JibitAuthenticationError,
    JibitConfigurationError,
    JibitResponseError,
)
from jibit.logging import StructuredLogger
from jibit.response import RawResponse
from jibit.retry import OperationSafety
from jibit.types import ServiceName


class StubRequestEngine:
    """Return or raise predefined outcomes while recording request options."""

    def __init__(self, outcomes: list[RawResponse | Exception], *, delay: float = 0) -> None:
        self.outcomes = outcomes
        self.delay = delay
        self.requests: list[RequestOptions] = []

    def execute(self, options: RequestOptions) -> RawResponse:
        """Record and resolve one request."""
        self.requests.append(options)
        if self.delay:
            time.sleep(self.delay)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def raw_json(value: object, *, correlation_id: str = "cid") -> RawResponse:
    """Create a JSON raw response."""
    return RawResponse(200, {}, json.dumps(value).encode(), correlation_id)


def config_for(
    service: ServiceName,
    *,
    auth: AuthConfig | None = None,
    scopes: tuple[str, ...] = (),
) -> JibitConfig:
    """Create a service configuration with synthetic credentials."""
    return JibitConfig.from_mapping(
        {
            "auth": (auth or AuthConfig()).model_dump(),
            service.value: {
                "api_key": "api-key",
                "secret_key": "secret-key",
                "scopes": scopes,
            },
        }
    )


def authenticator(
    service: ServiceName,
    engine: StubRequestEngine,
    *,
    store: InMemoryTokenStore | None = None,
    clock: float = 1000,
    config: JibitConfig | None = None,
) -> ServiceAuthenticator:
    """Build an authenticator with deterministic dependencies."""
    return ServiceAuthenticator(
        service=service,
        config=config or config_for(service),
        request_engine=cast(RequestEngine, engine),
        token_store=store or InMemoryTokenStore(),
        lock_provider=ThreadLockProvider(),
        logger=StructuredLogger(logging.getLogger("tests.auth")),
        clock=lambda: clock,
    )


@pytest.mark.parametrize(
    ("service", "expected_path", "api_field"),
    [
        (ServiceName.PAYMENT_GATEWAY, "/ppg/v3/tokens", "apiKey"),
        (ServiceName.TRANSFERS, "/trf/v2/tokens/generate", "apiKey"),
        (ServiceName.COBANK, "/cobank/v1/tokens/generate", "apiKey"),
        (ServiceName.IDENTICATOR, "/ide/v1/tokens/generate", "apiKey"),
        (
            ServiceName.DIRECT_DEBIT,
            "/directdebit/api/v1/auth/authenticate",
            "api_key",
        ),
        (ServiceName.SMS, "/pulse/api/v1/auth/authenticate", "api_key"),
        (ServiceName.CONTRACTS, "/mzahub/v1/auth/login", "apiKey"),
    ],
)
def test_service_specific_generation_contracts(
    service: ServiceName,
    expected_path: str,
    api_field: str,
) -> None:
    """Each service uses its documented path and request-field casing."""
    response_fields = (
        {"access_token": "access", "refresh_token": "refresh"}
        if service in {ServiceName.DIRECT_DEBIT, ServiceName.SMS}
        else {"accessToken": "access", "refreshToken": "refresh"}
    )
    engine = StubRequestEngine([raw_json(response_fields)])

    token = authenticator(service, engine).get_token()

    assert token.access_value() == "access"
    assert engine.requests[0].path == expected_path
    assert engine.requests[0].json[api_field] == "api-key"
    assert "secret-key" not in repr(engine.requests[0])


def test_cached_token_skips_network_and_invalidates() -> None:
    """A valid token is reused until explicitly invalidated."""
    store = InMemoryTokenStore()
    engine = StubRequestEngine([raw_json({"accessToken": "access", "refreshToken": "refresh"})])
    auth = authenticator(ServiceName.PAYMENT_GATEWAY, engine, store=store)

    first = auth.get_token()
    second = auth.get_token()
    auth.invalidate()

    assert first is second
    assert len(engine.requests) == 1


def test_token_cache_identity_includes_base_url_and_scopes() -> None:
    """Tokens from distinct environments or scope grants never share cache entries."""
    store = InMemoryTokenStore()
    engine = StubRequestEngine(
        [
            raw_json({"accessToken": "scope-a", "refreshToken": "refresh-a"}),
            raw_json({"accessToken": "scope-b", "refreshToken": "refresh-b"}),
        ]
    )
    first = authenticator(
        ServiceName.COBANK,
        engine,
        store=store,
        config=config_for(ServiceName.COBANK, scopes=("SETTLEMENT",)),
    )
    second = authenticator(
        ServiceName.COBANK,
        engine,
        store=store,
        config=config_for(ServiceName.COBANK, scopes=("ACCOUNT",)),
    )

    assert first.get_token().access_value() == "scope-a"
    assert second.get_token().access_value() == "scope-b"
    assert len(engine.requests) == 2


def test_identicator_refresh_sends_access_and_refresh_tokens() -> None:
    """Identicator uses the documented two-token refresh request."""
    engine = StubRequestEngine(
        [
            raw_json({"accessToken": "old-access", "refreshToken": "old-refresh"}),
            raw_json({"accessToken": "new-access", "refreshToken": "new-refresh"}),
        ]
    )
    store = InMemoryTokenStore()
    auth = authenticator(ServiceName.IDENTICATOR, engine, store=store, clock=1000)
    first = auth.get_token()
    auth = authenticator(
        ServiceName.IDENTICATOR,
        engine,
        store=store,
        clock=90_000,
    )

    refreshed = auth.get_token()

    assert first.access_value() == "old-access"
    assert refreshed.access_value() == "new-access"
    assert engine.requests[1].json == {
        "refreshToken": "old-refresh",
        "accessToken": "old-access",
    }


def test_refresh_rejection_falls_back_to_credentials(caplog: object) -> None:
    """A rejected refresh token is replaced through credential authentication once."""
    store = InMemoryTokenStore()
    engine = StubRequestEngine(
        [
            raw_json({"accessToken": "initial", "refreshToken": "refresh"}),
            JibitAuthenticationError("refresh rejected"),
            raw_json({"accessToken": "replacement", "refreshToken": "replacement-refresh"}),
        ]
    )
    auth = authenticator(ServiceName.PAYMENT_GATEWAY, engine, store=store)
    auth.get_token()
    late_auth = authenticator(
        ServiceName.PAYMENT_GATEWAY,
        engine,
        store=store,
        clock=90_000,
    )

    with caplog.at_level(logging.WARNING, logger="tests.auth"):  # type: ignore[attr-defined]
        token = late_auth.get_token()

    assert token.access_value() == "replacement"
    assert len(engine.requests) == 3
    assert caplog.records[-1].event == "jibit.token.refresh_failed"  # type: ignore[attr-defined]


def test_contract_expiry_and_previous_refresh_token_are_preserved() -> None:
    """MzaHub expiry fields schedule refresh and an omitted replacement token is retained."""
    engine = StubRequestEngine(
        [
            raw_json(
                {
                    "accessToken": "access",
                    "refreshToken": "refresh",
                    "expiresIn": 60,
                    "refreshTokenExpiresIn": 120,
                    "tokenType": "JWT",
                }
            ),
            raw_json({"accessToken": "new-access", "expiresIn": 60}),
        ]
    )
    store = InMemoryTokenStore()
    first_auth = authenticator(ServiceName.CONTRACTS, engine, store=store, clock=1000)
    first = first_auth.get_token()
    second_auth = authenticator(ServiceName.CONTRACTS, engine, store=store, clock=1001)
    second = second_auth.get_token()

    assert first.expires_at == 1060
    assert first.refresh_expires_at == 1120
    assert first.token_type == "JWT"
    assert second.refresh_value() == "refresh"


def test_unknown_opaque_token_ttl_is_configurable() -> None:
    """Consumers can schedule refresh when an opaque-token contract has no expiry field."""
    auth_config = AuthConfig(unknown_access_token_ttl_seconds=600)
    engine = StubRequestEngine([raw_json({"access_token": "opaque", "refresh_token": "refresh"})])
    auth = authenticator(
        ServiceName.SMS,
        engine,
        clock=1000,
        config=config_for(ServiceName.SMS, auth=auth_config),
    )

    assert auth.get_token().expires_at == 1600


@pytest.mark.parametrize("body", [{}, [], {"accessToken": ""}])
def test_malformed_token_response_is_rejected(body: object) -> None:
    """Invalid token responses are never cached or used for authorization."""
    auth = authenticator(ServiceName.PAYMENT_GATEWAY, StubRequestEngine([raw_json(body)]))
    with pytest.raises(JibitResponseError):
        auth.get_token()


def test_missing_api_key_pair_and_unsupported_service_are_rejected() -> None:
    """Automatic auth refuses undocumented KYC auth and incompatible credentials."""
    username_config = JibitConfig.from_mapping(
        {"sms": {"username": "user", "password": "password"}}
    )
    with pytest.raises(JibitConfigurationError, match="api_key"):
        authenticator(
            ServiceName.SMS,
            StubRequestEngine([]),
            config=username_config,
        ).get_token()
    with pytest.raises(JibitConfigurationError, match="not documented"):
        ServiceAuthenticator(
            service=ServiceName.KYC,
            config=JibitConfig(),
            request_engine=cast(RequestEngine, StubRequestEngine([])),
            token_store=InMemoryTokenStore(),
            lock_provider=ThreadLockProvider(),
            logger=StructuredLogger(logging.getLogger("tests.auth")),
        )


def test_thread_lock_prevents_token_generation_stampede() -> None:
    """Concurrent callers share one generated token inside a process."""
    engine = StubRequestEngine(
        [raw_json({"accessToken": "shared", "refreshToken": "refresh"})],
        delay=0.03,
    )
    auth = authenticator(ServiceName.PAYMENT_GATEWAY, engine)

    with ThreadPoolExecutor(max_workers=8) as pool:
        tokens = list(pool.map(lambda _: auth.get_token(), range(8)))

    assert {token.access_value() for token in tokens} == {"shared"}
    assert len(engine.requests) == 1


def test_safe_401_is_refreshed_and_replayed_once() -> None:
    """A read-only request uses a refreshed token after one authentication rejection."""
    engine = StubRequestEngine(
        [
            raw_json({"accessToken": "old", "refreshToken": "refresh"}),
            JibitAuthenticationError("expired", context=ErrorContext(status_code=401)),
            raw_json({"accessToken": "new", "refreshToken": "new-refresh"}),
            raw_json({"ok": True}),
        ]
    )
    auth = authenticator(ServiceName.PAYMENT_GATEWAY, engine)
    authorized = AuthenticatedRequestEngine(cast(RequestEngine, engine), auth)

    result = authorized.execute(
        RequestOptions(
            ServiceName.PAYMENT_GATEWAY,
            "get_purchase",
            "GET",
            "/ppg/v3/purchases/1",
            OperationSafety.READ_ONLY,
        )
    )

    assert result.json() == {"ok": True}
    assert engine.requests[1].headers["Authorization"] == "Bearer old"
    assert engine.requests[3].headers["Authorization"] == "Bearer new"


def test_unsafe_401_is_not_replayed_and_second_401_invalidates() -> None:
    """Unsafe requests never replay, and repeated safe rejection clears cached state."""
    unsafe_engine = StubRequestEngine(
        [
            raw_json({"accessToken": "old", "refreshToken": "refresh"}),
            JibitAuthenticationError("rejected"),
        ]
    )
    unsafe_auth = authenticator(ServiceName.PAYMENT_GATEWAY, unsafe_engine)
    unsafe = AuthenticatedRequestEngine(cast(RequestEngine, unsafe_engine), unsafe_auth)
    with pytest.raises(JibitAuthenticationError):
        unsafe.execute(
            RequestOptions(
                ServiceName.PAYMENT_GATEWAY,
                "create_purchase",
                "POST",
                "/ppg/v3/purchases",
                OperationSafety.UNSAFE,
            )
        )
    assert len(unsafe_engine.requests) == 2

    safe_engine = StubRequestEngine(
        [
            raw_json({"accessToken": "old", "refreshToken": "refresh"}),
            JibitAuthenticationError("expired"),
            raw_json({"accessToken": "new", "refreshToken": "new-refresh"}),
            JibitAuthenticationError("still rejected"),
        ]
    )
    safe_auth = authenticator(ServiceName.PAYMENT_GATEWAY, safe_engine)
    safe = AuthenticatedRequestEngine(cast(RequestEngine, safe_engine), safe_auth)
    with pytest.raises(JibitAuthenticationError):
        safe.execute(
            RequestOptions(
                ServiceName.PAYMENT_GATEWAY,
                "get_purchase",
                "GET",
                "/ppg/v3/purchases/1",
                OperationSafety.READ_ONLY,
            )
        )
    assert len(safe_engine.requests) == 4
