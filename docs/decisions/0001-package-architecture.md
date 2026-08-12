# 0001: Framework-independent core with optional integrations

- Status: Accepted
- Date: 2026-08-12

## Decision

The SDK core remains independent of Django, Redis, databases, and observability vendors.
Integrations implement small protocols and are installed through optional dependency
groups.

## Consequences

- Plain Python applications have a small dependency surface.
- Django projects reuse their existing settings, cache, and logging configuration.
- Token stores, transports, clocks, audit sinks, and retry policies remain testable and
  replaceable.
- Optional integrations require dedicated compatibility tests.
