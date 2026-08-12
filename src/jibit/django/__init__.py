"""Optional Django integration for Jibit client configuration and lifecycle."""

from jibit.django.client import close_jibit_client, get_jibit_client

__all__ = ["close_jibit_client", "get_jibit_client"]
