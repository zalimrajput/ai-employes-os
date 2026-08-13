"""Zoho CRM client built on stored OAuth credentials.

Tokens are stored encrypted by ``app.services.integration_service``; this
client decrypts them and talks to the Zoho CRM REST API with httpx. On a 401
the refresh_token is exchanged for a new access_token, the encrypted row is
updated, and the request is retried once — same contract as the Gmail client.
"""
import httpx

from app.integrations.gmail.client import (  # noqa: F401  (shared error contract)
    IntegrationAuthError,
    IntegrationNotConnectedError,
)

ZOHO_AUTH_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
ZOHO_API_BASE = "https://www.zohoapis.com/crm/v2"


class ZohoCRMClient:
    """Minimal Zoho CRM client (Leads + Contacts modules) with automatic token refresh."""

    def __init__(
        self,
        *,
        db,
        organization_id,
        access_token: str | None,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_url: str = ZOHO_AUTH_TOKEN_URL,
        api_base: str = ZOHO_API_BASE,
    ):
        self._db = db
        self._organization_id = organization_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._api_base = api_base

    # -- internal helpers -------------------------------------------------

    def _headers(self) -> dict:
        return {"Authorization": f"Zoho-oauthtoken {self._access_token}"}

    def _refresh(self) -> None:
        if not (self._refresh_token and self._client_id and self._client_secret):
            raise IntegrationAuthError(
                "Zoho access token expired and no refresh credentials are available"
            )
        resp = httpx.post(
            self._token_url,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        if resp.status_code >= 300:
            raise IntegrationAuthError(
                f"Zoho token refresh failed: {resp.status_code} {resp.text[:200]}"
            )
        payload = resp.json()
        new_access = payload.get("access_token")
        if not new_access:
            raise IntegrationAuthError("Zoho token refresh returned no access_token")
        self._access_token = new_access
        if payload.get("refresh_token"):
            self._refresh_token = payload["refresh_token"]
        self._persist(new_access, payload.get("refresh_token"))

    def _persist(self, access_token: str, refresh_token: str | None) -> None:
        from app.services.integration_service import save_credentials

        tokens = {"access_token": access_token}
        if refresh_token:
            tokens["refresh_token"] = refresh_token
        save_credentials(self._db, self._organization_id, "zoho", tokens)

    def _request(self, method: str, path: str, *, params=None, json=None) -> httpx.Response:
        url = f"{self._api_base.rstrip('/')}/{path.lstrip('/')}"
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
                f"Zoho {action} failed: {resp.status_code} {resp.text[:200]}"
            )

    # -- public API -------------------------------------------------------

    def create_lead(
        self,
        *,
        last_name: str,
        first_name: str | None = None,
        company: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Create a lead in Zoho CRM (the 'Add John as a lead' flow)."""
        payload: dict = {"Last_Name": last_name}
        if first_name:
            payload["First_Name"] = first_name
        if company:
            payload["Company"] = company
        if email:
            payload["Email"] = email
        if phone:
            payload["Phone"] = phone
        if description:
            payload["Description"] = description
        resp = self._request("POST", "Leads", json={"data": [payload]})
        self._raise(resp, "create lead")
        data = resp.json()
        lead = (data.get("data") or [{}])[0]
        return {
            "created": True,
            "lead_id": lead.get("id"),
            "status": lead.get("Status"),
            "record_details": lead.get("details") or lead,
        }

    def create_customer(
        self,
        *,
        name: str,
        company: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Create a customer as a Contact in Zoho CRM (mirrors internal CRM).

        The name is split into First_Name/Last_Name when it contains a space;
        `company` maps to the Account_Name field, `notes` to Description.
        """
        parts = [p for p in (name or "").strip().split() if p]
        first_name = " ".join(parts[:-1]) if len(parts) > 1 else None
        last_name = parts[-1] if parts else (name or "")

        payload: dict = {}
        if first_name:
            payload["First_Name"] = first_name
        payload["Last_Name"] = last_name
        if company:
            payload["Account_Name"] = company
        if email:
            payload["Email"] = email
        if phone:
            payload["Phone"] = phone
        if address:
            payload["Mailing_Street"] = address
        if notes:
            payload["Description"] = notes

        resp = self._request("POST", "Contacts", json={"data": [payload]})
        self._raise(resp, "create customer")
        data = resp.json()
        contact = (data.get("data") or [{}])[0]
        return {
            "created": True,
            "contact_id": contact.get("id"),
            "record_details": contact.get("details") or contact,
        }

    def list_leads(self, limit: int = 25) -> list[dict]:
        """List recent leads from Zoho CRM."""
        resp = self._request(
            "GET", "Leads", params={"per_page": int(limit or 25)}
        )
        self._raise(resp, "list leads")
        data = resp.json()
        return [
            {
                "lead_id": lead.get("id"),
                "full_name": " ".join(
                    filter(
                        None,
                        [
                            lead.get("First_Name") or "",
                            lead.get("Last_Name") or "",
                        ],
                    )
                ).strip(),
                "company": lead.get("Company"),
                "email": lead.get("Email"),
                "phone": lead.get("Phone"),
            }
            for lead in data.get("data") or []
        ]

    def search_leads(self, *, email: str | None = None, phone: str | None = None) -> list[dict]:
        """Search leads by email or phone via Zoho's search endpoint."""
        criteria = []
        if email:
            criteria.append(f"(Email:equals:{email})")
        if phone:
            criteria.append(f"(Phone:equals:{phone})")
        if not criteria:
            return []
        resp = self._request(
            "GET",
            "Leads/search",
            params={"criteria": "or".join(criteria)},
        )
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Zoho search leads failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return [lead.get("id") for lead in data.get("data") or []]
