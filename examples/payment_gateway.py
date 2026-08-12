"""Minimal Payment Gateway flow using environment-provided credentials."""

import os

from jibit import JibitClient


def create_payment() -> tuple[int, str]:
    """Create a purchase and return its identifier and payer redirect URL."""
    with JibitClient.from_config(
        {
            "payment_gateway": {
                "api_key": os.environ["JIBIT_PPG_API_KEY"],
                "secret_key": os.environ["JIBIT_PPG_SECRET_KEY"],
            }
        }
    ) as client:
        purchase = client.payment_gateway.create_purchase(
            amount=100_000,
            callback_url="https://merchant.example/payments/jibit/callback/",
            client_reference_number="replace-with-a-persisted-unique-reference",
        )
        return purchase.data.purchase_id, str(purchase.data.psp_switching_url)


if __name__ == "__main__":
    purchase_id, redirect_url = create_payment()
    print(f"Purchase {purchase_id} created; redirect the payer to {redirect_url}")
