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
| Cobank/transfers | Service token and refresh token | Planned | Financial submissions require reconciliation-safe behavior. |
| Identicator | Bearer token with automatic acquisition and refresh | Implemented | Mock-tested; deeply nested legal, foreigner, cheque, and corporation payloads use typed envelopes with raw nested mappings. |
| Biometric/KYC | Configured static bearer token | Unverified | Mock-tested from conflicting catalog/snapshot contracts; environment confirmation is required. |
| Direct Debit | Authentication and refresh token | Planned | Five operations are status-only. |
| Pulse SMS | Authentication and refresh token | Planned | Message content is sensitive and excluded from logs. |
| MzaHub contracts | Login and refresh token | Planned | Signed documents and identity data are excluded from logs. |

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
