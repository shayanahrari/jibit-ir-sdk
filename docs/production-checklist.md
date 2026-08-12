# Production checklist

Complete this checklist for each deployed service scope.

## Provider and contract verification

- Confirm the endpoint origin, path version, credentials, scopes, IP allowlist, limits,
  currency units, bank identifiers, and enabled features with Jibit.
- Verify every operation marked environment-unverified in an authorized non-production
  account before enabling it for customers.
- Record the upstream contract version and a service owner in the consuming project.

## Secrets and network

- Load credentials from an approved secret manager and rotate them on a defined schedule.
- Enforce TLS verification and restrict outbound traffic to expected provider origins.
- Protect token caches with TLS, authentication, private networking, least privilege, and
  controlled backups.
- Use separate credentials and cache namespaces for environments and service scopes.

## Financial correctness

- Persist business references before financial submissions.
- Enforce application-level uniqueness and state transitions in database transactions.
- Implement inquiry/reconciliation jobs for timeout, network, server, and malformed-response
  outcomes.
- Never treat a timeout as a rejection or automatically resubmit an unsafe operation.
- Reconcile provider, bank, and internal ledger state and alert on divergence.

## Identity and privacy

- Minimize identity, biometric, message, contract, and callback data.
- Enforce tenant ownership, purpose limitation, role access, retention, and deletion policy.
- Encrypt sensitive stored data and backups and restrict export/debug tooling.
- Confirm logs, traces, error monitoring, analytics, and support tools do not capture payloads.

## Callbacks

- Apply the officially supplied authenticity mechanism through a fail-closed verifier.
- Enforce body-size and content-type limits, rate limits, atomic deduplication, and fast
  acknowledgement.
- Verify/inquire upstream state before applying payment or collection business transitions.
- Monitor rejected, duplicate, delayed, and reconciliation-pending callbacks.

## Operations

- Set explicit connect, read, write, and pool timeouts.
- Route `jibit_sdk` structured events and application-owned audit events to protected sinks.
- Alert on auth refresh failure, rate limiting, repeated server/network errors, unknown
  outcomes, reconciliation backlog, and audit-sink failure.
- Test credential rotation, cache outage, provider outage, callback replay, and rollback.
- Pin an SDK version, review release notes before upgrades, and maintain a rollback package.

No SDK can replace application authorization, ledger controls, incident response, backup
policy, or legal/compliance review.
