# Jibit IR SDK

Jibit IR SDK is an unofficial, typed Python client for integrating with Jibit APIs. The
package prioritizes a small public API, automatic authentication, financial-operation
safety, secure logging, and explicit documentation of upstream contract limitations.

The package is currently under active development. Start with the repository
[README](https://github.com/shayanahrari/jibit-ir-sdk#readme), then review the architecture
and API support matrix before using an operation in a production system.

Payment Gateway v3 is the first implemented domain. See the
[Payment Gateway guide](payment-gateway.md) for purchase initialization, callback handling,
verification, reversal, refund, inquiry, and uncertain-outcome guidance.

For banking inquiries, identity matching, civil identity data, and biometric uploads, read
the [Identicator and KYC guide](identity-and-kyc.md), including its data-minimization and
environment-verification requirements.
