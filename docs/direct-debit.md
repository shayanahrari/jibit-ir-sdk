# Direct Debit

Configure Direct Debit credentials once. The SDK obtains, refreshes, caches, and attaches
the service token automatically.

```python
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
```

## Mandate lifecycle

Persist a unique creditor mandate reference before initiation:

```python
mandate = client.direct_debit.create_mandate(
    "one-tap",
    creditor_mandate_reference="subscription-000042",
    debtor_bank="<provider-bank-id>",
    maximum_amount=1_000_000,
    period=1,
    period_unit="MONTH",
    start_date="1405-01-01",
    expire_date="1406-01-01",
    frequency=1,
    otp_requirement_status="<provider-value>",
)
```

The SDK supports `time-frame`, `subscription`, and `one-tap` mandate workflows. It validates
shared fields and required workflow-specific fields, but deployment-specific bank IDs and
OTP policy values must be confirmed with Jibit.

Mandate initiation is not retried automatically. Reconcile after a timeout through
`inquire_creditor_mandate(...)`. Use `inquire_mandate(...)` after receiving the provider
reference. Enable, disable, and revoke operations are explicit unsafe actions.

## Collection

Persist a unique creditor transaction number before collection:

```python
result = client.direct_debit.collect(
    creditor_transaction_no="invoice-000042-attempt-1",
    mandate_reference="<mandate-reference>",
    amount=100_000,
)
```

Collection is never automatically replayed. After an uncertain outcome, call
`inquire_transaction(creditor_transaction_no)` and reconcile with the application ledger.
Never log OTPs, mandate data, debtor identity, or account details.

## Status-only operations

The available catalog documents HTTP success but no reliable response schema for:

- mandate revoke;
- mandate enable;
- mandate disable;
- one-tap OTP dispatch;
- Blue Bank callback forwarding.

These return `APIResponse[StatusResult]`. Success means only that the HTTP response was in
the success range; any body is optional uninterpreted bytes.

## Callback boundary

Parse Blue Bank callback bodies with `parse_callback(..., BlueBankCallback, ...)` and an
application-supplied verifier. The SDK does not have a documented Jibit signature or source
verification contract and therefore never marks a callback trusted without a verifier.
Only after verification and deduplication should an application call
`accept_blue_bank_callback(...)`, if its integration flow actually requires forwarding.

All Direct Debit operations are mock-tested from the consolidated catalog and remain
environment-unverified. Confirm auth, bank values, OTP policy, callbacks, limits, and state
transitions before production use.
