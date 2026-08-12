# Pulse SMS and MzaHub contracts

Pulse and MzaHub use independent credential and token scopes. Configure only enabled
services and keep credentials in environment variables or a secret manager.

## Pulse SMS

```python
client = JibitClient.from_config(
    {
        "sms": {
            "api_key": os.environ["JIBIT_SMS_API_KEY"],
            "secret_key": os.environ["JIBIT_SMS_SECRET_KEY"],
        }
    }
)

sent = client.sms.send(
    receptor="<mobile-number>",
    message="Your notification text",
    client_message_id="notification-000042",
)
```

Simple, pattern, and bulk sends are unsafe operations and are not automatically replayed.
Use unique client references and inquire by client message ID or provider message ID after
an uncertain result. Pattern parameters, message bodies, receptors, senders, and bulk lists
are never logged. The application must also prevent them from entering its own logs,
analytics, exception reporting, and audit metadata.

Bulk creation accepts either `message` or `predefined_message_id`, never both, and limits a
request to 1,000 receptors. Inbound-message queries require an explicit date range and
zero-based page. Apply authorization and retention rules before storing inbound messages.

## MzaHub contracts

```python
from jibit.services.contracts import Signer

client = JibitClient.from_config(
    {
        "contracts": {
            "api_key": os.environ["JIBIT_MZAHUB_API_KEY"],
            "secret_key": os.environ["JIBIT_MZAHUB_SECRET_KEY"],
        }
    }
)

created = client.contracts.initiate(
    track_id="contract-000042",
    pdf=pdf_bytes,
    redirect_url="https://merchant.example/contracts/return",
    signers=[
        Signer(
            national_code="<national-code>",
            birth_date="<provider-date-format>",
        )
    ],
    real_ip="<end-user-ip>",
)
```

The SDK validates base64 conversion, PDF signature, signer count, identity format, and the
required `X-REAL-IP`. It does not guess the end-user IP. Determine it at the trusted
application boundary using a correctly configured reverse-proxy policy; do not accept a
spoofable forwarded header directly from the internet.

Creation and cancellation are not automatically replayed. Persist `track_id` and reconcile
through `inquire(track_id, real_ip=...)`. Download a signed PDF only after checking the
contract state and authorize access to the requesting user or tenant. Signed-document bytes
are returned in a secret-safe model and never logged or written to disk by the SDK.

Pulse and MzaHub are mock-tested from the consolidated catalog and remain environment-
unverified. MzaHub merchant signing-step and signature-extraction endpoints are not exposed
because the available material is insufficient to establish a safe high-level workflow.
