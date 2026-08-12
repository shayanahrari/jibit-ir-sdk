"""Root SDK client and dependency lifecycle."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from types import TracebackType
from typing import Any

from typing_extensions import Self

from jibit.config import JibitConfig
from jibit.engine import RequestEngine
from jibit.logging import AuditSink, NullAuditSink, StructuredLogger, get_structured_logger
from jibit.retry import RetryPolicy
from jibit.transport import HTTPTransport, HttpxTransport


class JibitClient:
    """Coordinate shared SDK infrastructure and domain service clients."""

    def __init__(
        self,
        config: JibitConfig,
        *,
        transport: HTTPTransport | None = None,
        logger: logging.Logger | StructuredLogger | None = None,
        audit_sink: AuditSink | None = None,
    ) -> None:
        self.config = config
        self.audit_sink = audit_sink or NullAuditSink()
        self._owns_transport = transport is None
        self._transport = transport or HttpxTransport(
            verify_ssl=config.verify_ssl,
            user_agent=config.user_agent,
        )
        if isinstance(logger, StructuredLogger):
            structured_logger = logger
        elif isinstance(logger, logging.Logger):
            structured_logger = StructuredLogger(logger, enabled=config.logging.enabled)
        else:
            structured_logger = get_structured_logger(
                config.logging.logger_name,
                enabled=config.logging.enabled,
            )
        self._engine = RequestEngine(
            config=config,
            transport=self._transport,
            logger=structured_logger,
            retry_policy=RetryPolicy(config.retry),
        )
        self._closed = False

    @classmethod
    def from_config(
        cls,
        config: JibitConfig | Mapping[str, Any],
        **dependencies: Any,
    ) -> Self:
        """Create a client from validated configuration or a plain mapping."""
        validated = config if isinstance(config, JibitConfig) else JibitConfig.from_mapping(config)
        return cls(validated, **dependencies)

    @property
    def request_engine(self) -> RequestEngine:
        """Expose the shared engine to domain service implementations."""
        return self._engine

    def close(self) -> None:
        """Release an internally owned transport exactly once."""
        if self._closed:
            return
        if self._owns_transport:
            self._transport.close()
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
