"""Static bearer authentication for services without a documented token flow."""

from __future__ import annotations

from dataclasses import replace

from jibit.config import JibitConfig
from jibit.engine import RequestEngine, RequestOptions
from jibit.exceptions import JibitConfigurationError
from jibit.response import RawResponse
from jibit.types import ServiceName


class StaticBearerRequestEngine:
    """Attach a configured bearer token without attempting undocumented refresh behavior."""

    def __init__(self, engine: RequestEngine, config: JibitConfig, service: ServiceName) -> None:
        credentials = config.service(service).credentials
        if credentials.access_token is None:
            raise JibitConfigurationError(
                f"Service '{service.value}' requires a configured access_token"
            )
        self._engine = engine
        self._access_token = credentials.access_token

    def execute(self, options: RequestOptions) -> RawResponse:
        """Attach the static token while preserving secret-safe request representations."""
        headers = dict(options.headers)
        headers["Authorization"] = f"Bearer {self._access_token.get_secret_value()}"
        return self._engine.execute(replace(options, headers=headers))
