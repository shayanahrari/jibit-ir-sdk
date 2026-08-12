"""Reconcile a Direct Debit collection using environment-held credentials."""

import os

from jibit import JibitClient

client = JibitClient.from_config(
    {
        "direct_debit": {
            "api_key": os.environ["JIBIT_DIRECT_DEBIT_API_KEY"],
            "secret_key": os.environ["JIBIT_DIRECT_DEBIT_SECRET_KEY"],
        }
    }
)

result = client.direct_debit.inquire_transaction("persisted-creditor-transaction-reference")
print(result.data.status)
