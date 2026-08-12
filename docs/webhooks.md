# Webhooks and callbacks

Callback delivery is untrusted input. Network arrival, an IP address, or a syntactically
valid body does not prove the caller is Jibit and does not prove a financial outcome.

The framework-independent `parse_callback` helper provides:

- typed payload validation;
- fail-closed application-supplied authenticity verification;
- application-owned atomic deduplication;
- secret-safe result representations;
- optional structured received/rejected logging.

```python
from jibit.webhooks import PaymentCallback, parse_callback

parsed = parse_callback(
    request_data,
    PaymentCallback,
    service="payment_gateway",
    raw_body=request_body,
    headers=request_headers,
    verifier=verify_using_authorized_jibit_mechanism,
    deduplication_store=callback_store,
    deduplication_key=lambda payload: str(payload.purchase_id),
)

if not parsed.duplicate:
    verification = client.payment_gateway.verify_purchase(parsed.payload.purchase_id)
```

The verifier receives exact raw bytes and headers and must return true only when the
officially supplied mechanism passes. Because that mechanism is not present in the
available material, the SDK ships no permissive default verifier. Omitting a verifier,
returning false, or raising from it rejects the callback.

Deduplication is an extension point, not in-memory persistence supplied by the SDK. In
multi-worker systems, implement atomic claim semantics using the application's database,
cache, or idempotency infrastructure. A duplicate is not necessarily malicious; acknowledge
it quickly without reapplying the business transition.

## Fast acknowledgement pattern

Callback routes should validate size/content type, parse and authenticate, atomically claim
the event key, enqueue or transactionally perform the smallest necessary work, and return a
success acknowledgement quickly. Provider inquiry/verification and internal reconciliation
remain the source of truth for payments and collections.

Apply request-size limits, rate limiting, CSRF exemptions only where framework-appropriate,
strict tenant/ownership checks, retention controls, and secret-safe logging. Never include a
full callback body in logs or error monitoring.
