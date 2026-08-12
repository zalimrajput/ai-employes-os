"""Google Calendar REST API client built on stored OAuth credentials.

Mirrors ``app/integrations/gmail/client.py``: tokens are decrypted with
``app.utils.encryption.decrypt_value``, calls go straight to the Google
Calendar v3 API via httpx, and a 401 triggers a refresh-token exchange that
persists the new token and retries once. The exception contract
(``IntegrationAuthError`` / ``IntegrationNotConnectedError``) is shared with
the Gmail client so callers can handle both integrations the same way.
"""

from datetime import datetime, timezone

import httpx

from app.integrations.gmail.client import (  # noqa: F401  (shared error contract)
    IntegrationAuthError,
    IntegrationNotConnectedError,
)

GOOGLE_CAL_EVENTS_URL = (
    "https://www.googleapis.com/calendar/v3/calendars/primary/events"
)
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _to_iso(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class GoogleCalendarClient:
    """Minimal Google Calendar client with automatic token refresh."""

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

    # -- internal helpers -------------------------------------------------

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _refresh(self) -> None:
        if not (self._refresh_token and self._client_id and self._client_secret):
            raise IntegrationAuthError(
                "Google Calendar access token expired and no refresh "
                "credentials are available"
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
                f"Google Calendar token refresh failed: {resp.status_code} {resp.text[:200]}"
            )
        payload = resp.json()
        new_access = payload.get("access_token")
        if not new_access:
            raise IntegrationAuthError(
                "Google Calendar token refresh returned no access_token"
            )
        self._access_token = new_access
        if payload.get("refresh_token"):
            self._refresh_token = payload["refresh_token"]
        self._persist(new_access, payload.get("refresh_token"))

    def _persist(self, access_token: str, refresh_token: str | None) -> None:
        from app.services.integration_service import save_credentials

        tokens = {"access_token": access_token}
        if refresh_token:
            tokens["refresh_token"] = refresh_token
        save_credentials(self._db, self._organization_id, "google-calendar", tokens)

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

    def create_event(
        self,
        title: str,
        start_time,
        end_time,
        attendees=None,
        description: str | None = None,
    ) -> dict:
        """Create an event on the primary calendar."""
        payload = {
            "summary": title,
            "description": description,
            "start": {"dateTime": _to_iso(start_time)},
            "end": {"dateTime": _to_iso(end_time)},
        }
        emails = [
            a for a in (attendees or []) if isinstance(a, str)
        ]
        if emails:
            payload["attendees"] = [{"email": email} for email in emails]

        resp = self._request("POST", GOOGLE_CAL_EVENTS_URL, json=payload)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Google Calendar create failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return {
            "event_id": data.get("id"),
            "html_link": data.get("htmlLink"),
        }

    def list_upcoming_events(self, max_results: int = 10) -> list[dict]:
        """Return the next upcoming events on the primary calendar."""
        # "now" is rejected by the API (400 badRequest) — send a real ISO
        # timestamp so the call only returns upcoming events.
        params = {
            "maxResults": int(max_results),
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": datetime.now(timezone.utc).isoformat(),
        }
        resp = self._request("GET", GOOGLE_CAL_EVENTS_URL, params=params)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Google Calendar list failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return [
            {
                "event_id": item.get("id"),
                "html_link": item.get("htmlLink"),
                "summary": item.get("summary"),
            }
            for item in data.get("items", [])
        ]
