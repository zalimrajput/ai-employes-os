"""email_worker tests: send_email_task now goes through GmailClient."""
import sys

sys.path.insert(0, ".")

from unittest.mock import MagicMock

from workers.email_worker import send_email_task


class _FakeClient:
    def __init__(self):
        self.calls = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "sent"}


def test_send_email_task_uses_gmail_client(monkeypatch):
    fake = _FakeClient()

    def fake_get_client(db, organization_id):
        return fake

    monkeypatch.setattr(
        "app.integrations.gmail.service.get_client", fake_get_client
    )

    result = send_email_task(
        "org-123", "a@b.com", "Hello", "Body", thread_id=None
    )

    assert result == {"queued": True, "delivered": True, "provider": "gmail"}
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["to"] == "a@b.com"
    assert call["subject"] == "Hello"
    assert call["body"] == "Body"


def test_send_email_task_not_connected_handled(monkeypatch):
    from app.integrations.gmail.client import IntegrationNotConnectedError

    def raise_not_connected(db, organization_id):
        raise IntegrationNotConnectedError("no connection")

    # The worker falls through Gmail -> Outlook -> Microsoft 365; mock all three.
    for module in (
        "app.integrations.gmail.service",
        "app.integrations.outlook.service",
        "app.integrations.microsoft365.service",
    ):
        monkeypatch.setattr(module + ".get_client", raise_not_connected)

    result = send_email_task(
        "org_id", "a@b.com", "Hello", "Body", thread_id=None
    )
    assert result == {"queued": True, "delivered": False, "reason": "no integration"}


def test_send_email_task_falls_back_to_outlook(monkeypatch):
    """When Gmail isn't connected, the worker tries the Outlook client."""
    from app.integrations.gmail.client import IntegrationNotConnectedError

    fake = _FakeClient()

    def not_connected(db, organization_id):
        raise IntegrationNotConnectedError("no connection")

    def fake_outlook(db, organization_id):
        return fake

    monkeypatch.setattr("app.integrations.gmail.service.get_client", not_connected)
    monkeypatch.setattr(
        "app.integrations.outlook.service.get_client", fake_outlook
    )

    result = send_email_task(
        "org-456", "a@b.com", "Hello", "Body", thread_id=None
    )
    assert result == {"queued": True, "delivered": True, "provider": "outlook"}
    assert len(fake.calls) == 1
    assert fake.calls[0]["subject"] == "Hello"