"""Authorized request execution with bounded 401 recovery."""

from __future__ import annotations

from dataclasses import replace

from jibit.auth.provider import ServiceAuthenticator
from jibit.engine import RequestEngine, RequestOptions
from jibit.exceptions import JibitAuthenticationError
from jibit.response import RawResponse
from jibit.retry import OperationSafety


class AuthenticatedRequestEngine:
    """Attach service tokens and replay one safe request after authentication rejection."""

    def __init__(self, engine: RequestEngine, authenticator: ServiceAuthenticator) -> None:
        self._engine = engine
        self._authenticator = authenticator

    def execute(self, options: RequestOptions) -> RawResponse:
        """Authorize a request and perform at most one safe 401 recovery."""
        token = self._authenticator.get_token()
        authorized = self._authorize(options, token.token_type, token.access_value())
        try:
            return self._engine.execute(authorized)
        except JibitAuthenticationError:
            if not self._can_replay(options):
                self._authenticator.invalidate()
                raise
        replacement = self._authenticator.recover_from_unauthorized(token.access_value())
        replay = self._authorize(options, replacement.token_type, replacement.access_value())
        try:
            return self._engine.execute(replay)
        except JibitAuthenticationError:
            self._authenticator.invalidate()
            raise

    @staticmethod
    def _authorize(options: RequestOptions, token_type: str, access_token: str) -> RequestOptions:
        headers = dict(options.headers)
        headers["Authorization"] = f"{token_type} {access_token}"
        return replace(options, headers=headers)

    @staticmethod
    def _can_replay(options: RequestOptions) -> bool:
        if options.safety in {OperationSafety.READ_ONLY, OperationSafety.IDEMPOTENT}:
            return True
        return (
            options.safety is OperationSafety.IDEMPOTENCY_PROTECTED
            and options.idempotency_key is not None
        )
