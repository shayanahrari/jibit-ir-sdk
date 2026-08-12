# Logging and audit events

The SDK uses Python's standard `logging` package and the `jibit_sdk` logger by default. It
does not add handlers, create files, or modify global logging configuration. Applications
can route records to Django logging, structlog processors, JSON handlers, Sentry,
OpenTelemetry, ELK, Datadog, or another destination.

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "jibit_sdk": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        }
    },
}
```

Each record contains a stable `event` attribute and a redacted `jibit` mapping. Common
events include:

- `jibit.request.started`
- `jibit.request.completed`
- `jibit.request.failed`
- `jibit.request.retry_scheduled`
- `jibit.token.refreshed`
- `jibit.token.refresh_failed`
- `jibit.webhook.received`
- `jibit.webhook.rejected`

Tokens, secrets, authorization headers, OTPs, national identifiers, card data, IBANs,
mobile numbers, KYC media, images, and videos are redacted. Request and response payloads
are excluded by default.

## Audit events

Operational logs and business audit events are separate. Applications may inject an
`AuditSink` to persist already-redacted `AuditEvent` objects. The SDK does not require a
database or choose retention, access-control, or regulatory policies for the application.
