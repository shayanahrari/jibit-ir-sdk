# Versioning and compatibility

The package follows Semantic Versioning and exposes its version as `jibit.__version__`.

## Supported runtimes

- Python 3.10, 3.11, 3.12, and 3.13.
- Pydantic 2.7 or newer within major version 2.
- HTTPX 0.27 or newer below major version 1.
- Optional Django 5.2 LTS and 6.0.
- Optional redis-py 5 and 6.

The CI matrix runs the test suite across each declared Python version and separately tests
the Django 5.2 and 6.0 series. The quality job also runs formatting, linting, strict type
checking, documentation build, package build, metadata validation, dependency audit, and
dependency consistency checks.

## Public compatibility

Public imports, client service properties, method signatures, request/response model fields,
exception classes, operation safety behavior, event names, and configuration fields form the
SDK contract. Raw upstream response bytes and explicitly documented flexible mappings are
available for advanced use but their provider-specific nested keys are not stable SDK APIs.

Before `1.0.0`, incompatible public changes may be required when upstream behavior is
corrected. They require a minor-version increment and a clear changelog entry. Patch releases
contain compatible fixes and security hardening.

After `1.0.0`:

- breaking public changes require a major release;
- compatible features require a minor release;
- compatible fixes require a patch release;
- planned removal should be deprecated for at least one minor release;
- deprecations must use a documented warning and migration path;
- an unsafe API may be removed or disabled sooner when security or financial integrity
  requires it.

## Upstream contract changes

The support matrix distinguishes implemented, unverified, status-only, and unsupported
behavior. Environment verification can promote an operation's confidence without changing
its API. A provider contract change that alters request meaning, authentication, retry
safety, or reconciliation behavior may require a new SDK API instead of silently changing
the old one.

## Release process

For a release candidate:

1. Confirm the target version and update `src/jibit/__about__.py`.
2. Move relevant changelog entries from Unreleased into a dated version section.
3. Run every local quality command and confirm the CI matrix.
4. Inspect wheel and source-distribution contents for confidential or generated material.
5. Test installation in a clean environment and import both core and optional integrations.
6. Publish to TestPyPI and perform a clean install smoke test.
7. Create a signed or protected release tag through the repository's release process.
8. Publish to PyPI only from a trusted CI environment using a trusted publisher.

Version `0.1.0` is an alpha baseline. Do not mark `1.0.0` until production contracts have
been verified in an authorized environment and compatibility commitments are supportable.
