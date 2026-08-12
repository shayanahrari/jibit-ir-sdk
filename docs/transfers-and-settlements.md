# Transfers and settlements

The SDK exposes two related but independent services:

- `client.transfers` implements the Transferor v2 wallet-to-IBAN batch API.
- `client.cobank` implements Cobank settlement operations from the consolidated catalog.

They use different route prefixes, token endpoints, credentials, token caches, and audit
event scopes. Configure only the service your Jibit account has enabled.

## Transferor configuration

```python
import os

from jibit import JibitClient

client = JibitClient.from_config(
    {
        "transfers": {
            "api_key": os.environ["JIBIT_TRANSFEROR_API_KEY"],
            "secret_key": os.environ["JIBIT_TRANSFEROR_SECRET_KEY"],
        }
    }
)
```

The SDK obtains `/trf/v2` tokens automatically and refreshes them before expiry.

## Submit and reconcile a Transferor batch

Persist the batch and transfer references in your application before calling the provider.

```python
result = client.transfers.submit_batch(
    batch_id="payout-2026-00042",
    submission_mode="BATCH",
    transfers=[
        {
            "transfer_id": "payout-line-1",
            "transfer_mode": "ACH",
            "destination": "<destination-iban>",
            "amount": 1_000_000,
            "currency": "IRR",
            "description": "Invoice settlement",
        }
    ],
)
```

Submission is `UNSAFE` and is never retried by the SDK. A timeout does not establish that
the provider rejected the batch. Reconcile it instead:

```python
batch = client.transfers.inquire(batch_id="payout-2026-00042")
transfer = client.transfers.inquire(transfer_id="payout-line-1")
```

`cancel(...)` and `retry_failed(...)` are explicit financial actions and are also never
automatically replayed. Their available source contract does not define response bodies, so
the SDK returns `APIResponse[StatusResult]` and preserves any body only as uninterpreted raw
bytes. `retry_failed` means requesting a provider retry of an already failed transfer; it is
not the SDK retry policy.

Transferor also supports typed balance, filter, daily-usage, supported-bank,
currently-active-bank, receipt-control, and batch-generator operations. Public receipt URLs
can expose financial facts to anyone holding the link. Protect them and disable them as soon
as they are no longer required.

## Cobank configuration

```python
client = JibitClient.from_config(
    {
        "cobank": {
            "api_key": os.environ["JIBIT_COBANK_API_KEY"],
            "secret_key": os.environ["JIBIT_COBANK_SECRET_KEY"],
            "scopes": ["SETTLEMENT"],
        }
    }
)
```

Confirm the scopes assigned by Jibit. The SDK forwards configured scopes during token
acquisition but does not invent or escalate them.

## Submit and reconcile a Cobank settlement

Generate and persist a UUID in your own transaction before submission:

```python
from uuid import uuid4

record_track_id = uuid4()

created = client.cobank.create_settlement(
    record_track_id=record_track_id,
    destination_iban="<destination-iban>",
    amount=1_000_000,
    transfer_type="ACH",
    transfer_reason="KHARID_KHADAMAT",
    request_description="Service invoice",
)
```

Creation is never automatically retried. After a timeout or network error:

```python
reconciled = client.cobank.inquire_settlement(record_track_id)
```

Batch inquiry is an idempotent POST and supports up to 10,000 track IDs. Settlement listing,
merchant-account discovery, and receipt-link state are also typed. Merchant account objects
are intentionally exposed as a secret-safe flexible container because that large
configuration schema is provider-evolving; do not depend on undocumented fields.

## Operational requirements

- Treat `unknown` audit outcomes as requiring reconciliation, not as failures.
- Enforce application-level uniqueness for batch, transfer, and track references.
- Do not place customer data in `metadata`, descriptions, or tracking identifiers.
- Restrict receipt links and avoid storing them in logs.
- Verify Cobank routes, scopes, transfer reasons, limits, and enabled rails in an authorized
  environment before production use.
- Keep an internal ledger and compare provider state with bank and business state.

The SDK does not call live financial APIs in its tests. Transferor is mock-tested against the
available version 2.5 contract. Cobank is mock-tested from the consolidated catalog and
remains environment-unverified.
