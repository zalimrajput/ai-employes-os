"""Tests for the newly implemented Outlook / Microsoft 365 / Slack / Accounting clients.

All external calls are mocked (no real API is ever hit).
"""
import sys

sys.path.insert(0, ".")

import pytest


class FakeResp:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else str(payload)
        self.content = b"" if payload is None else str(payload).encode()

    def json(self):
        return self._payload


class _Empty:
    def filter(self, *a, **k):
        return self

    def first(self):
        return None


class _FakeDB:
    def query(self, model):
        return _Empty()

    def add(self, obj):
        return None

    def commit(self):
        return None

    def refresh(self, obj):
        return None


@pytest.fixture()
def fake_httpx(monkeypatch):
    """Route httpx.request/post to captured responses."""
    calls = []

    def _install(responses):
        def fake_request(method, url, **kwargs):
            calls.append({"method": method, "url": url, **kwargs})
            return responses.pop(0)

        def fake_post(url, **kwargs):
            calls.append({"method": "POST", "url": url, **kwargs})
            return responses.pop(0)

        monkeypatch.setattr("httpx.request", fake_request)
        monkeypatch.setattr("httpx.post", fake_post)

    return {"calls": calls, "install": _install}


# ── Outlook ────────────────────────────────────────────────────────────────
def test_outlook_send_email_builds_graph_payload(fake_httpx):
    from app.integrations.outlook.client import OutlookClient

    fake_httpx["install"]([FakeResp(202, {})])

    client = OutlookClient(
        db=_FakeDB(), organization_id="org", access_token="a",
        refresh_token="r", client_id="c", client_secret="s",
    )
    result = client.send_email(
        "john@acme.com", "Quotation", "See attached", cc=None, bcc=None,
        attachments=[{"filename": "q.pdf", "content_bytes": b"%PDF", "mime_type": "application/pdf"}],
    )
    call = fake_httpx["calls"][0]
    assert call["url"] == "https://graph.microsoft.com/v1.0/me/sendMail"
    msg = call["json"]["message"]
    assert msg["subject"] == "Quotation"
    assert msg["toRecipients"] == [{"emailAddress": {"address": "john@acme.com"}}]
    assert msg["attachments"][0]["name"] == "q.pdf"
    assert result["status"] == "sent"


def test_outlook_list_messages(fake_httpx):
    from app.integrations.outlook.client import OutlookClient

    fake_httpx["install"](
        [FakeResp(200, {"value": [{"id": "m1", "subject": "Hi", "from": {"emailAddress": {"address": "x@y.com"}}, "receivedDateTime": "2026-01-01T00:00:00Z"}]})]
    )
    client = OutlookClient(db=_FakeDB(), organization_id="org", access_token="a")
    items = client.list_recent_messages(max_results=5)
    assert items[0]["id"] == "m1"
    assert items[0]["from"] == "x@y.com"


def test_outlook_401_refreshes_once(fake_httpx):
    from app.integrations.outlook.client import OutlookClient

    fake_httpx["install"](
        [
            FakeResp(401, {}, text="expired"),
            FakeResp(200, {"access_token": "new-token"}),
            FakeResp(202, {}),
        ]
    )
    client = OutlookClient(
        db=_FakeDB(), organization_id="org", access_token="old",
        refresh_token="r", client_id="c", client_secret="s",
    )
    client.send_email("a@b.com", "S", "B")
    methods = [c["method"] for c in fake_httpx["calls"]]
    assert methods == ["POST", "POST", "POST"]
    assert fake_httpx["calls"][2]["headers"]["Authorization"] == "Bearer new-token"


# ── Microsoft 365 ──────────────────────────────────────────────────────────
def test_microsoft365_create_event_and_task(fake_httpx):
    from app.integrations.microsoft365.client import Microsoft365Client

    fake_httpx["install"](
        [
            FakeResp(201, {"id": "ev-1", "webLink": "https://outlook.office.com/ev1"}),
            FakeResp(200, {"value": [{"id": "list-1"}]}),
            FakeResp(201, {"id": "ts-1", "title": "Follow up"}),
        ]
    )
    client = Microsoft365Client(db=_FakeDB(), organization_id="org", access_token="a")
    event = client.create_event("Call", "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z", attendees=["ceo@acme.com"])
    assert event["event_id"] == "ev-1"
    task = client.create_task("Follow up", due_date="2026-01-05T00:00:00Z")
    assert task["title"] == "Follow up"
    assert "todo/lists/list-1/tasks" in fake_httpx["calls"][2]["url"]


def test_microsoft365_send_email(fake_httpx):
    from app.integrations.microsoft365.client import Microsoft365Client

    fake_httpx["install"]([FakeResp(202, {})])
    client = Microsoft365Client(db=_FakeDB(), organization_id="org", access_token="a")
    result = client.send_email(["x@y.com", "z@w.com"], "Subj", "Body")
    assert result["provider"] == "microsoft365"
    msg = fake_httpx["calls"][0]["json"]["message"]
    assert len(msg["toRecipients"]) == 2


# ── Slack ──────────────────────────────────────────────────────────────────
def test_slack_post_message(fake_httpx):
    from app.integrations.slack.client import SlackClient

    fake_httpx["install"]([FakeResp(200, {"ok": True, "ts": "123.456", "channel": "C123"})])
    client = SlackClient(access_token="xoxb-token")
    result = client.post_message("#sales", "Quotation sent ✅")
    assert result["ok"] is True
    call = fake_httpx["calls"][0]
    assert call["url"] == "https://slack.com/api/chat.postMessage"
    assert call["json"] == {"channel": "#sales", "text": "Quotation sent ✅"}


def test_slack_error_raises(fake_httpx):
    from app.integrations.slack.client import SlackClient, SlackError

    fake_httpx["install"]([FakeResp(200, {"ok": False, "error": "channel_not_found"})])
    client = SlackClient(access_token="xoxb-token")
    with pytest.raises(SlackError, match="channel_not_found"):
        client.post_message("#nowhere", "hi")


# ── Accounting ─────────────────────────────────────────────────────────────
def test_accounting_push_invoice(fake_httpx):
    from app.integrations.accounting.client import AccountingClient

    fake_httpx["install"]([FakeResp(201, {"id": "inv-9"})])
    client = AccountingClient(base_url="https://acct.example.com", api_key="k")
    result = client.push_invoice(invoice_number="INV-100", customer_name="Acme", amount=12500.0)
    assert result == {"id": "inv-9"}
    call = fake_httpx["calls"][0]
    assert call["url"] == "https://acct.example.com/invoices"
    assert call["json"]["invoice_number"] == "INV-100"
    assert call["headers"]["Authorization"] == "Bearer k"


def test_accounting_push_expense(fake_httpx):
    from app.integrations.accounting.client import AccountingClient

    fake_httpx["install"]([FakeResp(201, {"id": "exp-2"})])
    client = AccountingClient(base_url="https://acct.example.com", api_key="k")
    result = client.push_expense(description="Travel", amount=120.5)
    assert result == {"id": "exp-2"}
