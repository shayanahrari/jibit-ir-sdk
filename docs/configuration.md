# Configuration

`JibitConfig` validates SDK-wide behavior and keeps every service's credentials in an
isolated scope. Unknown fields and incomplete credential pairs are rejected before a
network request is attempted.

```python
import os

from jibit import JibitClient

client = JibitClient.from_config(
    {
        "payment_gateway": {
            "api_key": os.environ["JIBIT_PPG_API_KEY"],
            "secret_key": os.environ["JIBIT_PPG_SECRET_KEY"],
        },
        "timeout": {
            "connect": 5,
            "read": 30,
            "write": 30,
            "pool": 5,
        },
        "retry": {
            "max_attempts": 3,
            "base_delay": 0.25,
            "max_delay": 4,
            "jitter_ratio": 0.1,
        },
        "auth": {
            "expiry_leeway_seconds": 60,
            "unknown_access_token_ttl_seconds": None,
            "cache_key_prefix": "jibit:tokens",
        },
    }
)
```

Credentials may also be nested under a `services` mapping. Advanced consumers can inject
an HTTP transport, logger, and audit sink into `JibitClient`.

## Safe defaults

- TLS verification is enabled.
- Request bodies and response bodies are not logged.
- Only operations explicitly classified as safe can be retried.
- A private HTTP connection pool is closed by the client context manager.
- An injected transport remains owned by the application and is never closed by the SDK.
- Tokens are stored in a thread-safe in-memory store unless another store is injected.

Do not disable TLS verification in production. Credentials should come from environment
variables or a secrets manager and must never be stored in application source code.
