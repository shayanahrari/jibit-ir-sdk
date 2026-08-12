"""Reconcile a Transferor batch using environment-held credentials."""

from __future__ import annotations

import os

from jibit import JibitClient


def build_client() -> JibitClient:
    """Create a Transferor client without embedding credentials in source."""
    return JibitClient.from_config(
        {
            "transfers": {
                "api_key": os.environ["JIBIT_TRANSFEROR_API_KEY"],
                "secret_key": os.environ["JIBIT_TRANSFEROR_SECRET_KEY"],
            }
        }
    )


def reconcile(client: JibitClient, batch_id: str) -> None:
    """Print only non-sensitive states after reconciling a persisted batch reference."""
    result = client.transfers.inquire(batch_id=batch_id)
    states = [transfer.state for transfer in result.data.transfers]
    print(states)
