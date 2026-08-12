# Changelog

All notable changes are documented in this file. The project follows
[Semantic Versioning](https://semver.org/) and uses an unreleased section while changes
are being prepared.

## [Unreleased]

### Added

- Initial package, documentation, quality tooling, and CI foundation.
- Typed configuration, transport abstraction, structured exceptions, safe retry policy,
  correlation IDs, redacted logging, audit hooks, and raw response access.
- Service-aware token acquisition and refresh, thread-safe in-memory storage, Django Cache
  and Redis adapters, distributed refresh locking, and bounded safe 401 recovery.
- Typed Payment Gateway v3 purchase, verification, reversal, refund, inquiry, settlement,
  terminal, balance, and health operations with status-only refund actions, audit events,
  and reconciliation-safe retry classification.
- Typed Identicator banking, identity, postal, matching, legal, social, cheque, balance,
  reporting, availability, and health inquiries; KYC multipart video, photo, and OCR
  operations using explicit static bearer authentication and media-safe diagnostics.
- Transferor v2 batch submission, inquiry, cancellation, explicit retry, filtering,
  receipts, balances, usage, bank status, and batch generation; Cobank settlement creation,
  reconciliation, batch inquiry, listing, account discovery, and receipt controls with
  isolated token scopes and conservative financial retry behavior.
- Direct Debit mandate and collection lifecycle with five explicitly status-only operations,
  Pulse SMS simple, pattern, bulk, status, and inbound operations, MzaHub contract creation,
  inquiry, cancellation, and signed-document download, plus fail-closed callback parsing,
  verification, and deduplication extension points.
