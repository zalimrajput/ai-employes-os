"""Accounting system client (API-key based).

Pushes invoices and expenses to an external accounting system (e.g. a
QuickBooks/Xero-style REST endpoint) configured through
``ACCOUNTING_BASE_URL`` and ``ACCOUNTING_API_KEY``. The client is intentionally
thin: it posts standard invoice/expense payloads and returns the external id.
"""
from datetime import date

import httpx


class AccountingError(Exception):
    """Raised when the accounting system rejects the request."""


class AccountingClient:
    """Minimal accounting system client built on an API key."""

    def __init__(self, *, base_url: str, api_key: str, timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: dict) -> dict:
        if not self._base_url:
            raise AccountingError("Accounting system is not configured (ACCOUNTING_BASE_URL)")
        resp = httpx.post(
            f"{self._base_url}/{path.lstrip('/')}",
            headers=self._headers(),
            json=payload,
            timeout=self._timeout,
        )
        if resp.status_code >= 300:
            raise AccountingError(
                f"Accounting request failed: {resp.status_code} {resp.text[:200]}"
            )
        try:
            data = resp.json() if resp.content else {}
        except Exception:
            data = {}
        return data if isinstance(data, dict) else {}

    # -- public API -------------------------------------------------------

    def push_invoice(
        self,
        *,
        invoice_number: str,
        customer_name: str | None = None,
        amount: float,
        currency: str = "USD",
        due_date: str | None = None,
        status: str = "unpaid",
        items: list | None = None,
    ) -> dict:
        """Create an invoice in the external accounting system."""
        return self._post(
            "/invoices",
            {
                "invoice_number": invoice_number,
                "customer_name": customer_name,
                "amount": amount,
                "currency": currency,
                "due_date": due_date,
                "status": status,
                "items": items or [],
            },
        )

    def push_expense(
        self,
        *,
        description: str,
        amount: float,
        currency: str = "USD",
        category: str | None = None,
        occurred_on: str | None = None,
    ) -> dict:
        """Record an expense in the external accounting system."""
        return self._post(
            "/expenses",
            {
                "description": description,
                "amount": amount,
                "currency": currency,
                "category": category,
                "occurred_on": occurred_on,
            },
        )
