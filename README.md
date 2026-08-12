# Jibit IR SDK

**Unofficial Python SDK for Jibit APIs.**

Jibit IR SDK provides a typed, secure, framework-independent client for Jibit payment,
transfer, inquiry, identity, KYC, direct-debit, SMS, and contract-signing APIs. Django
integration is available as an optional extra.

> It is not affiliated with, endorsed by, or sponsored by Jibit.

Official service-provider website: [jibit.ir](https://jibit.ir/)

## معرفی فارسی

Jibit IR SDK یک کتابخانهٔ مستقل و غیررسمی پایتون برای ارتباط ساخت‌یافته و امن با
وب‌سرویس‌های جیبیت است. این پکیج تلاش می‌کند استفاده از سرویس‌های پرداخت، انتقال وجه،
استعلام، احراز هویت، برداشت مستقیم، پیامک و امضای قرارداد را در پروژه‌های Python و
Django ساده‌تر کند.

> این پروژه محصول رسمی جیبیت نیست و توسط جیبیت پشتیبانی یا تأیید نشده است. برای آشنایی
> با شرکت، دریافت دسترسی و مشاهدهٔ اطلاعات رسمی سرویس‌ها به
> [وب‌سایت رسمی جیبیت](https://jibit.ir/) مراجعه کنید.

امکانات اصلی پکیج:

- دریافت، نگهداری و تمدید خودکار توکن به‌صورت مستقل برای هر سرویس؛
- مدل‌های ورودی و خروجی typed با اعتبارسنجی پیش از ارسال درخواست؛
- مدیریت خطاهای شبکه، احراز هویت، اعتبارسنجی و خطاهای تجاری؛
- retry محافظه‌کارانه و جلوگیری از ارسال مجدد ناامن عملیات مالی؛
- لاگ ساخت‌یافته همراه با حذف یا پوشاندن اطلاعات حساس؛
- پشتیبانی اختیاری از Django Cache و Redis برای نگهداری توکن؛
- دسترسی به سرویس‌های مختلف از طریق یک `JibitClient` ساده و یکپارچه.

برای نصب نسخهٔ توسعه از checkout محلی:

```bash
python -m pip install -e .
```

برای استفاده در Django:

```bash
python -m pip install -e ".[django]"
```

پس از قرار دادن تنظیمات در `settings.py` می‌توان client مشترک پروژه را به شکل زیر دریافت
کرد:

```python
from jibit.django import get_jibit_client

client = get_jibit_client()
```

کلیدها و رمزهای سرویس را در سورس پروژه قرار ندهید. آن‌ها را از environment variables یا
یک secret manager بخوانید. همچنین timeout یک عملیات مالی به معنی ناموفق بودن قطعی آن نیست؛
پیش از ارسال مجدد، وضعیت درخواست را با سرویس inquiry یا reconciliation مربوط بررسی کنید.

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
| Transferor v2 | `client.transfers` | Implemented |
| Cobank settlements | `client.cobank` | Implemented; environment verification required |
| Identicator and inquiries | `client.identicator` | Implemented |
| Biometric and KYC | `client.kyc` | Implemented; environment verification required |
| Direct Debit | `client.direct_debit` | Implemented; environment verification required |
| Pulse SMS | `client.sms` | Implemented; environment verification required |
| MzaHub contracts | `client.contracts` | Implemented; environment verification required |

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

Python 3.10 through 3.13 are supported. Django 5.2 through 6.0 is supported through the
optional `django` extra. The core package does not install Django or Redis.

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

For Django, define `JIBIT = {...}` in settings and use:

```python
from jibit.django import get_jibit_client

client = get_jibit_client()
```

See the [Django integration guide](docs/django.md) for cache and logging configuration.

Payment and refund submissions are never blindly retried. If a create or refund request
times out, keep the SDK correlation ID and reconcile using the purchase or refund inquiry
operation before deciding whether another business action is safe. See the
[Payment Gateway guide](docs/payment-gateway.md).

Transferor batch submissions and Cobank settlements are also never blindly retried. Use a
unique `batch_id` or `record_track_id`, persist it before submission, and reconcile through
the corresponding inquiry operation after any timeout or network failure. See the
[transfers and settlements guide](docs/transfers-and-settlements.md).

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
- [Identicator and KYC](docs/identity-and-kyc.md)
- [Transfers and settlements](docs/transfers-and-settlements.md)
- [Direct Debit](docs/direct-debit.md)
- [Pulse SMS and MzaHub contracts](docs/sms-and-contracts.md)
- [Webhooks and callbacks](docs/webhooks.md)
- [Django integration](docs/django.md)
- [Token storage](docs/token-storage.md)
- [Error handling](docs/error-handling.md)
- [Logging and audit events](docs/logging.md)
- [Retry and idempotency](docs/retry-and-idempotency.md)
- [API support matrix](docs/api-support.md)
- [Versioning and compatibility](docs/versioning.md)
- [Production checklist](docs/production-checklist.md)
- [Source provenance](docs/source-provenance.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
