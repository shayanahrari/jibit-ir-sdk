# Source provenance

The SDK is implemented from locally supplied Jibit technical material. Source documents
are not distributed with the repository or package. This register records only the
minimum metadata necessary to explain implementation provenance.

| Source | Version or date | Used for | Distribution |
| --- | --- | --- | --- |
| Consolidated API catalog | OpenAPI 3.1, catalog version 1.0.0 | Cross-service paths and schemas | Not distributed |
| Transferor REST API documentation | Version 2.5, 22 July 2024 | Transfers and settlement behavior | Not distributed |
| Identicator technical documentation | Version 1.5.2, October 2024 | Inquiry and identity behavior | Not distributed |
| Identity-service technical documentation | Version 2.6.1, September 2025 | Identity verification behavior | Not distributed |
| Payment Gateway documentation | Retrieved August 2026 | PPG operations and empty response behavior | Not distributed |
| KYC documentation snapshot | Retrieved August 2026 | KYC operation discovery and contract comparison | Not distributed |

## Provenance policy

- Documentation in this repository is original and describes the SDK's public behavior.
- Source PDFs, screenshots, catalogs, logos, and confidential text are not copied.
- Incomplete or conflicting upstream behavior is identified in the API support matrix.
- A source contract must be confirmed before an operation is marked stable.
- When source contracts conflict, the selected contract and unresolved difference are
  recorded in the API support matrix instead of silently choosing a stable behavior.
