"""Xero accounting client built on stored OAuth credentials.

Xero's token endpoints authenticate with **HTTP Basic** credentials
(client_id:client_secret) rather than form fields. Invoices are created via
the Accounting API (``/api.xro/2.0``). On a 401 the refresh token is
exchanged (Basic auth), the encrypted row is updated, and the request retried.
"""
import httpx

from app.integrations.gmail.client import (  # noqa: F401  (shared error contract)
    IntegrationAuthError,
    IntegrationNotConnectedError,
)

XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"


class XeroClient:
    """Minimal Xero Accounting API client (invoices) with token refresh.

    Xero's Accounting API requires the ``Xero-Tenant-Id`` header on every
    call. The tenant is resolved lazily from the /connections endpoint (and
    cached on the integration row) so the caller never has to know it.
    """

    def __init__(
        self,
        *,
        db,
        organization_id,
        access_token: str | None,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_url: str = XERO_TOKEN_URL,
        api_base: str = XERO_API_BASE,
        tenant_id: str | None = None,
    ):
        self._db = db
        self._organization_id = organization_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._api_base = api_base
        self._tenant_id = tenant_id

    # -- internal helpers -------------------------------------------------

    def _headers(self) -> dict:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        if self._tenant_id:
            headers["Xero-Tenant-Id"] = self._tenant_id
        return headers

    def _resolve_tenant(self) -> str:
        """Fetch and cache the Xero organisation (tenant) id for this account."""
        if self._tenant_id:
            return self._tenant_id
        resp = httpx.request(
            "GET",
            XERO_CONNECTIONS_URL,
            headers={"Authorization": f"Bearer {self._access_token}"},
            timeout=30,
        )
        if resp.status_code == 401:
            self._refresh()
            resp = httpx.request(
                "GET",
                XERO_CONNECTIONS_URL,
                headers={"Authorization": f"Bearer {self._access_token}"},
                timeout=30,
            )
        if resp.status_code >= 300:
            raise IntegrationAuthError(
                f"Xero connections lookup failed: {resp.status_code} {resp.text[:200]}"
            )
        tenants = resp.json()
        if not isinstance(tenants, list) or not tenants:
            raise IntegrationAuthError("No Xero organisation is connected to this account")
        self._tenant_id = tenants[0].get("tenantId")
        self._persist_tenant(self._tenant_id)
        return self._tenant_id

    def _persist_tenant(self, tenant_id: str) -> None:
        """Cache the tenant id on the integration row (best-effort)."""
        try:
            from app.models.integration import Integration

            if self._db is None:
                return
            row = (
                self._db.query(Integration)
                .filter(
                    Integration.organization_id == self._organization_id,
                    Integration.provider == "xero",
                )
                .first()
            )
            if row is not None:
                meta = dict(row.metadata_json or {})
                meta["xero_tenant_id"] = tenant_id
                row.metadata_json = meta
                self._db.commit()
        except Exception:  # noqa: BLE001 - caching is best-effort
            pass

    def _basic_auth(self):
        return (self._client_id or "", self._client_secret or "")

    def _refresh(self) -> None:
        if not (self._refresh_token and self._client_id and self._client_secret):
            raise IntegrationAuthError(
                "Xero access token expired and no refresh credentials are available"
            )
        resp = httpx.post(
            self._token_url,
            auth=self._basic_auth(),
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
            timeout=30,
        )
        if resp.status_code >= 300:
            raise IntegrationAuthError(
                f"Xero token refresh failed: {resp.status_code} {resp.text[:200]}"
            )
        payload = resp.json()
        new_access = payload.get("access_token")
        if not new_access:
            raise IntegrationAuthError("Xero token refresh returned no access_token")
        self._access_token = new_access
        if payload.get("refresh_token"):
            self._refresh_token = payload["refresh_token"]
        self._persist(new_access, payload.get("refresh_token"))

    def _persist(self, access_token: str, refresh_token: str | None) -> None:
        from app.services.integration_service import save_credentials

        tokens = {"access_token": access_token}
        if refresh_token:
            tokens["refresh_token"] = refresh_token
        save_credentials(self._db, self._organization_id, "xero", tokens)

    def _request(self, method: str, path: str, *, params=None, json=None) -> httpx.Response:
        url = f"{self._api_base.rstrip('/')}/{path.lstrip('/')}"
        # The Accounting API rejects calls without the tenant id.
        if self._tenant_id is None:
            self._tenant_id = self._resolve_tenant()
        resp = httpx.request(
            method,
            url,
            headers=self._headers(),
            params=params,
            json=json,
            timeout=30,
        )
        if resp.status_code == 401:
            self._refresh()
            resp = httpx.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json,
                timeout=30,
            )
        return resp

    @staticmethod
    def _raise(resp: httpx.Response, action: str) -> None:
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Xero {action} failed: {resp.status_code} {resp.text[:200]}"
            )

    # -- public API -------------------------------------------------------

    def create_invoice(
        self,
        *,
        invoice_number: str,
        contact_name: str,
        amount: float,
        currency: str = "USD",
        due_date: str | None = None,
        description: str | None = None,
        status: str = "AUTHORISED",
    ) -> dict:
        """Create an accounts-receivable invoice in Xero."""
        payload = {
            "Type": "ACCREC",
            "Contact": {"Name": contact_name or "Unknown"},
            "LineItems": [
                {
                    "Description": description or invoice_number or "Invoice",
                    "Quantity": 1.0,
                    "UnitAmount": float(amount or 0),
                    "AccountCode": "200",
                }
            ],
            "Status": status,
        }
        if invoice_number:
            payload["InvoiceNumber"] = invoice_number
        if currency:
            payload["CurrencyCode"] = currency
        if due_date:
            payload["DueDate"] = due_date
        resp = self._request("POST", "Invoices", json=payload)
        self._raise(resp, "create invoice")
        data = resp.json()
        inv = ((data.get("Invoices") or [{}])[0]) if isinstance(data, dict) else {}
        return {
            "created": True,
            "invoice_id": inv.get("InvoiceID"),
            "invoice_number": inv.get("InvoiceNumber"),
            "status": inv.get("Status"),
            "total": inv.get("Total"),
        }

    def list_invoices(self, limit: int = 20) -> list[dict]:
        """List the tenant's recent invoices."""
        resp = self._request("GET", "Invoices", params={"page": 1})
        self._raise(resp, "list invoices")
        data = resp.json()
        return [
            {
                "invoice_id": inv.get("InvoiceID"),
                "invoice_number": inv.get("InvoiceNumber"),
                "status": inv.get("Status"),
                "total": inv.get("Total"),
                "currency": inv.get("CurrencyCode"),
            }
            for inv in (data.get("Invoices") or [])[: int(limit or 20)]
        ]
