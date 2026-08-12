"""HTTP transport protocol and default httpx implementation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from jibit.config import TimeoutConfig
from jibit.types import ContentPartType, MultipartPart


@dataclass(frozen=True, slots=True)
class TransportRequest:
    """Describe a transport-neutral HTTP request."""

    method: str
    url: str
    headers: Mapping[str, str] = field(repr=False)
    params: Mapping[str, Any] | None = field(default=None, repr=False)
    json: Any = field(default=None, repr=False)
    content: bytes | None = field(default=None, repr=False)
    multipart: tuple[MultipartPart, ...] | None = field(default=None, repr=False)
    timeout: TimeoutConfig | None = None


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """Describe a fully-read transport-neutral HTTP response."""

    status_code: int
    headers: dict[str, str]
    content: bytes


class TransportTimeoutError(Exception):
    """Signal a timeout without leaking transport-specific objects."""


class TransportNetworkError(Exception):
    """Signal a network failure without leaking transport-specific objects."""


class HTTPTransport(Protocol):
    """Define the replaceable synchronous HTTP transport contract."""

    def send(self, request: TransportRequest) -> TransportResponse:
        """Send one request and return a fully-read response."""

    def close(self) -> None:
        """Release transport resources."""


class HttpxTransport:
    """Send SDK requests through a private synchronous httpx client."""

    def __init__(self, *, verify_ssl: bool = True, user_agent: str) -> None:
        self._client = httpx.Client(verify=verify_ssl, headers={"User-Agent": user_agent})

    def send(self, request: TransportRequest) -> TransportResponse:
        """Send and fully read one request, normalizing transport failures."""
        timeout = request.timeout
        httpx_timeout = (
            httpx.Timeout(
                connect=timeout.connect,
                read=timeout.read,
                write=timeout.write,
                pool=timeout.pool,
            )
            if timeout is not None
            else None
        )
        try:
            files: list[tuple[str, tuple[str | None, bytes | str, str | None]]] | None = None
            if request.multipart is not None:
                files = [
                    (
                        part.name,
                        (
                            part.filename if part.kind is ContentPartType.FILE else None,
                            part.value,
                            part.content_type,
                        ),
                    )
                    for part in request.multipart
                ]
            response = self._client.request(
                request.method,
                request.url,
                headers=request.headers,
                params=request.params,
                json=request.json,
                content=request.content,
                files=files,
                timeout=httpx_timeout,
            )
        except httpx.TimeoutException as exc:
            raise TransportTimeoutError from exc
        except httpx.RequestError as exc:
            raise TransportNetworkError from exc
        return TransportResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.content,
        )

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._client.close()
