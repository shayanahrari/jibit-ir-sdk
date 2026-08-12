# Error handling

All runtime exceptions and messages use English. `JibitError` is the base class for
predictable SDK failures. Consumers can either handle a broad SDK failure or use a narrow
category:

```python
from jibit import (
    JibitAuthenticationError,
    JibitBusinessError,
    JibitError,
    JibitTimeoutError,
)

try:
    result = perform_operation()
except JibitAuthenticationError:
    alert_credentials_owner()
except JibitBusinessError as exc:
    handle_business_rejection(exc.context.error_code)
except JibitTimeoutError as exc:
    reconcile_uncertain_result(exc.context.correlation_id)
except JibitError as exc:
    report_integration_failure(exc.context.safe_dict())
```

## Exception categories

| Exception | Meaning |
| --- | --- |
| `JibitConfigurationError` | Local configuration is missing or invalid. |
| `JibitAuthenticationError` | Credentials or tokens were rejected. |
| `JibitAuthorizationError` | The authenticated client lacks permission. |
| `JibitValidationError` | Local or upstream request validation failed. |
| `JibitBusinessError` | A documented business rule rejected the operation. |
| `JibitRateLimitError` | The upstream service rate-limited a request. |
| `JibitTimeoutError` | A configured network timeout expired. |
| `JibitNetworkError` | No valid HTTP response was received. |
| `JibitServerError` | The upstream service returned a server failure. |
| `JibitResponseError` | A response could not be safely interpreted. |
| `JibitWebhookVerificationError` | A callback failed configured verification. |
| `JibitUnsupportedOperationError` | A safe contract is unavailable. |

Exception context can contain service, operation, endpoint, HTTP status, upstream error
code, request ID, fingerprint, reference number, correlation ID, and retryability. Values
are redacted before they enter string or dictionary representations.
