# Django integration

Install the optional integration:

```bash
python -m pip install "jibit-ir-sdk[django]"
```

Add normal SDK configuration to Django settings. Secret values should come from environment
variables or the deployment secret manager.

```python
# settings.py
import os

JIBIT = {
    "payment_gateway": {
        "api_key": os.environ["JIBIT_PPG_API_KEY"],
        "secret_key": os.environ["JIBIT_PPG_SECRET_KEY"],
    },
    "integration": {
        "use_django_cache": True,
        "cache_alias": "jibit",
        "cache_key_prefix": "jibit-token",
    },
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "jibit": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["JIBIT_CACHE_URL"],
    },
}
```

The `integration` mapping belongs to the Django adapter and is removed before core
configuration validation. Unknown integration settings are rejected.

Use the lazy process-local client:

```python
from jibit.django import get_jibit_client


def begin_payment(order):
    client = get_jibit_client()
    return client.payment_gateway.create_purchase(
        amount=order.amount,
        callback_url=order.callback_url,
        client_reference_number=str(order.public_id),
    )
```

`get_jibit_client()` is thread-safe and returns one client per application process, allowing
the HTTP connection pool to be reused. `close_jibit_client()` exists for worker shutdown,
test isolation, and controlled reloads. Normal web requests should not close the shared
client. Create the client after a process fork; do not initialize it in a preloaded parent
process. The current SDK transport is synchronous. Call it from synchronous Django code or
move calls to a worker thread when using async views.

## Cache and concurrency

`use_django_cache` is opt-in. Without it, the client uses a thread-safe in-memory token
store. A shared Django cache allows token reuse across workers, but the default lock remains
process-local. For strict multi-process refresh coordination, construct `JibitClient`
directly with a distributed `LockProvider`, such as `RedisLockProvider`, until a distributed
lock is explicitly supported by the Django facade.

Token cache infrastructure is sensitive. Require authentication and TLS, isolate it on a
private network, restrict administrative access, and choose a backend/serializer suitable
for secrets. Do not use Django's local-memory backend to share tokens between processes.

## Logging

The SDK uses the `jibit_sdk` standard logger and does not configure handlers:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "jibit_sdk": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
```

Production handlers should output the record's stable `event` and redacted `jibit` mapping.
Do not add filters that serialize request models, exception locals, HTTP bodies, Django
request bodies, or callback payloads.

## Testing

Override `JIBIT` with synthetic credentials, inject a mocked transport when testing the core
client, and never call live financial APIs. If a test changes settings after the singleton
has been created, call `close_jibit_client()` before obtaining it again.
