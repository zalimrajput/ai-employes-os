"""Tests for the external integration clients (Zoho/Xero/Drive/Sheets/OneDrive),
the S3/R2 cloud storage backend, and the integration AI tools.

All provider HTTP calls are mocked — no live API calls.
"""
import sys
import uuid

sys.path.insert(0, ".")

import pytest


class FakeResp:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else str(payload)

    def json(self):
        return self._payload


def _org(db):
    from app.models.organization import Organization

    org = Organization(name="Ext Org", slug=f"ext-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _teardown(db, org):
    from sqlalchemy import text

    for stmt in (
        "DELETE FROM leads WHERE organization_id = :id",
        "DELETE FROM customers WHERE organization_id = :id",
        "DELETE FROM invoices WHERE organization_id = :id",
        "DELETE FROM invoice_items WHERE organization_id = :id",
        "DELETE FROM integrations WHERE organization_id = :id",
        "DELETE FROM organizations WHERE id = :id",
    ):
        db.execute(text(stmt), {"id": org.id})
    db.commit()


# ── Zoho client ─────────────────────────────────────────────


def test_zoho_create_lead_success(monkeypatch):
    from app.integrations.zoho.client import ZohoCRMClient

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        return FakeResp(200, {"data": [{"id": "zlead-1", "Status": "Lead Contacted"}]})

    monkeypatch.setattr("app.integrations.zoho.client.httpx.request", fake_request)
    client = ZohoCRMClient(db=None, organization_id="org", access_token="tok")
    result = client.create_lead(
        last_name="Smith", first_name="John", company="Acme", email="john@acme.com"
    )
    assert result["created"] is True
    assert result["lead_id"] == "zlead-1"
    method, url, payload = calls[0]
    assert method == "POST" and url.endswith("/crm/v2/Leads")
    assert payload["data"][0]["Last_Name"] == "Smith"
    assert payload["data"][0]["First_Name"] == "John"


def test_zoho_create_customer_success(monkeypatch):
    from app.integrations.zoho.client import ZohoCRMClient

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        return FakeResp(200, {"data": [{"id": "zcontact-1", "Last_Name": "Acme"}]})

    monkeypatch.setattr("app.integrations.zoho.client.httpx.request", fake_request)
    client = ZohoCRMClient(db=None, organization_id="org", access_token="tok")
    result = client.create_customer(
        name="Acme Corp", company="Acme", email="john@acme.com", phone="555"
    )
    assert result["created"] is True
    assert result["contact_id"] == "zcontact-1"
    method, url, payload = calls[0]
    assert method == "POST" and url.endswith("/crm/v2/Contacts")
    assert payload["data"][0]["First_Name"] == "Acme"
    assert payload["data"][0]["Last_Name"] == "Corp"
    assert payload["data"][0]["Account_Name"] == "Acme"


def test_zoho_create_customer_single_word_name(monkeypatch):
    from app.integrations.zoho.client import ZohoCRMClient

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(kwargs.get("json"))
        return FakeResp(200, {"data": [{"id": "zc2"}]})

    monkeypatch.setattr("app.integrations.zoho.client.httpx.request", fake_request)
    client = ZohoCRMClient(db=None, organization_id="org", access_token="tok")
    client.create_customer(name="Acme")
    assert calls[0]["data"][0] == {"Last_Name": "Acme"}


def test_zoho_refresh_then_retry(monkeypatch):
    from app.integrations.zoho.client import ZohoCRMClient

    responses = [
        FakeResp(401, text="expired"),
        FakeResp(200, {"data": [{"id": "z2"}]}),
    ]

    def fake_request(method, url, **kwargs):
        return responses.pop(0)

    def fake_post(url, **kwargs):
        assert kwargs["data"]["grant_type"] == "refresh_token"
        return FakeResp(200, {"access_token": "new"})

    monkeypatch.setattr("app.integrations.zoho.client.httpx.request", fake_request)
    monkeypatch.setattr("app.integrations.zoho.client.httpx.post", fake_post)
    client = ZohoCRMClient(
        db=None, organization_id="org", access_token="old", refresh_token="rt",
        client_id="cid", client_secret="cs",
    )
    client._persist = lambda *a, **k: None  # no DB in unit test
    result = client.list_leads(limit=5)
    assert result[0]["lead_id"] == "z2"
    assert client._access_token == "new"


# ── Xero client ─────────────────────────────────────────────


def test_xero_create_invoice_success(monkeypatch):
    from app.integrations.xero.client import XeroClient, XERO_CONNECTIONS_URL

    def fake_request(method, url, **kwargs):
        if url == XERO_CONNECTIONS_URL:
            return FakeResp(200, [{"tenantId": "t1", "tenantName": "Acme Co"}])
        assert kwargs["json"]["Type"] == "ACCREC"
        assert kwargs["headers"]["Xero-Tenant-Id"] == "t1"
        return FakeResp(
            200,
            {
                "Invoices": [
                    {
                        "InvoiceID": "x1",
                        "InvoiceNumber": "INV-1",
                        "Status": "AUTHORISED",
                        "Total": 120.0,
                    }
                ]
            },
        )

    monkeypatch.setattr("app.integrations.xero.client.httpx.request", fake_request)
    client = XeroClient(db=None, organization_id="org", access_token="tok")
    result = client.create_invoice(
        invoice_number="INV-1", contact_name="Acme", amount=120.0
    )
    assert result["created"] is True
    assert result["invoice_id"] == "x1"
    assert client._tenant_id == "t1"


def test_xero_resolves_tenant_from_connections(monkeypatch):
    """The tenant id is fetched once and reused — never sent on connections."""
    from app.integrations.xero.client import XeroClient, XERO_CONNECTIONS_URL

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((url, kwargs.get("headers", {})))
        if url == XERO_CONNECTIONS_URL:
            return FakeResp(200, [{"tenantId": "t9"}])
        return FakeResp(200, {"Invoices": []})

    monkeypatch.setattr("app.integrations.xero.client.httpx.request", fake_request)
    client = XeroClient(db=None, organization_id="org", access_token="tok")
    client.list_invoices(limit=1)
    client.list_invoices(limit=1)  # second call must reuse the cached tenant
    assert calls[0][0] == XERO_CONNECTIONS_URL
    assert calls[1][0].endswith("/Invoices")
    assert calls[1][1]["Xero-Tenant-Id"] == "t9"
    assert calls[2][0].endswith("/Invoices")  # no second connections call


def test_xero_refresh_uses_basic_auth(monkeypatch):
    from app.integrations.xero.client import XeroClient

    responses = [FakeResp(401, text="expired"), FakeResp(200, {"Invoices": []})]

    def fake_request(method, url, **kwargs):
        return responses.pop(0)

    def fake_post(url, **kwargs):
        auth = kwargs.get("auth")
        assert auth == ("cid", "cs"), "Xero refresh must use HTTP Basic auth"
        return FakeResp(200, {"access_token": "new"})

    monkeypatch.setattr("app.integrations.xero.client.httpx.request", fake_request)
    monkeypatch.setattr("app.integrations.xero.client.httpx.post", fake_post)
    client = XeroClient(
        db=None, organization_id="org", access_token="old", refresh_token="rt",
        client_id="cid", client_secret="cs",
    )
    client._persist = lambda *a, **k: None  # no DB in unit test
    client._tenant_id = "t1"  # skip tenant resolution in this unit test
    client.list_invoices(limit=1)
    assert client._access_token == "new"


# ── Google Drive client ─────────────────────────────────────


def test_drive_upload_multipart(monkeypatch):
    from app.integrations.google_drive.client import GoogleDriveClient

    def fake_request(method, url, **kwargs):
        assert method == "POST"
        assert kwargs["params"]["uploadType"] == "multipart"
        assert kwargs["files"], "must send multipart metadata + file"
        return FakeResp(200, {"id": "d1", "name": "note.txt", "webViewLink": "https://drive"})

    monkeypatch.setattr("app.integrations.google_drive.client.httpx.request", fake_request)
    client = GoogleDriveClient(db=None, organization_id="org", access_token="tok")
    result = client.upload_file(filename="note.txt", content_bytes=b"hi")
    assert result["uploaded"] is True
    assert result["file_id"] == "d1"


# ── Google Sheets client ────────────────────────────────────


def test_sheets_append_row(monkeypatch):
    from app.integrations.google_sheets.client import GoogleSheetsClient

    def fake_request(method, url, **kwargs):
        assert method == "POST"
        assert kwargs["json"]["values"] == [["a", "b"]]
        return FakeResp(200, {"updates": {"updatedRange": "Sheet1!A1:B1", "updatedRows": 1}})

    monkeypatch.setattr("app.integrations.google_sheets.client.httpx.request", fake_request)
    client = GoogleSheetsClient(db=None, organization_id="org", access_token="tok")
    result = client.append_row(spreadsheet_id="sp1", values=["a", "b"])
    assert result["appended"] is True
    assert result["updated_rows"] == 1


# ── OneDrive client ─────────────────────────────────────────


def test_onedrive_upload_and_excel(monkeypatch):
    from app.integrations.onedrive.client import OneDriveClient

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        if method == "PUT":
            return FakeResp(200, {"id": "f1", "name": "x.txt", "webUrl": "https://od"})
        return FakeResp(200, {"value": [{"id": "t1", "name": "Table1"}]})

    monkeypatch.setattr("app.integrations.onedrive.client.httpx.request", fake_request)
    client = OneDriveClient(db=None, organization_id="org", access_token="tok")
    up = client.upload_file(path="Reports/x.txt", content_bytes=b"hi", mime_type="text/plain")
    assert up["uploaded"] is True
    ex = client.append_excel_rows(path="Reports/book.xlsx", values=["1", "2"])
    assert ex["appended"] is True
    assert calls[0][0] == "PUT" and calls[1][0] == "POST"


# ── Slack -----------------------------------------------------------------


def test_slack_client_post_message(monkeypatch):
    from app.integrations.slack.client import SlackClient

    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        captured["json"] = kwargs.get("json")
        return FakeResp(200, {"ok": True, "ts": "111", "channel": "C123"})

    monkeypatch.setattr("app.integrations.slack.client.httpx.post", fake_post)
    client = SlackClient(access_token="xoxb-tok")
    result = client.post_message(channel="#general", text="hi")
    assert result["ok"] is True
    assert captured["url"] == "https://slack.com/api/chat.postMessage"
    assert captured["headers"]["Authorization"] == "Bearer xoxb-tok"
    assert captured["json"] == {"channel": "#general", "text": "hi"}


def test_slack_client_api_error_raises(monkeypatch):
    from app.integrations.slack.client import SlackClient, SlackError

    monkeypatch.setattr(
        "app.integrations.slack.client.httpx.post",
        lambda *a, **k: FakeResp(200, {"ok": False, "error": "not_in_channel"}),
    )
    client = SlackClient(access_token="x")
    with pytest.raises(SlackError):
        client.post_message(text="hi")


def test_slack_token_exchange_omits_grant_type(monkeypatch):
    import asyncio

    from app.core.config import settings
    import app.services.integration_service as svc

    monkeypatch.setattr(settings, "SLACK_CLIENT_ID", "sid")
    monkeypatch.setattr(settings, "SLACK_CLIENT_SECRET", "ssec")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", "gid")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_SECRET", "gsec")

    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"ok": True, "access_token": "x"}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["data"] = kwargs.get("data") or {}
            return FakeResp()

    monkeypatch.setattr(svc.httpx, "AsyncClient", lambda *a, **k: FakeClient())

    asyncio.run(svc.exchange_code("slack", "c1"))
    assert captured["url"] == "https://slack.com/api/oauth.v2.access"
    assert "grant_type" not in captured["data"], "Slack must not receive grant_type"
    assert captured["data"]["code"] == "c1"

    asyncio.run(svc.exchange_code("gmail", "c2"))
    assert "grant_type" in captured["data"], "Google requires grant_type"


def test_slack_service_post_message_none_when_not_connected(db, monkeypatch):
    from app.core.config import settings
    from app.integrations.slack.service import post_message

    # No connected integration and no global bot token configured.
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", None)
    org = _org(db)
    try:
        assert post_message(db, org.id, "hi") is None
    finally:
        _teardown(db, org)


def test_slack_service_post_message_falls_back_to_bot_token(db, monkeypatch):
    from app.core.config import settings
    from app.integrations.slack.service import post_message

    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-bot-token")
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        captured["json"] = kwargs.get("json")
        return FakeResp(200, {"ok": True, "ts": "999", "channel": "C1"})

    monkeypatch.setattr("app.integrations.slack.client.httpx.post", fake_post)
    org = _org(db)  # no connected slack integration row
    try:
        result = post_message(db, org.id, "invoice paid", channel="#finance")
        assert result["ok"] is True
        assert captured["headers"]["Authorization"] == "Bearer xoxb-bot-token"
        assert captured["json"]["channel"] == "#finance"
    finally:
        _teardown(db, org)


def test_slack_tool_posts_when_connected(db, monkeypatch):
    from app.ai.tools.integration_tools import INTEGRATION_TOOLS

    org = _org(db)
    try:
        class FakeSlack:
            def post_message(self, **kwargs):
                return {"ok": True, "ts": "123", "channel": "general"}

        monkeypatch.setattr(
            "app.integrations.slack.service.get_client",
            lambda db_, oid, channel=None: FakeSlack(),
        )
        result = INTEGRATION_TOOLS["slack_post_message"].handler(
            db, org.id, None, {"text": "hello", "channel": "general"}
        )
        assert result["posted"] is True
        assert result["ts"] == "123"
    finally:
        _teardown(db, org)


def test_slack_tool_without_connection_returns_error(db, monkeypatch):
    from app.ai.tools.integration_tools import INTEGRATION_TOOLS
    from app.core.config import settings
    from app.integrations.gmail.client import IntegrationNotConnectedError

    # No connected integration and no global bot token configured.
    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", None)
    org = _org(db)
    try:
        def raise_not_connected(db_, oid, channel=None):
            raise IntegrationNotConnectedError("not connected")

        monkeypatch.setattr(
            "app.integrations.slack.service.get_client", raise_not_connected
        )
        result = INTEGRATION_TOOLS["slack_post_message"].handler(
            db, org.id, None, {"text": "hi"}
        )
        assert "error" in result
    finally:
        _teardown(db, org)


def test_slack_tool_falls_back_to_bot_token(db, monkeypatch):
    from app.ai.tools.integration_tools import INTEGRATION_TOOLS
    from app.core.config import settings
    from app.integrations.gmail.client import IntegrationNotConnectedError

    monkeypatch.setattr(settings, "SLACK_BOT_TOKEN", "xoxb-bot-token")
    captured = {}

    def fake_post(url, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return FakeResp(200, {"ok": True, "ts": "321", "channel": "C2"})

    monkeypatch.setattr("app.integrations.slack.client.httpx.post", fake_post)

    def raise_not_connected(db_, oid, channel=None):
        raise IntegrationNotConnectedError("not connected")

    monkeypatch.setattr(
        "app.integrations.slack.service.get_client", raise_not_connected
    )
    org = _org(db)
    try:
        result = INTEGRATION_TOOLS["slack_post_message"].handler(
            db, org.id, None, {"text": "hello"}
        )
        assert result["posted"] is True
        assert result["ts"] == "321"
        assert captured["headers"]["Authorization"] == "Bearer xoxb-bot-token"
    finally:
        _teardown(db, org)


# ── Cloud storage (SigV4) ───────────────────────────────────


def test_cloud_storage_put_object_signs_request(monkeypatch):
    from app.integrations.cloud_storage import CloudStorageClient

    captured = {}

    def fake_put(url, content=None, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers or {}
        return FakeResp(200, {})

    monkeypatch.setattr("app.integrations.cloud_storage.httpx.put", fake_put)
    client = CloudStorageClient(
        endpoint_url="https://acct.r2.cloudflarestorage.com",
        access_key_id="AK",
        secret_access_key="SK",
        bucket="mybucket",
        region="auto",
    )
    url = client.put_object("org1/docs/invoice.pdf", b"%PDF-1.4", "application/pdf")
    assert url == "https://acct.r2.cloudflarestorage.com/mybucket/org1/docs/invoice.pdf"
    auth = captured["headers"]["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=AK/")
    assert "SignedHeaders=" in auth and "Signature=" in auth
    assert len(captured["headers"]["x-amz-content-sha256"]) == 64


def test_cloud_storage_put_failure_raises(monkeypatch):
    from app.integrations.cloud_storage import CloudStorageClient, CloudStorageError

    monkeypatch.setattr(
        "app.integrations.cloud_storage.httpx.put",
        lambda *a, **k: FakeResp(403, text="forbidden"),
    )
    client = CloudStorageClient(
        endpoint_url="https://x.com", access_key_id="AK", secret_access_key="SK",
        bucket="b",
    )
    with pytest.raises(CloudStorageError):
        client.put_object("k", b"data")


# ── OAuth registry / authorize URL behaviors ───────────────


def test_build_authorize_url_offline_params_by_provider(monkeypatch):
    from app.core.config import settings
    from app.services.integration_service import build_authorize_url

    # Deterministic regardless of the dev .env: force the client ids.
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", "gcid")
    monkeypatch.setattr(settings, "ZOHO_CLIENT_ID", "zcid")
    monkeypatch.setattr(settings, "XERO_CLIENT_ID", "xcid")

    # Google + Zoho send access_type=offline (needed for refresh tokens).
    url = build_authorize_url("gmail", "s1")
    assert "access_type=offline" in url and "prompt=consent" in url
    url = build_authorize_url("zoho", "s3")
    assert "access_type=offline" in url

    # Xero / Slack / Microsoft handle offline via scope — extra params rejected.
    url = build_authorize_url("xero", "s2")
    assert "access_type" not in url and "prompt" not in url


def test_xero_provider_uses_basic_token_auth(monkeypatch):
    from app.core.config import settings
    from app.services.integration_service import get_provider_config

    monkeypatch.setattr(settings, "XERO_CLIENT_ID", "xcid")
    monkeypatch.setattr(settings, "ZOHO_CLIENT_ID", "zcid")

    cfg = get_provider_config("xero")
    assert cfg is not None
    assert cfg["token_auth"] == "basic"
    assert get_provider_config("zoho")["token_auth"] == "form"


# ── AI tools (with connected/unconnected clients) ──────────


def test_zoho_create_lead_tool_syncs_when_connected(db, monkeypatch):
    from app.ai.tools.integration_tools import INTEGRATION_TOOLS
    from app.integrations.zoho.client import ZohoCRMClient

    org = _org(db)
    try:
        class FakeZoho:
            def create_lead(self, **kwargs):
                return {"created": True, "lead_id": "z-999", "status": "new"}

        monkeypatch.setattr(
            "app.integrations.zoho.service.get_client", lambda db_, oid: FakeZoho()
        )
        result = INTEGRATION_TOOLS["zoho_create_lead"].handler(
            db, org.id, None, {"last_name": "Smith", "first_name": "John", "email": "j@x.co"}
        )
        assert result["synced_to"] == "internal+zoho"
        assert result["zoho"]["lead_id"] == "z-999"
        from app.models.lead import Lead

        lead = db.query(Lead).filter(Lead.organization_id == org.id).first()
        assert lead is not None and lead.name == "John Smith"
    finally:
        _teardown(db, org)


def test_zoho_create_lead_tool_without_connection_still_saves(db, monkeypatch):
    from app.ai.tools.integration_tools import INTEGRATION_TOOLS
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.models.lead import Lead

    org = _org(db)
    try:

        def raise_not_connected(db_, oid):
            raise IntegrationNotConnectedError("not connected")

        monkeypatch.setattr(
            "app.integrations.zoho.service.get_client", raise_not_connected
        )
        result = INTEGRATION_TOOLS["zoho_create_lead"].handler(
            db, org.id, None, {"last_name": "Brown"}
        )
        assert result["synced_to"] == "internal"
        assert "error" in result["zoho"]
        assert db.query(Lead).filter(Lead.organization_id == org.id).count() == 1
    finally:
        _teardown(db, org)


def test_zoho_create_customer_tool_syncs_when_connected(db, monkeypatch):
    from app.ai.tools.integration_tools import INTEGRATION_TOOLS
    from app.models.customer import Customer

    org = _org(db)
    try:
        class FakeZoho:
            def create_customer(self, **kwargs):
                return {"created": True, "contact_id": "zc-777", "Last_Name": kwargs["name"]}

        monkeypatch.setattr(
            "app.integrations.zoho.service.get_client", lambda db_, oid: FakeZoho()
        )
        result = INTEGRATION_TOOLS["zoho_create_customer"].handler(
            db,
            org.id,
            None,
            {"name": "Acme Corp", "email": "john@acme.io", "company": "Acme"},
        )
        assert result["synced_to"] == "internal+zoho"
        assert result["zoho"]["contact_id"] == "zc-777"
        customer = db.query(Customer).filter(Customer.organization_id == org.id).first()
        assert customer is not None
        assert customer.name == "Acme Corp"
        assert customer.email == "john@acme.io"
    finally:
        _teardown(db, org)


def test_zoho_create_customer_tool_without_connection_still_saves(db, monkeypatch):
    from app.ai.tools.integration_tools import INTEGRATION_TOOLS
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.models.customer import Customer

    org = _org(db)
    try:

        def raise_not_connected(db_, oid):
            raise IntegrationNotConnectedError("not connected")

        monkeypatch.setattr(
            "app.integrations.zoho.service.get_client", raise_not_connected
        )
        result = INTEGRATION_TOOLS["zoho_create_customer"].handler(
            db, org.id, None, {"name": "GlobalTech"}
        )
        assert result["synced_to"] == "internal"
        assert "error" in result["zoho"]
        assert db.query(Customer).filter(Customer.organization_id == org.id).count() == 1
    finally:
        _teardown(db, org)


def test_zoho_create_customer_tool_requires_name(db):
    from app.ai.tools.integration_tools import INTEGRATION_TOOLS

    org = _org(db)
    try:
        result = INTEGRATION_TOOLS["zoho_create_customer"].handler(
            db, org.id, None, {"email": "x@y.co"}
        )
        assert result.get("error")
    finally:
        _teardown(db, org)


def test_xero_create_invoice_tool_syncs_when_connected(db, monkeypatch):
    from app.ai.tools.integration_tools import INTEGRATION_TOOLS
    from app.models.invoice import Invoice

    org = _org(db)
    try:
        class FakeXero:
            def create_invoice(self, **kwargs):
                return {"created": True, "invoice_id": "x-1", "status": "AUTHORISED"}

        monkeypatch.setattr(
            "app.integrations.xero.service.get_client", lambda db_, oid: FakeXero()
        )
        result = INTEGRATION_TOOLS["xero_create_invoice"].handler(
            db, org.id, None, {"invoice_number": "INV-1", "amount": 250.0}
        )
        assert result["xero"]["invoice_id"] == "x-1"
        assert db.query(Invoice).filter(Invoice.organization_id == org.id).count() == 1
    finally:
        _teardown(db, org)


def test_tools_registered_and_allowlisted():
    from app.ai.guardrails import _SAFE_TOOL_NAMES, validate_tool_call
    from app.ai.tools import ALL_TOOLS

    for name in (
        "zoho_create_lead",
        "zoho_create_customer",
        "zoho_list_leads",
        "xero_create_invoice",
        "xero_list_invoices",
        "sheets_append_row",
        "drive_upload_file",
        "onedrive_upload_file",
        "onedrive_append_excel",
        "slack_post_message",
    ):
        assert name in ALL_TOOLS, name
        assert name in _SAFE_TOOL_NAMES, name
        assert validate_tool_call(name, {})
