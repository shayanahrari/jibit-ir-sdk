"""Shared public types used across the SDK."""

from __future__ import annotations

from enum import Enum


class ServiceName(str, Enum):
    """Identify a Jibit API service and its isolated authentication scope."""

    PAYMENT_GATEWAY = "payment_gateway"
    TRANSFERS = "transfers"
    IDENTICATOR = "identicator"
    KYC = "kyc"
    DIRECT_DEBIT = "direct_debit"
    SMS = "sms"
    CONTRACTS = "contracts"
