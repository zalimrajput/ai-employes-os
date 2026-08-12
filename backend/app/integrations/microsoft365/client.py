"""Microsoft 365 client built on stored OAuth credentials.

Mirrors the Outlook client: encrypted tokens are decrypted, calls go to the
Microsoft Graph API via httpx, and a 401 triggers a refresh-token exchange that
persists the new token and retries once. Covers mail (send/list), calendar
(create/list events) and tasks (create/list) using the Microsoft 365 Graph
scopes configured for the ``microsoft365`` provider.
"""
import httpx

from app.integrations.gmail.client import (  # noqa: F401  (shared error contract)
    IntegrationAuthError,
    IntegrationNotConnectedError,
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
ME_URL = f"{GRAPH_BASE}/me"
SEND_MAIL_URL = f"{ME_URL}/sendMail"
LIST_MAIL_URL = f"{ME_URL}/messages"
CAL_EVENTS_URL = f"{ME_URL}/calendar/events"
TASKS_URL = f"{ME_URL}/todo/lists"
OAUTH_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


class Microsoft365Client:
    """Minimal Microsoft Graph client (mail + calendar + tasks)."""

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
                "Microsoft 365 access token expired and no refresh credentials are available"
            )
        resp = httpx.post(
            self._token_url,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
                "scope": self._scope or "https://graph.microsoft.com/Mail.ReadWrite Calendars.ReadWrite Tasks.ReadWrite",
            },
            timeout=30,
        )
        if resp.status_code >= 300:
            raise IntegrationAuthError(
                f"Microsoft 365 token refresh failed: {resp.status_code} {resp.text[:200]}"
            )
        payload = resp.json()
        new_access = payload.get("access_token")
        if not new_access:
            raise IntegrationAuthError(
                "Microsoft 365 token refresh returned no access_token"
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
        save_credentials(self._db, self._organization_id, "microsoft365", tokens)

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

    # -- mail -------------------------------------------------------------

    def send_email(self, to, subject: str, body: str, cc=None, bcc=None, attachments=None) -> dict:
        """Send an email through the user's Microsoft 365 mailbox via Graph."""
        to_list = [e.strip() for e in (", ".join(to) if isinstance(to, (list, tuple)) else str(to)).split(",") if e.strip()]
        message = {
            "subject": subject,
            "body": {"contentType": "text", "content": body or ""},
            "toRecipients": [{"emailAddress": {"address": e}} for e in to_list],
        }
        cc_header = ", ".join(cc) if isinstance(cc, (list, tuple)) else cc
        bcc_header = ", ".join(bcc) if isinstance(bcc, (list, tuple)) else bcc
        if cc_header:
            message["ccRecipients"] = [
                {"emailAddress": {"address": e.strip()}} for e in cc_header.split(",") if e.strip()
            ]
        if bcc_header:
            message["bccRecipients"] = [
                {"emailAddress": {"address": e.strip()}} for e in bcc_header.split(",") if e.strip()
            ]
        import base64

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

        resp = self._request("POST", SEND_MAIL_URL, json={"message": message})
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Microsoft 365 send failed: {resp.status_code} {resp.text[:200]}"
            )
        return {"id": None, "status": "sent", "provider": "microsoft365"}

    def list_recent_messages(self, query: str | None = None, max_results: int = 10) -> list[dict]:
        params = {
            "$top": int(max_results),
            "$select": "id,subject,from,receivedDateTime,bodyPreview",
        }
        if query:
            params["$search"] = f'"{query}"'
        resp = self._request("GET", LIST_MAIL_URL, params=params)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Microsoft 365 list failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return [
            {
                "id": item.get("id"),
                "subject": item.get("subject"),
                "from": (item.get("from") or {}).get("emailAddress", {}).get("address"),
                "received_at": item.get("receivedDateTime"),
            }
            for item in data.get("value", [])
        ]

    # -- calendar ---------------------------------------------------------

    def create_event(self, title: str, start_time, end_time, attendees=None, description: str | None = None) -> dict:
        """Create an event on the user's default calendar."""
        payload = {
            "subject": title,
            "body": {"contentType": "text", "content": description or ""},
            "start": {"dateTime": start_time.isoformat() if hasattr(start_time, "isoformat") else str(start_time), "timeZone": "UTC"},
            "end": {"dateTime": end_time.isoformat() if hasattr(end_time, "isoformat") else str(end_time), "timeZone": "UTC"},
        }
        emails = [a for a in (attendees or []) if isinstance(a, str)]
        if emails:
            payload["attendees"] = [
                {"emailAddress": {"address": e}, "type": "required"} for e in emails
            ]
        resp = self._request("POST", CAL_EVENTS_URL, json=payload)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Microsoft 365 calendar create failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return {"event_id": data.get("id"), "html_link": data.get("webLink")}

    def list_upcoming_events(self, max_results: int = 10) -> list[dict]:
        params = {
            "$top": int(max_results),
            "$orderby": "start/dateTime",
            "$select": "id,subject,start,webLink",
        }
        resp = self._request("GET", CAL_EVENTS_URL, params=params)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Microsoft 365 calendar list failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return [
            {
                "event_id": item.get("id"),
                "subject": item.get("subject"),
                "html_link": item.get("webLink"),
                "start": (item.get("start") or {}).get("dateTime"),
            }
            for item in data.get("value", [])
        ]

    # -- tasks ------------------------------------------------------------

    def create_task(self, title: str, due_date=None, importance: str = "normal") -> dict:
        """Create a task in the user's default To-Do list."""
        resp = self._request("GET", TASKS_URL, params={"$top": 1, "$select": "id"})
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Microsoft 365 todo lists failed: {resp.status_code} {resp.text[:200]}"
            )
        lists = resp.json().get("value", [])
        if not lists:
            raise RuntimeError("No Microsoft 365 To-Do list available")
        payload = {"title": title, "importance": importance}
        if due_date:
            payload["dueDateTime"] = {
                "dateTime": due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date),
                "timeZone": "UTC",
            }
        url = f"{TASKS_URL}/{lists[0]['id']}/tasks"
        resp = self._request("POST", url, json=payload)
        if resp.status_code >= 300:
            raise RuntimeError(
                f"Microsoft 365 task create failed: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
        return {"task_id": data.get("id"), "title": data.get("title")}
