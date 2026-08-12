"""Shared deterministic test doubles for SDK infrastructure."""

from __future__ import annotations

from collections.abc import Iterable

from jibit.transport import TransportRequest, TransportResponse


class FakeTransport:
    """Return a predefined sequence of responses or transport exceptions."""

    def __init__(self, outcomes: Iterable[TransportResponse | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[TransportRequest] = []
        self.close_calls = 0

    def send(self, request: TransportRequest) -> TransportResponse:
        """Record a request and return or raise the next configured outcome."""
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self) -> None:
        """Record lifecycle calls."""
        self.close_calls += 1


def response(
    status_code: int = 200,
    *,
    content: bytes = b"{}",
    headers: dict[str, str] | None = None,
) -> TransportResponse:
    """Create a transport response with predictable defaults."""
    return TransportResponse(status_code, headers or {}, content)
