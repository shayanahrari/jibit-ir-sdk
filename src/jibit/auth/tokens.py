"""Secret-safe token state and expiry discovery."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr


@dataclass(frozen=True, slots=True, repr=False)
class TokenState:
    """Store an access/refresh pair without exposing token values in representations."""

    access_token: SecretStr
    refresh_token: SecretStr | None = None
    expires_at: float | None = None
    refresh_expires_at: float | None = None
    token_type: str = "Bearer"  # noqa: S105
    scopes: tuple[str, ...] = ()

    def __repr__(self) -> str:
        refresh_repr = "SecretStr('**********')" if self.refresh_token else "None"
        return (
            "TokenState(access_token=SecretStr('**********'), "
            f"refresh_token={refresh_repr}, "
            f"expires_at={self.expires_at!r}, refresh_expires_at={self.refresh_expires_at!r}, "
            f"token_type={self.token_type!r}, scopes={self.scopes!r})"
        )

    def access_value(self) -> str:
        """Return the access token only for authorization-header construction."""
        return self.access_token.get_secret_value()

    def refresh_value(self) -> str | None:
        """Return the refresh token only for the provider refresh request."""
        return self.refresh_token.get_secret_value() if self.refresh_token else None

    def is_access_valid(self, now: float, leeway: float) -> bool:
        """Return whether the token is usable outside the configured expiry margin."""
        return self.expires_at is None or now + leeway < self.expires_at

    def is_refresh_valid(self, now: float, leeway: float) -> bool:
        """Return whether a refresh token exists and is outside its expiry margin."""
        return self.refresh_token is not None and (
            self.refresh_expires_at is None or now + leeway < self.refresh_expires_at
        )

    def to_cache_data(self) -> dict[str, Any]:
        """Serialize token state for an application-authorized cache backend."""
        return {
            "access_token": self.access_value(),
            "refresh_token": self.refresh_value(),
            "expires_at": self.expires_at,
            "refresh_expires_at": self.refresh_expires_at,
            "token_type": self.token_type,
            "scopes": list(self.scopes),
        }

    @classmethod
    def from_cache_data(cls, value: dict[str, Any]) -> TokenState:
        """Validate the minimal shape required to reconstruct cached token state."""
        access_token = value.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Cached token state has no access token")
        refresh_token = value.get("refresh_token")
        return cls(
            access_token=SecretStr(access_token),
            refresh_token=SecretStr(refresh_token) if isinstance(refresh_token, str) else None,
            expires_at=_optional_float(value.get("expires_at")),
            refresh_expires_at=_optional_float(value.get("refresh_expires_at")),
            token_type=str(value.get("token_type") or "Bearer"),
            scopes=tuple(str(scope) for scope in value.get("scopes") or ()),
        )


def jwt_expiry(token: str) -> float | None:
    """Read an unverified JWT expiry as a scheduling hint, never as authentication proof."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        expiry = decoded.get("exp") if isinstance(decoded, dict) else None
        return float(expiry) if expiry is not None else None
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _optional_float(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None
