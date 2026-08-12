"""Root SDK client and dependency lifecycle."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from types import TracebackType
from typing import Any

from typing_extensions import Self

from jibit.auth import (
    AuthenticatedRequestEngine,
    InMemoryTokenStore,
    LockProvider,
    ServiceAuthenticator,
    StaticBearerRequestEngine,
    ThreadLockProvider,
    TokenStore,
)
from jibit.config import JibitConfig
from jibit.engine import RequestEngine
from jibit.logging import AuditSink, NullAuditSink, StructuredLogger, get_structured_logger
from jibit.retry import RetryPolicy
from jibit.services.base import AuditedRequestExecutor
from jibit.services.cobank import CobankService
from jibit.services.identicator import IdenticatorService
from jibit.services.kyc import KycService
from jibit.services.payment_gateway import PaymentGatewayService
from jibit.services.transfer import TransferService
from jibit.transport import HTTPTransport, HttpxTransport
from jibit.types import ServiceName


class JibitClient:
    """Coordinate shared SDK infrastructure and domain service clients."""

    def __init__(
        self,
        config: JibitConfig,
        *,
        transport: HTTPTransport | None = None,
        logger: logging.Logger | StructuredLogger | None = None,
        audit_sink: AuditSink | None = None,
        token_store: TokenStore | None = None,
        lock_provider: LockProvider | None = None,
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
        self._logger = structured_logger
        self._token_store = token_store or InMemoryTokenStore()
        self._lock_provider = lock_provider or ThreadLockProvider()
        self._authenticated_engines: dict[ServiceName, AuthenticatedRequestEngine] = {}
        self._payment_gateway: PaymentGatewayService | None = None
        self._transfers: TransferService | None = None
        self._cobank: CobankService | None = None
        self._identicator: IdenticatorService | None = None
        self._kyc: KycService | None = None
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

    def authenticated_engine(self, service: ServiceName) -> AuthenticatedRequestEngine:
        """Return a lazily configured authenticated engine for a service."""
        authenticated = self._authenticated_engines.get(service)
        if authenticated is None:
            authenticator = ServiceAuthenticator(
                service=service,
                config=self.config,
                request_engine=self._engine,
                token_store=self._token_store,
                lock_provider=self._lock_provider,
                logger=self._logger,
            )
            authenticated = AuthenticatedRequestEngine(self._engine, authenticator)
            self._authenticated_engines[service] = authenticated
        return authenticated

    @property
    def payment_gateway(self) -> PaymentGatewayService:
        """Return the lazily initialized Payment Gateway service facade."""
        if self._payment_gateway is None:
            self._payment_gateway = PaymentGatewayService(
                self.authenticated_engine(ServiceName.PAYMENT_GATEWAY),
                self.audit_sink,
                self._logger,
            )
        return self._payment_gateway

    @property
    def transfers(self) -> TransferService:
        """Return the lazily initialized Transferor v2 facade."""
        if self._transfers is None:
            self._transfers = TransferService(
                AuditedRequestExecutor(
                    self.authenticated_engine(ServiceName.TRANSFERS),
                    audit_sink=self.audit_sink,
                    logger=self._logger,
                    event_name="jibit.transfer.operation",
                )
            )
        return self._transfers

    @property
    def cobank(self) -> CobankService:
        """Return the lazily initialized Cobank settlement facade."""
        if self._cobank is None:
            self._cobank = CobankService(
                AuditedRequestExecutor(
                    self.authenticated_engine(ServiceName.COBANK),
                    audit_sink=self.audit_sink,
                    logger=self._logger,
                    event_name="jibit.cobank.operation",
                )
            )
        return self._cobank

    @property
    def identicator(self) -> IdenticatorService:
        """Return the lazily initialized Identicator inquiry facade."""
        if self._identicator is None:
            self._identicator = IdenticatorService(
                AuditedRequestExecutor(
                    self.authenticated_engine(ServiceName.IDENTICATOR),
                    audit_sink=self.audit_sink,
                    logger=self._logger,
                    event_name="jibit.identicator.operation",
                )
            )
        return self._identicator

    @property
    def kyc(self) -> KycService:
        """Return KYC operations using a configured static bearer token."""
        if self._kyc is None:
            self._kyc = KycService(
                AuditedRequestExecutor(
                    StaticBearerRequestEngine(self._engine, self.config, ServiceName.KYC),
                    audit_sink=self.audit_sink,
                    logger=self._logger,
                    event_name="jibit.kyc.operation",
                )
            )
        return self._kyc

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
