"""Google Sheets client built on stored OAuth credentials (spreadsheets scope).

Create spreadsheets, read a range, and append rows. On a 401 the refresh
token is exchanged and the request retried once.
"""
import httpx

from app.integrations.gmail.client import (  # noqa: F401  (shared error contract)
    IntegrationAuthError,
    IntegrationNotConnectedError,
)

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"


class GoogleSheetsClient:
    """Minimal Google Sheets API client with automatic token refresh."""

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
                "Google Sheets access token expired and no refresh credentials are available"
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
        save_credentials(self._db, self._organization_id, "google-sheets", tokens)

    def _request(self, method: str, url: str, *, params=None, json=None) -> httpx.Response:
        resp = httpx.request(
            method,
            url,
            headers=self._headers(),
            params=params,
            json=json,
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
                timeout=60,
            )
        return resp

    # -- public API -------------------------------------------------------

    def create_spreadsheet(self, title: str) -> dict:
        """Create a new spreadsheet and return its id + URL."""
        resp = self._request(
            "POST", SHEETS_API, json={"properties": {"title": title}}
        )
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Google Sheets create failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return {
            "created": True,
            "spreadsheet_id": data.get("spreadsheetId"),
            "url": data.get("spreadsheetUrl"),
        }

    def append_row(
        self,
        *,
        spreadsheet_id: str,
        values: list,
        range_name: str = "A1",
    ) -> dict:
        """Append one row of values to a spreadsheet."""
        resp = self._request(
            "POST",
            f"{SHEETS_API}/{spreadsheet_id}/values/{range_name}:append",
            params={"valueInputOption": "RAW"},
            json={"values": [values]},
        )
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Google Sheets append failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return {
            "appended": True,
            "range": data.get("updates", {}).get("updatedRange"),
            "updated_rows": data.get("updates", {}).get("updatedRows", 0),
        }

    def read_sheet(self, spreadsheet_id: str, range_name: str = "A1:Z100") -> list[list]:
        """Read values from a spreadsheet range (list of rows)."""
        resp = self._request(
            "GET", f"{SHEETS_API}/{spreadsheet_id}/values/{range_name}"
        )
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Google Sheets read failed: {resp.status_code} {resp.text[:200]}"
            )
        return resp.json().get("values") or []
