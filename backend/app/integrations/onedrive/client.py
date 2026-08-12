"""Microsoft OneDrive / Excel client built on stored OAuth credentials.

Uses the Microsoft Graph API (Files.ReadWrite scope): upload files, list a
folder, and append rows to an Excel workbook's table. On a 401 the refresh
token is exchanged and the request retried once.
"""
import httpx

from app.integrations.gmail.client import (  # noqa: F401  (shared error contract)
    IntegrationAuthError,
    IntegrationNotConnectedError,
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0/me/drive"
OAUTH_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


class OneDriveClient:
    """Minimal Microsoft Graph client (OneDrive files + Excel tables)."""

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

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _refresh(self) -> None:
        if not (self._refresh_token and self._client_id and self._client_secret):
            raise IntegrationAuthError(
                "OneDrive access token expired and no refresh credentials are available"
            )
        resp = httpx.post(
            self._token_url,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
                "scope": self._scope or "Files.ReadWrite offline_access",
            },
            timeout=30,
        )
        if resp.status_code >= 300:
            raise IntegrationAuthError(
                f"OneDrive token refresh failed: {resp.status_code} {resp.text[:200]}"
            )
        payload = resp.json()
        new_access = payload.get("access_token")
        if not new_access:
            raise IntegrationAuthError("OneDrive token refresh returned no access_token")
        self._access_token = new_access
        if payload.get("refresh_token"):
            self._refresh_token = payload["refresh_token"]
        self._persist(new_access, payload.get("refresh_token"))

    def _persist(self, access_token: str, refresh_token: str | None) -> None:
        from app.services.integration_service import save_credentials

        tokens = {"access_token": access_token}
        if refresh_token:
            tokens["refresh_token"] = refresh_token
        save_credentials(self._db, self._organization_id, "onedrive", tokens)

    def _request(self, method: str, url: str, *, params=None, json=None, content=None, headers=None) -> httpx.Response:
        req_headers = self._headers()
        if headers:
            req_headers = {**req_headers, **headers}
        resp = httpx.request(
            method,
            url,
            headers=req_headers,
            params=params,
            json=json,
            content=content,
            timeout=60,
        )
        if resp.status_code == 401:
            self._refresh()
            resp = httpx.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json,
                content=content,
                timeout=60,
            )
        return resp

    @staticmethod
    def _raise(resp: httpx.Response, action: str) -> None:
        if resp.status_code >= 300:
            raise RuntimeError(
                f"OneDrive {action} failed: {resp.status_code} {resp.text[:200]}"
            )

    # -- public API -------------------------------------------------------

    def upload_file(
        self,
        *,
        path: str,
        content_bytes: bytes,
        mime_type: str = "application/octet-stream",
    ) -> dict:
        """Upload (or overwrite) a file at the given OneDrive path."""
        url = f"{GRAPH_BASE}/root:/{path}:/content"
        resp = self._request(
            "PUT", url, content=content_bytes, headers={"Content-Type": mime_type}
        )
        self._raise(resp, "upload")
        data = resp.json()
        return {
            "uploaded": True,
            "file_id": data.get("id"),
            "name": data.get("name"),
            "web_url": data.get("webUrl"),
            "size": data.get("size"),
        }

    def list_files(self, folder: str = "", limit: int = 25) -> list[dict]:
        """List files in a OneDrive folder (root when folder is empty)."""
        url = f"{GRAPH_BASE}/root:/{folder}:/children" if folder else f"{GRAPH_BASE}/root/children"
        resp = self._request("GET", url, params={"$top": int(limit or 25)})
        self._raise(resp, "list")
        data = resp.json()
        return [
            {
                "file_id": item.get("id"),
                "name": item.get("name"),
                "size": item.get("size"),
                "web_url": item.get("webUrl"),
            }
            for item in data.get("value") or []
        ]

    def append_excel_rows(
        self,
        *,
        path: str,
        values: list,
        table: str = "Table1",
    ) -> dict:
        """Append a row to a named table inside an Excel workbook on OneDrive.

        ``path`` is the workbook path, e.g. \"Reports/leads.xlsx\".
        """
        url = f"{GRAPH_BASE}/root:/{path}:/workbook/tables/{table}/rows/add"
        resp = self._request("POST", url, json={"values": [values]})
        self._raise(resp, "excel append")
        return {"appended": True, "table": table, "path": path}
