"""Documented token endpoint contracts for each supported service."""

from __future__ import annotations

from dataclasses import dataclass

from jibit.types import ServiceName


@dataclass(frozen=True, slots=True)
class AuthSpec:
    """Describe field names and paths for one service token contract."""

    service: ServiceName
    generate_path: str
    refresh_path: str
    api_key_field: str
    secret_key_field: str
    access_response_field: str
    refresh_response_field: str
    refresh_token_field: str
    refresh_access_token_field: str | None = None
    scopes_field: str | None = None
    expires_in_field: str | None = None
    refresh_expires_in_field: str | None = None
    documented_access_ttl_seconds: int | None = None
    documented_refresh_ttl_seconds: int | None = None


AUTH_SPECS: dict[ServiceName, AuthSpec] = {
    ServiceName.PAYMENT_GATEWAY: AuthSpec(
        service=ServiceName.PAYMENT_GATEWAY,
        generate_path="/ppg/v3/tokens",
        refresh_path="/ppg/v3/tokens/refresh",
        api_key_field="apiKey",
        secret_key_field="secretKey",
        access_response_field="accessToken",
        refresh_response_field="refreshToken",
        refresh_token_field="refreshToken",
        documented_access_ttl_seconds=86_400,
        documented_refresh_ttl_seconds=172_800,
    ),
    ServiceName.TRANSFERS: AuthSpec(
        service=ServiceName.TRANSFERS,
        generate_path="/cobank/v1/tokens/generate",
        refresh_path="/cobank/v1/tokens/refresh",
        api_key_field="apiKey",
        secret_key_field="secretKey",
        access_response_field="accessToken",
        refresh_response_field="refreshToken",
        refresh_token_field="refreshToken",
        refresh_access_token_field="accessToken",
        scopes_field="scopes",
    ),
    ServiceName.IDENTICATOR: AuthSpec(
        service=ServiceName.IDENTICATOR,
        generate_path="/ide/v1/tokens/generate",
        refresh_path="/ide/v1/tokens/refresh",
        api_key_field="apiKey",
        secret_key_field="secretKey",
        access_response_field="accessToken",
        refresh_response_field="refreshToken",
        refresh_token_field="refreshToken",
        refresh_access_token_field="accessToken",
        documented_access_ttl_seconds=86_400,
        documented_refresh_ttl_seconds=172_800,
    ),
    ServiceName.DIRECT_DEBIT: AuthSpec(
        service=ServiceName.DIRECT_DEBIT,
        generate_path="/directdebit/api/v1/auth/authenticate",
        refresh_path="/directdebit/api/v1/auth/refresh-token",
        api_key_field="api_key",
        secret_key_field="secret_key",
        access_response_field="access_token",
        refresh_response_field="refresh_token",
        refresh_token_field="refresh_token",
        refresh_access_token_field="access_token",
    ),
    ServiceName.SMS: AuthSpec(
        service=ServiceName.SMS,
        generate_path="/pulse/api/v1/auth/authenticate",
        refresh_path="/pulse/api/v1/auth/refresh-token",
        api_key_field="api_key",
        secret_key_field="secret_key",
        access_response_field="access_token",
        refresh_response_field="refresh_token",
        refresh_token_field="refresh_token",
        refresh_access_token_field="access_token",
    ),
    ServiceName.CONTRACTS: AuthSpec(
        service=ServiceName.CONTRACTS,
        generate_path="/mzahub/v1/auth/login",
        refresh_path="/mzahub/v1/auth/refresh",
        api_key_field="apiKey",
        secret_key_field="secretKey",
        access_response_field="accessToken",
        refresh_response_field="refreshToken",
        refresh_token_field="refreshToken",
        expires_in_field="expiresIn",
        refresh_expires_in_field="refreshTokenExpiresIn",
    ),
}
