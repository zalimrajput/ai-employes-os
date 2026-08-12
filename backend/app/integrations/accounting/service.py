"""Lookup helper: build an AccountingClient from the configured settings."""

from app.core.config import settings
from app.integrations.accounting.client import AccountingClient


def get_client() -> AccountingClient:
    """Return an AccountingClient configured from ``ACCOUNTING_BASE_URL`` and
    ``ACCOUNTING_API_KEY``. Raises ``AccountingError`` when unconfigured."""
    return AccountingClient(
        base_url=settings.ACCOUNTING_BASE_URL or "",
        api_key=settings.ACCOUNTING_API_KEY or "",
    )
