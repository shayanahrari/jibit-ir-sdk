# Retry and idempotency

Every operation is assigned one safety category:

| Category | Automatic retry |
| --- | --- |
| Read-only | Allowed for bounded transient failures. |
| Idempotent | Allowed for bounded transient failures. |
| Idempotency-protected | Allowed only when an idempotency key is present. |
| Unsafe | Never automatically retried. |

Transient failures are limited to transport failures and HTTP `408`, `425`, `429`, `500`,
`502`, `503`, and `504`. Retries use bounded exponential backoff with jitter.

## Uncertain financial outcomes

A timeout does not prove a financial submission failed. The provider may have accepted the
operation before the connection was interrupted. For unsafe payment, refund, transfer,
settlement, or Direct Debit operations, the SDK raises an exception containing a
correlation ID and expects the caller to use the relevant inquiry or reconciliation
operation. It never blindly resubmits the request.

Applications should persist their own business reference before submission and enforce
business-level idempotency independently of the SDK.

For Payment Gateway purchase creation, use a unique `client_reference_number` and call
`inquire_purchase(client_reference_number=...)` after a timeout. For refunds, retain the
returned `refund_id`, `batch_id`, and `transfer_id`; if the submission outcome itself is
unknown, reconcile the purchase and your own ledger before resubmitting anything.
