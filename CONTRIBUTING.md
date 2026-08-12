# Contributing

Thank you for improving Jibit IR SDK. Contributions must preserve the package's security,
compatibility, and confidentiality guarantees.

## Development setup

```bash
python -m venv .venv
python -m pip install -e ".[dev,django,redis]"
```

## Required checks

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=jibit --cov-report=term-missing
mkdocs build --strict
python -m build
python -m twine check dist/*
python -m pip_audit .
python -m pip check
```

## Contribution rules

- Keep runtime messages, exception text, log events, identifiers, and documentation in
  English.
- Never commit credentials, tokens, OTPs, private customer data, logs, or real API
  payloads.
- Never commit third-party source documentation unless redistribution is authorized.
- Mock HTTP at the transport boundary. Automated tests must not call real financial or
  identity APIs.
- Treat retry behavior, logging changes, and public API changes as security-sensitive.
- Add tests and documentation for public behavior.
- Use focused conventional commit messages.
