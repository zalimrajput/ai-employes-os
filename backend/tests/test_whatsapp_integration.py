"""WhatsApp Business Cloud API integration tests.

The Meta Graph API is always mocked (no real Facebook calls) so the webhook
flow, org resolution and send/download logic stay deterministic.  Webhook
handler functions are called directly with a real DB session like the rest of
the API tests.
"""
import sys
import uuid

sys.path.insert(0, ".")

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.api.v1.whatsapp.routes import (
    receive_webhook,
    router,
    verify_webhook,
)


class FakeResp:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else (str(payload) if payload else "")

    def json(self):
        return self._payload


class _Empty:
    def filter(self, *a, **k):
        return self

    def all(self):
        return []

    def first(self):
        return None


class _FakeDB:
    def query(self, model):
        return _Empty()


def _org(db):
    from app.models.organization import Organization

    org = Organization(
        name="WhatsApp Test Org",
        slug=f"whatsapp-{uuid.uuid4().hex[:10]}",
        settings={},
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _teardown(db, org):
    deletes = [
        "DELETE FROM ai_messages WHERE organization_id = :id",
        "DELETE FROM ai_conversations WHERE organization_id = :id",
        "DELETE FROM whatsapp_messages WHERE organization_id = :id",
        "DELETE FROM whatsapp_contacts WHERE organization_id = :id",
        "DELETE FROM users WHERE organization_id = :id",
        "DELETE FROM integrations WHERE organization_id = :id",
        "DELETE FROM organizations WHERE id = :id",
    ]
    for statement in deletes:
        db.execute(text(statement), {"id": org.id})
    db.commit()


def _integration(db, org, *, phone_number_id, connected=True):
    from app.models.integration import Integration
    from app.utils.encryption import encrypt_value

    row = Integration(
        organization_id=org.id,
        provider="whatsapp",
        connected=connected,
        access_token=encrypt_value("meta-app-token"),
        metadata_json={"phone_number_id": phone_number_id},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _webhook_payload(
    phone_number_id, phone_number="15550000001", body="Hello", contacts=True
):
    value = {
        "messaging_product": "whatsapp",
        "metadata": {
            "display_phone_number": "15551231234",
            "phone_number_id": phone_number_id,
        },
        "messages": [
            {
                "from": phone_number,
                "id": f"wamid.{uuid.uuid4().hex}",
                "timestamp": "1700000000",
                "type": "text",
                "text": {"body": body},
            }
        ],
        "contacts": (
            [{"profile": {"name": "John"}, "wa_id": phone_number}]
            if contacts
            else []
        ),
    }
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-1",
                "changes": [{"field": "messages", "value": value}],
            }
        ],
    }


class _FakeClient:
    def __init__(self, sent=None):
        self.sent = [] if sent is None else sent

    def send_text(self, to, message):
        self.sent.append({"to": to, "message": message})
        return {"id": "wamid.out", "status": "sent"}


def test_webhook_verify_success(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.whatsapp.routes.settings.WHATSAPP_VERIFY_TOKEN", "my-verify-token"
    )
    resp = verify_webhook(
        mode="subscribe",
        verify_token="my-verify-token",
        challenge="CHALLENGE-123",
    )
    assert resp.status_code == 200
    assert resp.body.decode() == "CHALLENGE-123"


def test_webhook_verify_rejects_bad_token(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.whatsapp.routes.settings.WHATSAPP_VERIFY_TOKEN", "my-verify-token"
    )
    with pytest.raises(HTTPException) as excinfo:
        verify_webhook(mode="subscribe", verify_token="nope", challenge="x")
    assert excinfo.value.status_code == 403


@pytest.mark.db
def test_webhook_processes_inbound_text(db, monkeypatch):
    org = _org(db)
    # Unique phone_number_id per test: resolution must never collide with a
    # leftover integration row from a previous (possibly killed) run, which
    # would route the webhook into the wrong org.
    pnid = f"105{uuid.uuid4().hex[:9]}"
    _integration(db, org, phone_number_id=pnid)
    captured = {}

    def fake_execute_turn(db_, organization_id, user_id, conversation, user_message,
                          employee=None, history_messages=None, model=None, temperature=0.3):
        captured["org"] = organization_id
        captured["conversation"] = conversation
        captured["user_message"] = user_message
        return "Thanks! I've noted that you asked about pricing.", "sales"

    monkeypatch.setattr(
        "app.ai.orchestrator.execute_turn", fake_execute_turn
    )
    fake_client = _FakeClient()

    def fake_get_client(db, organization_id, *, phone_number_id=None):
        return fake_client

    monkeypatch.setattr(
        "app.api.v1.whatsapp.routes.get_client", fake_get_client
    )

    try:
        result = receive_webhook(_webhook_payload(phone_number_id=pnid), db)
        assert result["processed"] == 1
        assert result["errors"] == []

        from app.models.ai_conversation import AIConversation
        from app.models.ai_message import AIMessage
        from app.models.whatsapp import WhatsAppContact, WhatsAppMessage

        contact = (
            db.query(WhatsAppContact)
            .filter(WhatsAppContact.organization_id == org.id)
            .first()
        )
        assert contact is not None
        assert contact.phone == "15550000001"
        assert contact.name == "John"

        messages = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.organization_id == org.id)
            .order_by(WhatsAppMessage.created_at)
            .all()
        )
        assert len(messages) == 2
        assert messages[0].direction == "inbound"
        assert messages[0].ai_generated is False
        assert messages[0].message == "Hello"
        assert messages[1].direction == "outgoing"
        assert messages[1].ai_generated is True

        # AI turn was routed through the orchestrator entry point
        assert captured["user_message"] == "Hello"
        assert captured["org"] == org.id

        # AI messages persisted scoped to the org
        ai_msgs = (
            db.query(AIMessage)
            .filter(
                AIMessage.organization_id == org.id,
                AIMessage.conversation_id.in_(
                    db.query(AIConversation.id).filter(
                        AIConversation.organization_id == org.id
                    )
                ),
            )
            .order_by(AIMessage.created_at)
            .all()
        )
        assert len(ai_msgs) == 2

        # reply actually forwarded to the WhatsApp Cloud API
        assert len(fake_client.sent) == 1
        assert fake_client.sent[0]["to"] == "15550000001"
    finally:
        _teardown(db, org)


@pytest.mark.db
@pytest.mark.db
def test_resolve_picks_deterministically_when_phone_is_claimed_twice(db):
    """Two orgs claiming the same phone number resolve to one stable org.

    Guards against the flakiness this file historically suffered from: a
    leftover integration row (from a killed run) must never flip which org
    receives the webhook between calls or runs.
    """
    from app.integrations.whatsapp.service import resolve_organization_id

    org_a = _org(db)
    org_b = _org(db)
    pnid = f"105{uuid.uuid4().hex[:9]}"
    _integration(db, org_a, phone_number_id=pnid)
    _integration(db, org_b, phone_number_id=pnid)
    try:
        first = resolve_organization_id(db, pnid)
        second = resolve_organization_id(db, pnid)
        assert first is not None
        assert first == second  # stable across calls
        assert str(first) in {str(org_a.id), str(org_b.id)}
    finally:
        _teardown(db, org_a)
        _teardown(db, org_b)


@pytest.mark.db
def test_webhook_without_integration_is_dropped(db):
    """A phone number with no connected integration is ignored (no leak)."""
    org = _org(db)

    def unexpected(*args, **kwargs):
        raise AssertionError("no AI turn when the org is not resolvable")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.ai.orchestrator.execute_turn", unexpected)

    try:
        # Random phone_number_id so this can never resolve to a leftover
        # integration row from a previous run (which would silently process
        # the message instead of dropping it).
        result = receive_webhook(
            _webhook_payload(phone_number_id=f"105{uuid.uuid4().hex[:9]}"), db
        )
        assert result["processed"] == 0

        from app.models.whatsapp import WhatsAppContact

        assert (
            db.query(WhatsAppContact)
            .filter(WhatsAppContact.organization_id == org.id)
            .count()
            == 0
        )
    finally:
        monkeypatch.undo()
        _teardown(db, org)


@pytest.mark.db
def test_webhook_org_isolation(db):
    """Two tenants on different phone numbers must never cross-resolve."""
    org_a = _org(db)
    org_b = _org(db)
    _integration(db, org_a, phone_number_id="101000000000")
    _integration(db, org_b, phone_number_id="202000000000")

    try:
        # org A's number -> resolves to org A only
        from app.integrations.whatsapp.service import resolve_organization_id

        assert resolve_organization_id(db, "101000000000") == org_a.id
        assert resolve_organization_id(db, "202000000000") == org_b.id
        assert resolve_organization_id(db, "999999999999") is None
    finally:
        _teardown(db, org_a)
        _teardown(db, org_b)


def test_whatsapp_routes_registered():
    paths = [r.path for r in router.routes]
    assert "/whatsapp/webhook" in paths
    assert "/whatsapp/webhook" in paths
    assert "/whatsapp-contacts/" in paths
    assert "/whatsapp-messages/" in paths


def test_send_text_success(monkeypatch):
    from app.integrations.whatsapp.client import WhatsAppClient

    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["json"] = kwargs["json"]
        return FakeResp(200, {"messages": [{"id": "wamid.outbound"}]})

    monkeypatch.setattr("app.integrations.whatsapp.client.httpx.post", fake_post)

    client = WhatsAppClient(
        api_token="tok",
        phone_number_id="105000000000",
    )
    result = client.send_text("+15550000001", "Hello!")
    assert result["status"] == "sent"
    assert calls["json"]["messaging_product"] == "whatsapp"
    assert calls["json"]["to"] == "+15550000001"
    assert calls["json"]["text"]["body"] == "Hello!"


def test_send_text_failure_raises(monkeypatch):
    from app.integrations.whatsapp.client import WhatsAppClient, WhatsAppError

    def fake_post(url, **kwargs):
        return FakeResp(400, {"error": {"message": "invalid token"}})

    monkeypatch.setattr("app.integrations.whatsapp.client.httpx.post", fake_post)

    client = WhatsAppClient(api_token="bad-tok", phone_number_id="105000000000")
    with pytest.raises(WhatsAppError):
        client.send_text("+1555555", "hi")


def test_download_media(monkeypatch):
    from app.integrations.whatsapp.client import WhatsAppClient

    class MediaResp:
        def __init__(self, status_code, json=None, content=None):
            self.status_code = status_code
            self._json = json
            self.content = content or b""

        def json(self):
            return self._json

    responses = [
        MediaResp(200, json={"url": "https://cdn.example/media.bin"}),
        MediaResp(200, content=b"BINARY"),
    ]

    def fake_get(url, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr("app.integrations.whatsapp.client.httpx.get", fake_get)

    client = WhatsAppClient(api_token="tok", phone_number_id="105000000000")
    data = client.download_media("media-id-1")
    assert data == b"BINARY"


def test_get_client_not_connected_raises():
    from app.integrations.whatsapp.client import WhatsAppNotConnectedError
    from app.integrations.whatsapp.service import get_client

    with pytest.raises(WhatsAppNotConnectedError):
        get_client(_FakeDB(), "org")


@pytest.mark.db
def test_get_client_resolves_org_row(db):
    from app.integrations.whatsapp.service import get_client

    org = _org(db)
    _integration(db, org, phone_number_id="105111111111")

    try:
        client = get_client(db, org.id)
        assert client._api_token == "meta-app-token"
        assert client._phone_number_id == "105111111111"
    finally:
        _teardown(db, org)


@pytest.mark.db
def test_webhook_conversation_is_reused_across_messages(db):
    monkeypatch = pytest.MonkeyPatch()

    def fake_execute_turn(db, organization_id, user_id, conversation, user_message,
                          employee=None, history_messages=None, model=None, temperature=0.3):
        return ("Reply " + user_message, None)

    monkeypatch.setattr("app.ai.orchestrator.execute_turn", fake_execute_turn)
    fake_client = _FakeClient()
    monkeypatch.setattr(
        "app.api.v1.whatsapp.routes.get_client", lambda db, org_id, *, phone_number_id=None: fake_client
    )

    org = _org(db)
    pnid = f"105{uuid.uuid4().hex[:9]}"
    _integration(db, org, phone_number_id=pnid)

    from app.models.ai_conversation import AIConversation

    try:
        receive_whatsapp = receive_webhook
        receive_whatsapp(_webhook_payload(body="first", phone_number_id=pnid), db)
        receive_whatsapp(_webhook_payload(body="second", phone_number_id=pnid), db)

        conversations = (
            db.query(AIConversation)
            .filter(AIConversation.organization_id == org.id)
            .all()
        )
        assert len(conversations) == 1  # one conversation per contact
    finally:
        _teardown(db, org)


def test_master_prompt_has_checkmark_completion_instruction():
    from app.ai.agents.master_agent import master_system_prompt

    prompt = master_system_prompt([])
    assert "checkmark" in prompt
    assert "\u2713" in prompt
    assert "completion summary" in prompt