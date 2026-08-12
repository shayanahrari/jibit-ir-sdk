# Payment Gateway

The Payment Gateway facade provides typed PPG v3 operations through
`client.payment_gateway`. Authentication is automatic and isolated from every other Jibit
service. Application code must never fetch, cache, refresh, or attach the service token.

## Configuration

Read credentials from environment variables or a secret manager and pass their values to
the SDK at application startup:

```python
import os

from jibit import JibitClient

client = JibitClient.from_config(
    {
        "payment_gateway": {
            "api_key": os.environ["JIBIT_PPG_API_KEY"],
            "secret_key": os.environ["JIBIT_PPG_SECRET_KEY"],
        }
    }
)
```

Never put real credentials in source code, settings committed to version control, tests,
documentation, or exception messages.

## Create and redirect

Persist the order and its unique business reference before calling the provider. A stored
reference is needed to reconcile a timeout safely.

```python
purchase = client.payment_gateway.create_purchase(
    amount=100_000,
    wage=0,
    callback_url="https://merchant.example/payments/jibit/callback/",
    client_reference_number="order-2026-000042",
)

purchase_id = purchase.data.purchase_id
redirect_url = str(purchase.data.psp_switching_url)
correlation_id = purchase.raw.correlation_id
```

Redirect the payer to `redirect_url`. Do not log the full request, callback, card fields,
or payer identity data. The models use safe representations and the SDK does not log bodies,
but the application must apply the same rule to its own logs.

## Callback and verification

A callback reaching your route is not proof of payment. Treat every callback field as
untrusted input, compare the purchase and business reference with your stored order, and
call the verification endpoint before marking the order paid:

```python
from jibit import JibitError


def handle_callback(untrusted_form: dict[str, str]) -> None:
    purchase_id = int(untrusted_form["purchaseId"])

    try:
        verification = client.payment_gateway.verify_purchase(purchase_id)
    except JibitError as exc:
        schedule_reconciliation(
            purchase_id=purchase_id,
            correlation_id=exc.context.correlation_id,
        )
        return

    if verification.data.status.value in {"SUCCESSFUL", "ALREADY_VERIFIED"}:
        mark_paid_idempotently(purchase_id)
    elif verification.data.status.value == "UNKNOWN":
        schedule_reconciliation(
            purchase_id=purchase_id,
            correlation_id=verification.raw.correlation_id,
        )
```

The example uses application functions intentionally: database transactions, ownership
checks, deduplication, and job scheduling belong to the consuming project. Provider-specific
callback authenticity verification is not yet documented in the available contract, so the
SDK does not claim that parsed callback values are trusted.

## Reconcile uncertain outcomes

Purchase creation is an unsafe financial submission and is not automatically retried after
a timeout or connection failure. Query by the reference stored before submission:

```python
result = client.payment_gateway.inquire_purchase(client_reference_number="order-2026-000042")

matches = result.data.elements
if matches:
    provider_purchase = matches[0]
```

The inquiry returns the documented page model because the upstream operation is a filter.
Handle an empty page explicitly. Keep the SDK correlation ID with application diagnostics,
but do not use it as a business identifier.

## Reversal and refund

Verification and reversal have documented repeatable outcomes such as `ALREADY_VERIFIED`
and `ALREADY_REVERSED`, so bounded transient retry is enabled for them. Refund submission is
not automatically retried:

```python
refund = client.payment_gateway.refund_purchase(
    purchase_id=purchase_id,
    amount=25_000,
    cancellable=True,
)

refund_state = client.payment_gateway.inquire_refund(refund.data.refund_id)
```

Refund verify, retry, cancel, and ignore-cancellable operations do not have a documented
response-body model. They return `APIResponse[StatusResult]`; use `data.success` and
`data.status_code`. `data.raw_body` is optional, uninterpreted, and must not become an
application contract.

## Filtering and operational inquiries

Use typed criteria for validation and documented pagination limits:

```python
from jibit.services.payment_gateway import PurchaseFilter, PurchaseState, SettlementFilter

purchases = client.payment_gateway.filter_purchases(
    PurchaseFilter(status=PurchaseState.SUCCESS, page=1, size=25)
)
settlements = client.payment_gateway.filter_settlements(SettlementFilter(page=1, size=25))
terminals = client.payment_gateway.list_terminals()
balances = client.payment_gateway.get_balances()
health = client.payment_gateway.health()
```

Every high-level result exposes typed data as `.data` and transport-neutral diagnostics as
`.raw`. Response bodies are not written to logs. Model and response representations hide
payload data by default.

## Production checklist

- Use an authorized Jibit environment and allowlisted source/callback addresses.
- Store credentials in a secret manager and rotate them according to your policy.
- Persist a unique business reference before purchase creation.
- Make callback handling idempotent and verify before crediting an order.
- Reconcile timeouts rather than blindly submitting another purchase or refund.
- Configure application logging and an audit sink without payload bodies.
- Restrict access to payment records, callback data, and operational logs.
- Verify operation behavior in your authorized environment before production rollout.
