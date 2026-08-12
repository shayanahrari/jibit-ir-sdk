"""Configuration validation and secret-safety tests."""

import pytest
from pydantic import ValidationError

from jibit.config import JibitConfig, RetryConfig, ServiceCredentials
from jibit.exceptions import JibitConfigurationError
from jibit.types import ServiceName


def test_top_level_service_shorthand_is_validated() -> None:
    """Users can configure a service without manually nesting credentials."""
    config = JibitConfig.from_mapping(
        {
            "payment_gateway": {
                "api_key": "public-key",
                "secret_key": "private-secret",
            }
        }
    )

    service = config.service(ServiceName.PAYMENT_GATEWAY)

    assert service.credentials.api_key is not None
    assert service.credentials.api_key.get_secret_value() == "public-key"
    assert "private-secret" not in repr(config)


def test_nested_service_configuration_and_url_override() -> None:
    """Explicit service mappings retain advanced configuration fields."""
    config = JibitConfig.from_mapping(
        {
            "services": {
                "sms": {
                    "username": "user",
                    "password": "password",
                    "base_url": "https://sandbox.example.test",
                }
            }
        }
    )

    assert str(config.service(ServiceName.SMS).base_url) == "https://sandbox.example.test/"


@pytest.mark.parametrize(
    "credentials",
    [
        {"api_key": "only-one"},
        {"secret_key": "only-one"},
        {"username": "only-one"},
        {"password": "only-one"},
        {},
    ],
)
def test_incomplete_credentials_are_rejected(credentials: dict[str, str]) -> None:
    """Partial or empty credential pairs fail before any network request."""
    with pytest.raises(ValidationError):
        ServiceCredentials.model_validate(credentials)


def test_retry_delay_bounds_are_validated() -> None:
    """An impossible retry delay range is rejected."""
    with pytest.raises(ValidationError, match="max_delay"):
        RetryConfig(base_delay=2, max_delay=1)


def test_missing_or_disabled_service_raises_safe_error() -> None:
    """Accessing an unavailable service produces an SDK configuration error."""
    config = JibitConfig.from_mapping(
        {
            "direct_debit": {
                "api_key": "key",
                "secret_key": "secret",
                "enabled": False,
            }
        }
    )

    with pytest.raises(JibitConfigurationError, match="direct_debit"):
        config.service(ServiceName.DIRECT_DEBIT)
    with pytest.raises(JibitConfigurationError, match="contracts"):
        config.service(ServiceName.CONTRACTS)


def test_unknown_configuration_fields_are_rejected() -> None:
    """Misspelled or unsupported settings cannot silently change behavior."""
    with pytest.raises(ValidationError):
        JibitConfig.from_mapping({"verify_tls": False})
