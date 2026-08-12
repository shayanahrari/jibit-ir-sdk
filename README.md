# Jibit IR SDK

**Unofficial Python SDK for Jibit APIs.**

Jibit IR SDK provides a typed, secure, framework-independent client for Jibit payment,
transfer, inquiry, identity, KYC, direct-debit, SMS, and contract-signing APIs. Django
integration is available as an optional extra.

> This project is under active development and is not yet suitable for production use.
> It is not affiliated with, endorsed by, or sponsored by Jibit.

## Design goals

- A concise high-level API with access to raw responses when needed.
- Automatic, service-scoped token acquisition and refresh.
- Conservative retry behavior for financial operations.
- Typed request and response models with early input validation.
- Structured English-language logging with strict redaction.
- Framework-independent core with optional Django and Redis integrations.
- Explicit documentation of verified, incomplete, and unsupported API behavior.

## Supported service families

| Service family | Package area | Status |
| --- | --- | --- |
| Payment Gateway (PPG) | `client.payment_gateway` | Implemented |
| Transfers and settlements | `client.transfers` | Planned |
| Identicator and inquiries | `client.identicator` | Planned |
| Biometric and KYC | `client.kyc` | Planned |
| Direct Debit | `client.direct_debit` | Planned |
| Pulse SMS | `client.sms` | Planned |
| MzaHub contracts | `client.contracts` | Planned |

See the [API support matrix](docs/api-support.md) for operation-level verification status.

## Installation

The package is not yet published. During development, install it from a local checkout:

```bash
python -m pip install -e .
```

Optional integrations:

```bash
python -m pip install -e ".[django]"
python -m pip install -e ".[redis]"
```

## Intended usage

```python
from jibit import JibitClient

client = JibitClient.from_config(
    {
        "payment_gateway": {
            "api_key": "<read-from-a-secret-store>",
            "secret_key": "<read-from-a-secret-store>",
        }
    }
)

purchase = client.payment_gateway.create_purchase(
    amount=100_000,
    callback_url="https://example.com/payments/callback/",
    client_reference_number="order-123",
)

print(purchase.data.purchase_id)
print(purchase.data.psp_switching_url)
```

Credentials must come from environment variables or a secrets manager. The SDK never
logs credentials, authorization headers, tokens, OTPs, or unredacted financial and
identity payloads.

Service tokens are acquired and refreshed automatically. Shared multi-process deployments
can inject Django Cache or Redis token storage and a distributed refresh lock.

Payment and refund submissions are never blindly retried. If a create or refund request
times out, keep the SDK correlation ID and reconcile using the purchase or refund inquiry
operation before deciding whether another business action is safe. See the
[Payment Gateway guide](docs/payment-gateway.md).

## Direct Debit response limitation

Five documented Direct Debit operations declare successful HTTP responses without a
reliable response-body schema: mandate revoke, enable, disable, OTP dispatch, and the
Blue Bank callback. The SDK treats them as status-only operations and keeps any response
body optional. Consumers must not depend on undocumented body fields.

## Documentation

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Authentication](docs/authentication.md)
- [Payment Gateway](docs/payment-gateway.md)
- [Token storage](docs/token-storage.md)
- [Error handling](docs/error-handling.md)
- [Logging and audit events](docs/logging.md)
- [Retry and idempotency](docs/retry-and-idempotency.md)
- [API support matrix](docs/api-support.md)
- [Source provenance](docs/source-provenance.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
