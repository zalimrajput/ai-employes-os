"""Outlook (Microsoft Graph) email client built on stored OAuth credentials.

Mirrors ``app/integrations/gmail/client.py``: tokens are stored encrypted by
``app.services.integration_service.save_credentials``, decrypted here, and
calls go straight to the Microsoft Graph API via httpx. A 401 triggers a
refresh-token exchange that persists the new token and retries once. The
exception contract (``IntegrationAuthError`` / ``IntegrationNotConnectedError``)
is shared with the Gmail client so callers handle every integration the same
way.
"""
import base64
import json
from email.message import EmailMessage

import httpx

from app.integrations.gmail.client import (  # noqa: F401  (shared error contract)
    IntegrationAuthError,
    IntegrationNotConnectedError,
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SEND_URL = f"{GRAPH_BASE}/me/sendMail"
GRAPH_LIST_URL = f"{GRAPH_BASE}/me/messages"
OAUTH_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def _header_value(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)


class OutlookClient:
    """Minimal Microsoft Graph mail client with automatic token refresh."""

    def __init__(
        self,
        *,
        db,
        organization_id,
        access_token: str | None,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_url: str = OAUTH_TOKEN_URL,
        scope: str | None = None,
    ):
        self._db = db
        self._organization_id = organization_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._scope = scope

    # -- internal helpers -------------------------------------------------

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _refresh(self) -> None:
        if not (self._refresh_token and self._client_id and self._client_secret):
            raise IntegrationAuthError(
                "Outlook access token expired and no refresh credentials are available"
            )
        resp = httpx.post(
            self._token_url,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
                "scope": self._scope or "https://graph.microsoft.com/Mail.ReadWrite",
            },
            timeout=30,
        )
        if resp.status_code >= 300:
            raise IntegrationAuthError(
                f"Outlook token refresh failed: {resp.status_code} {resp.text[:200]}"
            )
        payload = resp.json()
        new_access = payload.get("access_token")
        if not new_access:
            raise IntegrationAuthError("Outlook token refresh returned no access_token")
        self._access_token = new_access
        if payload.get("refresh_token"):
            self._refresh_token = payload["refresh_token"]
        self._persist(new_access, payload.get("refresh_token"))

    def _persist(self, access_token: str, refresh_token: str | None) -> None:
        from app.services.integration_service import save_credentials

        tokens = {"access_token": access_token}
        if refresh_token:
            tokens["refresh_token"] = refresh_token
        save_credentials(self._db, self._organization_id, "outlook", tokens)

    def _request(self, method: str, url: str, *, params=None, json=None) -> httpx.Response:
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

    # -- public API -------------------------------------------------------

    def send_email(self, to, subject: str, body: str, cc=None, bcc=None, attachments=None) -> dict:
        """Send an email through the user's Outlook account via Graph.

        ``attachments`` is an optional list of ``{"filename", "content_bytes",
        "mime_type"}``.
        """
        to_list = _header_value(to).split(",") if to else []
        message = {
            "subject": subject,
            "body": {"contentType": "text", "content": body or ""},
            "toRecipients": [{"emailAddress": {"address": e.strip()}} for e in to_list if e.strip()],
        }
        cc_header = _header_value(cc)
        bcc_header = _header_value(bcc)
        if cc_header:
            message["ccRecipients"] = [
                {"emailAddress": {"address": e.strip()}} for e in cc_header.split(",") if e.strip()
            ]
        if bcc_header:
            message["bccRecipients"] = [
                {"emailAddress": {"address": e.strip()}} for e in bcc_header.split(",") if e.strip()
            ]
        files = []
        for attachment in attachments or []:
            data = attachment.get("content_bytes")
            if isinstance(data, str):
                data = data.encode("utf-8")
            files.append(
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": attachment.get("filename") or "attachment",
                    "contentType": attachment.get("mime_type") or "application/octet-stream",
                    "contentBytes": base64.b64encode(data).decode("ascii"),
                }
            )
        if files:
            message["attachments"] = files

        resp = self._request("POST", GRAPH_SEND_URL, json={"message": message})
        if resp.status_code >= 300:
            raise RuntimeError(f"Outlook send failed: {resp.status_code} {resp.text[:200]}")
        return {"id": None, "status": "sent", "provider": "outlook"}

    def list_recent_messages(self, query: str | None = None, max_results: int = 10) -> list[dict]:
        """Return recent messages, optionally filtered by a Graph $search query."""
        params = {
            "$top": int(max_results),
            "$select": "id,subject,from,receivedDateTime,bodyPreview",
        }
        if query:
            params["$search"] = f'"{query}"'
        resp = self._request("GET", GRAPH_LIST_URL, params=params)
        if resp.status_code >= 300:
            raise RuntimeError(f"Outlook list failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        items = data.get("value", [])
        if isinstance(items, str):  # Graph sometimes returns JSON as a string
            try:
                items = json.loads(items).get("value", [])
            except (ValueError, AttributeError):
                items = []
        return [
            {
                "id": item.get("id"),
                "subject": item.get("subject"),
                "from": (item.get("from") or {}).get("emailAddress", {}).get("address"),
                "received_at": item.get("receivedDateTime"),
            }
            for item in items
        ]
