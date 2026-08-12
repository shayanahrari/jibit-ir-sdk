"""Minimal Identicator ownership-matching example."""

import os

from jibit import JibitClient


def match_iban_owner(iban: str, national_code: str) -> bool:
    """Return whether an IBAN and national code match without logging either value."""
    with JibitClient.from_config(
        {
            "identicator": {
                "api_key": os.environ["JIBIT_IDENTICATOR_API_KEY"],
                "secret_key": os.environ["JIBIT_IDENTICATOR_SECRET_KEY"],
            }
        }
    ) as client:
        return client.identicator.match(iban=iban, national_code=national_code).data.matched
