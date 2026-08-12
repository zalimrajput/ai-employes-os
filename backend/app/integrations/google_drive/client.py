"""Google Drive client built on stored OAuth credentials (drive.file scope).

Uploads and lists files the user has opened/created with this app. On a 401
the refresh token is exchanged and the request retried once.
"""
import json

import httpx

from app.integrations.gmail.client import (  # noqa: F401  (shared error contract)
    IntegrationAuthError,
    IntegrationNotConnectedError,
)

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"


class GoogleDriveClient:
    """Minimal Google Drive API client with automatic token refresh."""

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
    ):
        self._db = db
        self._organization_id = organization_id
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _refresh(self) -> None:
        if not (self._refresh_token and self._client_id and self._client_secret):
            raise IntegrationAuthError(
                "Google Drive access token expired and no refresh credentials are available"
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
                f"Google token refresh failed: {resp.status_code} {resp.text[:200]}"
            )
        payload = resp.json()
        new_access = payload.get("access_token")
        if not new_access:
            raise IntegrationAuthError("Google token refresh returned no access_token")
        self._access_token = new_access
        self._persist(new_access, payload.get("refresh_token"))

    def _persist(self, access_token: str, refresh_token: str | None) -> None:
        from app.services.integration_service import save_credentials

        tokens = {"access_token": access_token}
        if refresh_token:
            tokens["refresh_token"] = refresh_token
        save_credentials(self._db, self._organization_id, "google-drive", tokens)

    def _request(self, method: str, url: str, *, params=None, json=None, files=None) -> httpx.Response:
        resp = httpx.request(
            method,
            url,
            headers=self._headers(),
            params=params,
            json=json,
            files=files,
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
                files=files,
                timeout=60,
            )
        return resp

    # -- public API -------------------------------------------------------

    def upload_file(
        self,
        *,
        filename: str,
        content_bytes: bytes,
        mime_type: str = "application/octet-stream",
        description: str | None = None,
    ) -> dict:
        """Upload a file to the user's Drive (app-created files)."""
        metadata = {"name": filename}
        if description:
            metadata["description"] = description
        files = [
            ("metadata", (None, json.dumps(metadata), "application/json; charset=UTF-8")),
            ("file", (filename, content_bytes, mime_type)),
        ]
        resp = self._request("POST", DRIVE_UPLOAD, params={"uploadType": "multipart"}, files=files)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Google Drive upload failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return {
            "uploaded": True,
            "file_id": data.get("id"),
            "name": data.get("name"),
            "web_view_link": data.get("webViewLink"),
        }

    def list_files(self, limit: int = 25) -> list[dict]:
        """List files visible to the app."""
        resp = self._request(
            "GET",
            DRIVE_API,
            params={"pageSize": int(limit or 25), "fields": "files(id,name,mimeType,webViewLink)"},
        )
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Google Drive list failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return [
            {
                "file_id": f.get("id"),
                "name": f.get("name"),
                "mime_type": f.get("mimeType"),
                "web_view_link": f.get("webViewLink"),
            }
            for f in data.get("files") or []
        ]
