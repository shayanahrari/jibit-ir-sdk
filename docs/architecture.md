# Architecture

## Design principles

The SDK uses a framework-independent core and optional integration adapters. Service
clients share transport, authentication, error mapping, logging, redaction, correlation,
and retry infrastructure without sharing domain-specific models.

```text
JibitClient
  -> service facade
      -> typed request/response models
      -> service-aware authentication
      -> safe request engine
          -> retry policy
          -> HTTP transport
          -> structured logging and audit hooks
```

## Boundaries

- `core`: configuration, transport, retries, exceptions, redaction, and logging.
- `auth`: service-specific authentication and token storage.
- `services`: domain-specific API operations and models.
- `webhooks`: parsing, validation hooks, and deduplication extension points.
- `django`: optional settings, caching, and lifecycle integration.

The core does not require Django, Redis, a database, or a logging backend. Applications
provide those capabilities through documented protocols when required.

## Financial-operation safety

The request engine distinguishes read-only, idempotent, idempotency-protected, and unsafe
operations. Unsafe financial submissions are not automatically retried after uncertain
network outcomes. Service clients expose inquiry or reconciliation operations instead.

## Compatibility

Public APIs follow Semantic Versioning. During `0.x`, confirmed upstream behavior may
require model refinements; changes are documented in the changelog and support matrix.
After `1.0.0`, removals require deprecation in a prior minor release unless a security
issue makes continued support unsafe.
