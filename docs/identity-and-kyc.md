# Identicator and KYC

Identicator handles banking and identity inquiries. KYC handles biometric video, photo,
and OCR uploads. They are separate service scopes and do not share credentials or tokens.
All identity, banking, and media payloads are sensitive and excluded from operational logs.

## Identicator configuration

Identicator has a documented token lifecycle. Configure its API key and secret key once;
the SDK acquires, caches, refreshes, and attaches its bearer token automatically:

```python
import os

from jibit import JibitClient

client = JibitClient.from_config(
    {
        "identicator": {
            "api_key": os.environ["JIBIT_IDENTICATOR_API_KEY"],
            "secret_key": os.environ["JIBIT_IDENTICATOR_SECRET_KEY"],
        }
    }
)
```

## Banking inquiries

```python
iban = client.identicator.inquire_iban("IR000000000000000000000000")
card = client.identicator.inquire_card(
    "6037990000000001",
    include_iban=True,
)
deposit = client.identicator.inquire_deposit(
    bank="EXAMPLE_BANK",
    number="account-number",
    include_iban=True,
)
```

Card inquiry accepts at most one conversion flag because the upstream contract rejects
ambiguous combinations. Return values expose typed `.data` plus `.raw` diagnostics.

## Matching and identity inquiries

Matching accepts only documented identifier combinations and validates them before network
I/O:

```python
match = client.identicator.match(
    iban="IR000000000000000000000000",
    national_code="0013547891",
)

identity = client.identicator.inquire_identity(
    national_code="0013547891",
    birth_date="13600101",
)

similarity = client.identicator.compare_identity_names(
    national_code="0013547891",
    birth_date="13600101",
    full_name="Expected Person Name",
)
```

Identity inquiry defaults `without_photo=True` to minimize returned sensitive data. Set it
to false only when the application has a justified requirement, access controls, retention
policy, and secure storage for the image.

Legal identity, sign-holder, foreigner identity, military status, Sana, corporation, and
cheque inquiries are also available. Their top-level contracts are typed, while very large
provider-evolving nested structures remain raw mappings inside those envelopes. Do not log
or serialize them into errors.

`track_id` is optional on supported operations. Use a non-sensitive business tracking value;
never put a national code, IBAN, card number, mobile number, or name into that header.

## KYC configuration

The available KYC material documents bearer authentication but no safe token acquisition,
expiry, or refresh contract. Supply an already issued access token:

```python
client = JibitClient.from_config({"kyc": {"access_token": os.environ["JIBIT_KYC_ACCESS_TOKEN"]}})
```

The SDK attaches the token but does not refresh it. Rotation and replacement are controlled
by the consuming application until an authorized lifecycle contract is available.

## Photo and video verification

Use `MediaFile` to provide bytes, filename metadata, and MIME type without exposing content
through representations:

```python
from pathlib import Path

from jibit.services.kyc import MediaFile

photo = MediaFile(
    content=Path("private/live-face.jpg").read_bytes(),
    filename="live-face.jpg",
    content_type="image/jpeg",
)

result = client.kyc.verify_photo(
    national_id="0013547891",
    live_face=photo,
)
```

Video verification uses `verify_video` with an MP4-compatible `MediaFile`, national ID,
and challenge line. KYC media is classified as an unsafe POST: timeout and network failures
are surfaced without automatic resubmission. Let the user retry through an explicit product
flow after assessing provider state and consent.

## OCR

National-card, cheque, and bank-card OCR are separate methods:

```python
ocr = client.kyc.ocr_national_card(photo, is_back=False, try_rotate=True)
```

The consolidated catalog and documentation snapshot conflict on route prefixes and success
response shape. The SDK uses catalog routes and accepts either a JSON object or JSON string
response. KYC remains environment-unverified: confirm routes, token behavior, MIME types,
file limits, and result fields with your authorized environment before production rollout.

## Privacy and production checklist

- Obtain and record appropriate user consent before identity or biometric processing.
- Minimize requested and retained identity fields; keep photos disabled when unnecessary.
- Never log request/response bodies, media bytes, filenames, national codes, cards, IBANs,
  account numbers, mobile numbers, birth dates, or names.
- Encrypt sensitive records and media in transit and at rest with application-owned controls.
- Define retention and secure-deletion policies for media and identity responses.
- Restrict access by role, tenant, and purpose, and retain redacted audit events.
- Verify conflicting KYC paths and schemas in an authorized environment before production.
