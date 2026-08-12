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
| Payment Gateway | Service token and refresh token | Planned | Four actions use documented empty successful responses. |
| Cobank/transfers | Service token and refresh token | Planned | Financial submissions require reconciliation-safe behavior. |
| Identicator | Service token and refresh token | Planned | Identity and banking fields require strict redaction. |
| Biometric/KYC | Operation-specific authorization | Planned | Media and identity payloads are never logged. |
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
