# Authentication

The SDK maintains an isolated token lifecycle for each configured service. Applications
provide long-lived credentials once; service clients obtain, cache, attach, refresh, and
invalidate access tokens automatically.

Supported automatic token contracts:

| Service | Initial authentication | Refresh request |
| --- | --- | --- |
| Payment Gateway | API key and secret key | Refresh token |
| Cobank/transfers | API key, secret key, and optional scopes | Access and refresh tokens |
| Identicator | API key and secret key | Access and refresh tokens |
| Direct Debit | API key and secret key | Access and refresh tokens |
| Pulse SMS | API key and secret key | Access and refresh tokens |
| MzaHub contracts | API key and secret key | Refresh token |

KYC authentication is not inferred because the currently available contract does not
describe a safe automatic token flow for that service.

## Expiry handling

The SDK uses, in order:

1. The `exp` claim of a JWT as an unverified scheduling hint.
2. A documented `expiresIn` response field.
3. A documented service lifetime when available.
4. The optional `unknown_access_token_ttl_seconds` setting for opaque tokens.

An unverified JWT claim is never treated as proof of authenticity. It is used only to
schedule refresh. If an opaque-token contract provides no expiry and no fallback is
configured, the SDK retains it until the provider rejects it, then performs bounded 401
recovery.

## Authentication rejection

After a `401` response, the SDK refreshes or replaces the token and replays the operation
once only when replay is safe. Unsafe financial submissions are not replayed. A second
`401` invalidates cached token state and is returned to the application.

## Concurrency

`ThreadLockProvider` prevents refresh stampedes within one process. Multi-process and
multi-host deployments should use `RedisLockProvider` or provide another distributed
`LockProvider` implementation.
