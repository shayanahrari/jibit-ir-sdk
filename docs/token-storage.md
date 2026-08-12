# Token storage

The default `InMemoryTokenStore` is thread-safe and appropriate for development,
single-process applications, and short-lived workers. Tokens disappear when the process
stops.

Applications can inject any object implementing `TokenStore`:

```python
from jibit import JibitClient
from jibit.auth.redis import RedisLockProvider, RedisTokenStore

token_store = RedisTokenStore(redis_client)
lock_provider = RedisLockProvider(redis_client)

client = JibitClient.from_config(
    config,
    token_store=token_store,
    lock_provider=lock_provider,
)
```

For Django:

```python
from jibit.auth.django import DjangoCacheTokenStore

token_store = DjangoCacheTokenStore(alias="jibit")
```

The higher-level `jibit.django.get_jibit_client()` facade can enable this adapter through
`JIBIT["integration"]["use_django_cache"]`. See the [Django guide](django.md).

## Security requirements

Token caches contain credentials capable of authorizing API requests. Production cache
deployments must use authentication, encryption in transit, private networking, least
privilege, restricted administrative access, backup controls, and retention appropriate to
the application's threat model.

The Django adapter uses the application's selected cache backend and its configured
serialization. The Redis adapter serializes token state as compact JSON. Neither adapter
logs token values.

Use a distributed lock with a shared token store. Combining a shared cache with only local
thread locks can still allow separate processes to refresh the same token concurrently.
