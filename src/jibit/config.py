"""Typed SDK configuration with secret-safe representations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, model_validator
from typing_extensions import Self

from jibit.__about__ import __version__
from jibit.types import ServiceName


class TimeoutConfig(BaseModel):
    """Configure HTTP timeouts in seconds for each network phase."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connect: float = Field(default=5.0, gt=0)
    read: float = Field(default=30.0, gt=0)
    write: float = Field(default=30.0, gt=0)
    pool: float = Field(default=5.0, gt=0)


class RetryConfig(BaseModel):
    """Configure conservative retries for explicitly safe operations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=3, ge=1, le=10)
    base_delay: float = Field(default=0.25, ge=0)
    max_delay: float = Field(default=4.0, ge=0)
    jitter_ratio: float = Field(default=0.1, ge=0, le=1)

    @model_validator(mode="after")
    def validate_delay_bounds(self) -> Self:
        """Reject a maximum delay smaller than the initial delay."""
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be greater than or equal to base_delay")
        return self


class LoggingConfig(BaseModel):
    """Configure SDK-owned structured events without configuring handlers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    logger_name: str = Field(default="jibit_sdk", min_length=1)
    enabled: bool = True
    include_payload_diagnostics: bool = False


class AuthConfig(BaseModel):
    """Configure token expiry handling and cache namespace behavior."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expiry_leeway_seconds: int = Field(default=60, ge=0, le=3600)
    unknown_access_token_ttl_seconds: int | None = Field(default=None, ge=60)
    cache_key_prefix: str = Field(default="jibit:tokens", min_length=1, max_length=100)


class ServiceCredentials(BaseModel):
    """Store common credential forms while keeping values out of representations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key: SecretStr | None = None
    secret_key: SecretStr | None = None
    username: SecretStr | None = None
    password: SecretStr | None = None

    @model_validator(mode="after")
    def require_a_complete_credential_pair(self) -> Self:
        """Require either an API-key pair or a username/password pair."""
        api_pair = self.api_key is not None or self.secret_key is not None
        user_pair = self.username is not None or self.password is not None
        if api_pair and (self.api_key is None or self.secret_key is None):
            raise ValueError("api_key and secret_key must be configured together")
        if user_pair and (self.username is None or self.password is None):
            raise ValueError("username and password must be configured together")
        if not api_pair and not user_pair:
            raise ValueError("a supported credential pair is required")
        return self


class ServiceConfig(BaseModel):
    """Configure credentials and optional URL overrides for one service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    credentials: ServiceCredentials
    base_url: HttpUrl | None = None
    enabled: bool = True
    scopes: tuple[str, ...] = ()


class JibitConfig(BaseModel):
    """Configure the SDK and all enabled service authentication scopes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: HttpUrl = HttpUrl("https://napi.jibit.ir")
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    services: dict[ServiceName, ServiceConfig] = Field(default_factory=dict)
    verify_ssl: bool = True
    user_agent: str = Field(default=f"jibit-ir-sdk/{__version__}", min_length=1)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Self:
        """Validate a mapping and accept service names at the top level for convenience."""
        raw = dict(value)
        services = dict(raw.pop("services", {}))
        for service in ServiceName:
            if service.value in raw:
                services[service] = raw.pop(service.value)
        credential_keys = {"api_key", "secret_key", "username", "password"}
        for service_name, raw_service in services.items():
            if isinstance(raw_service, Mapping) and "credentials" not in raw_service:
                raw_service = dict(raw_service)
                credentials = {
                    key: raw_service.pop(key) for key in credential_keys if key in raw_service
                }
                if credentials:
                    raw_service["credentials"] = credentials
                services[service_name] = raw_service
        raw["services"] = services
        return cls.model_validate(raw)

    def service(self, name: ServiceName) -> ServiceConfig:
        """Return an enabled service configuration or raise a safe configuration error."""
        from jibit.exceptions import JibitConfigurationError

        config = self.services.get(name)
        if config is None or not config.enabled:
            raise JibitConfigurationError(f"Service '{name.value}' is not configured")
        return config
