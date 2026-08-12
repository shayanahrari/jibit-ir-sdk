# Security Policy

## Supported versions

Security fixes are applied to the latest released minor version. Until version `1.0.0`,
the latest published `0.x` release is the only supported line.

## Reporting a vulnerability

Report vulnerabilities privately through the repository's private vulnerability
reporting feature. Do not open a public issue containing credentials, tokens, customer
data, exploit details, or financial transaction information.

Include the affected version, impact, minimal reproduction, and suggested mitigation when
available. Remove or redact all real credentials and personal data.

## Security boundaries

The SDK is responsible for safe request construction, token handling, redaction, retry
classification, and callback parsing. Applications remain responsible for authorization,
business-level idempotency, secret storage, database security, callback routing, log
retention, and regulatory obligations.
