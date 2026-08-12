# API support matrix

Verification states:

- **Planned**: identified in source material but not implemented.
- **Implemented**: implemented from a documented contract and covered by mocked tests.
- **Status-only**: success status is documented but no reliable response model exists.
- **Unverified**: implementation exists but requires confirmation against an authorized
  environment before stable use.
- **Unsupported**: insufficient contract information exists for a safe implementation.

| Service | Authentication | Current status | Notes |
| --- | --- | --- | --- |
| Payment Gateway | Bearer token with automatic acquisition and refresh | Implemented | Mock-tested from the available v3 contract; environment verification remains the integrator's responsibility. |
| Transferor v2 | Automatic service token and refresh | Implemented | Mock-tested from the available v2.5 contract; financial writes require inquiry reconciliation. |
| Cobank settlements | Automatic scoped token and refresh | Unverified | Mock-tested from the consolidated catalog; routes, scopes, and transfer limits require environment confirmation. |
| Identicator | Bearer token with automatic acquisition and refresh | Implemented | Mock-tested; deeply nested legal, foreigner, cheque, and corporation payloads use typed envelopes with raw nested mappings. |
| Biometric/KYC | Configured static bearer token | Unverified | Mock-tested from conflicting catalog/snapshot contracts; environment confirmation is required. |
| Direct Debit | Automatic token and refresh | Unverified | Mock-tested from the catalog; five operations are status-only. |
| Pulse SMS | Automatic token and refresh | Unverified | Mock-tested from the catalog; message content is excluded from logs. |
| MzaHub contracts | Automatic login and refresh | Unverified | Mock-tested from the catalog; signed documents and signer identity are excluded from logs. |

## Known Direct Debit response limitation

The following operations have a documented successful status but no reliable response-body
schema. They will return an explicit status-only result while preserving an optional raw
body for diagnostics:

- `PUT /directdebit/api/v1/mandate/revoke`
- `PUT /directdebit/api/v1/mandate/enable`
- `PUT /directdebit/api/v1/mandate/disable`
- `POST /directdebit/api/v1/transaction/otp/{mandate-no}`
- `POST /directdebit/api/v1/blue-bank-callback`

No consumer should depend on undocumented response fields.

Other exposed Direct Debit operations include typed mandate initiation, collection,
transaction inquiry, subscription transaction listing, mandate inquiry by either provider
or creditor reference, and active-bank discovery. Mandate creation and collection are
unsafe and never automatically retried. The callback forwarding method accepts only a
validated body, but applications must verify callback authenticity before calling it.

## Pulse SMS

Simple, pattern, and bulk sends are typed and never automatically retried. Message, pattern
parameters, sender, receptor, and bulk contents are excluded from diagnostics. Status
inquiry by provider or client message ID, bulk inquiry, and inbound-message paging are
read-only. All operations are mock-tested and remain environment-unverified.

## MzaHub contracts

Contract creation accepts PDF bytes, validates the PDF signature and signer input, then
uses the catalog's JSON/base64 contract. Creation and cancellation are unsafe and never
automatically replayed; inquiry and signed-document download are read-only. `X-REAL-IP` is
required explicitly and validated as an IP address. Merchant signing-workflow and signature
extraction endpoints are not exposed because their sensitive media and workflow contracts
have not been verified. All implemented operations remain environment-unverified.

## Payment Gateway v3

All operations below use automatic service-scoped bearer authentication. “Typed” means
the documented response is validated before it is returned. “Status-only” means success
is determined by the HTTP status and an optional body is preserved without interpretation.

| SDK operation | HTTP contract | Model coverage | Retry classification | Verification |
| --- | --- | --- | --- | --- |
| `create_purchase` | `POST /ppg/v3/purchases` | Typed | Unsafe; never automatic | Implemented, mock-tested |
| `filter_purchases` / `inquire_purchase` | `GET /ppg/v3/purchases` | Typed | Read-only | Implemented, mock-tested |
| `verify_purchase` | `POST /ppg/v3/purchases/{purchaseId}/verify` | Typed | Idempotent | Implemented, mock-tested |
| `reverse_purchase` | `POST /ppg/v3/purchases/reverse` | Typed | Idempotent | Implemented, mock-tested |
| `refund_purchase` | `POST /ppg/v3/purchases/refund` | Typed | Unsafe; never automatic | Implemented, mock-tested |
| `inquire_refund` | `GET /ppg/v3/purchases/refunds/{refundId}` | Typed | Read-only | Implemented, mock-tested |
| `verify_refund` | `POST .../{refundId}/verify` | Status-only (`204`) | Unsafe; never automatic | Implemented, mock-tested |
| `retry_refund` | `POST .../{refundId}/retry` | Status-only (`200`) | Unsafe; never automatic | Implemented, mock-tested |
| `cancel_refund` | `POST .../{refundId}/cancel` | Status-only (`200`) | Unsafe; never automatic | Implemented, mock-tested |
| `ignore_refund_cancellable_delay` | `POST .../{refundId}/ignore-cancellable` | Status-only (`200`) | Unsafe; never automatic | Implemented, mock-tested |
| `list_terminals` | `GET /ppg/v3/terminals/list` | Typed | Read-only | Implemented, mock-tested |
| `filter_settlements` | `GET /ppg/v3/settlements` | Typed | Read-only | Implemented, mock-tested |
| `filter_purchase_histories` | `GET /ppg/v3/purchases/histories` | Typed | Read-only | Implemented, mock-tested |
| `get_balances` | `GET /ppg/v3/balances` | Typed | Read-only | Implemented, mock-tested |
| `health` | `GET /ppg/v3/app/health` | Typed | Read-only | Implemented, mock-tested |

The four PPG refund actions above have documented successful statuses but no response-body
schema. Their `APIResponse[StatusResult]` keeps `raw_body` only as uninterpreted bytes.
Do not build business behavior around body fields observed in a particular environment.

## Transferor v2

| SDK operation | HTTP contract | Model coverage | Retry classification |
| --- | --- | --- | --- |
| `submit_batch` | `POST /trf/v2/transfers` | Typed request/result | Unsafe; reconcile by `batch_id` |
| `inquire` | `GET /trf/v2/transfers` | Typed | Read-only |
| `cancel` | `DELETE /trf/v2/transfers` | Status-only | Unsafe; never automatic |
| `retry_failed` | `PATCH /trf/v2/transfers` | Status-only | Unsafe; never automatic |
| `filter_transfers` | `GET /trf/v2/transfers/filter` | Typed | Read-only |
| `set_receipt_enabled` | `POST /trf/v2/receipts` | Typed | Unsafe; never automatic |
| `get_balances` | `GET /trf/v2/balances` | Typed | Read-only |
| `get_daily_usage_report` | `GET /trf/v2/reports/daily` | Typed | Read-only |
| `get_supported_normal_banks` | `GET /trf/v2/banks/normal` | Typed | Read-only |
| `get_active_normal_banks` | `GET /trf/v2/banks/status` | Typed | Read-only |
| `generate_batch` | `POST /trf/v2/batch/generate` | Typed request/result | Idempotent helper |

Transferor creation has business references but no documented idempotency header.
`batch_id` and `transfer_id` support inquiry; they do not authorize blind resubmission.
Cancellation and explicit provider retry have no documented response schema and are
status-only. Public receipt state is conservatively treated as unsafe because the contract
does not establish idempotency semantics.

## Cobank settlements

| SDK operation | HTTP contract | Model coverage | Retry classification |
| --- | --- | --- | --- |
| `create_settlement` | `POST /cobank/v1/orders/settlement` | Typed | Unsafe; reconcile by `record_track_id` |
| `inquire_settlement` | `GET .../settlement/{trackId}` | Typed | Read-only |
| `batch_inquire_settlements` | `POST .../settlement/batch-inquiry` | Typed | Idempotent inquiry |
| `list_settlements` | `GET .../settlement/list` | Typed | Read-only |
| `get_merchant_accounts` | `GET /cobank/v1/accounts/` | Flexible safe container | Read-only |
| `set_settlement_receipt` | `PUT .../{reference}/receipt-link` | Typed | Idempotent |
| `set_record_receipt` | `PUT .../{reference}/records/{record}/receipt-link` | Typed | Idempotent |

The Cobank catalog documents many additional statement, refund, collect, waiting-state, and
augmented-transfer mutation endpoints. They are intentionally not exposed in this phase:
their safe workflow, permissions, reconciliation rules, or stable response expectations
have not been independently verified. Merchant-account configuration is provider-evolving
and therefore remains a typed root container of raw mappings. Cobank is environment-
unverified even though all exposed operations are mock-tested.

## Identicator

Identicator operations use automatic service-specific token acquisition and refresh.
Banking, postal, matching, identity, legal identity, foreigner identity, military status,
Sana, corporation, cheque, balance, usage-report, availability, and health inquiries are
implemented and tested at the mocked transport boundary. All operations are read-only or
idempotent inquiry POSTs; retry behavior is bounded to transient failures.

Core banking, postal, civil identity, matching, similarity, balance, and health fields have
dedicated typed models. Very large and provider-evolving legal, foreigner, corporation, and
cheque subtrees are held in typed response envelopes as raw nested mappings. Their data is
available to advanced consumers, but individual nested keys are not a stable SDK guarantee.

## Biometric and KYC

| SDK operation | Catalog contract | Model coverage | Verification |
| --- | --- | --- | --- |
| `verify_video` | `POST /alpha/v2/kyc` | Typed envelope, flexible result data | Mock-tested, environment-unverified |
| `verify_photo` | `POST /alpha/v2/authorization` | Typed envelope, flexible result data | Mock-tested, environment-unverified |
| `ocr_national_card` | `POST /alpha/ocr` | Typed envelope, flexible OCR data | Mock-tested, environment-unverified |
| `ocr_cheque` | `POST /alpha/cheque` | Typed envelope, flexible OCR data | Mock-tested, environment-unverified |
| `ocr_bank_card` | `POST /alpha/bank/card` | Typed envelope, flexible OCR data | Mock-tested, environment-unverified |

The available KYC documentation snapshot includes an `/alpha/api/...` prefix while the
newer consolidated catalog declares `/alpha/...`. The SDK follows the catalog and supports
per-service `base_url` overrides, but the routes must be verified in an authorized Jibit
environment before production use. The catalog describes success as a JSON string while
examples show a JSON object; both forms are parsed into a safe typed envelope.

KYC token acquisition and refresh are not documented. The SDK requires a supplied static
bearer token and does not guess an authentication lifecycle. Media is validated, isolated in
multipart parts, excluded from representations, and never logged. All KYC POST operations
are classified unsafe and are not automatically retried.
