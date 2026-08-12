"""Integration OAuth routes: redirect-URI correctness + callback behavior.

Regression guard for the bug where config redirect URIs pointed at
non-existent callback paths (``/api/v1/integrations/gmail/callback``) instead
of the real route (``/api/v1/integrations/oauth/callback/{provider}``) — which
made every provider OAuth flow 404 after consent. Also covers the callback
redirect back to the frontend and the token-safe status endpoint.
"""
import sys
import uuid

sys.path.insert(0, ".")

import pytest

from sqlalchemy import text

# provider -> settings attribute that holds its redirect URI.
REDIRECT_ATTRS = {
    "gmail": "GMAIL_REDIRECT_URI",
    "google-calendar": "GOOGLE_CAL_REDIRECT_URI",
    "google-drive": "GOOGLE_DRIVE_REDIRECT_URI",
    "google-sheets": "GOOGLE_SHEETS_REDIRECT_URI",
    "outlook": "OUTLOOK_REDIRECT_URI",
    "microsoft365": "MICROSOFT_REDIRECT_URI",
    "onedrive": "ONEDRIVE_REDIRECT_URI",
    "slack": "SLACK_REDIRECT_URI",
    "zoho": "ZOHO_REDIRECT_URI",
    "xero": "XERO_REDIRECT_URI",
}

# provider -> the single shared callback path its redirect URI must end with.
FAMILY_PATH = {
    "google": ("gmail", "google-calendar", "google-drive", "google-sheets"),
    "microsoft": ("outlook", "microsoft365", "onedrive"),
    "slack": "slack",
    "zoho": "zoho",
    "xero": "xero",
}


def _expected_callback_path(provider: str) -> str:
    for family, members in FAMILY_PATH.items():
        if isinstance(members, tuple) and provider in members:
            return f"/api/v1/integrations/oauth/callback/{family}"
        if provider == members:
            return f"/api/v1/integrations/oauth/callback/{provider}"
    raise AssertionError(f"no expected path for {provider}")


def test_redirect_uri_paths_match_real_routes():
    """Every configured redirect URI must point at a real callback route.

    Google-family providers share /oauth/callback/google and Microsoft-family
    providers share /oauth/callback/microsoft; standalone providers keep their
    own path. The provider itself rides inside the OAuth state token.
    """
    from app.core.config import settings

    for provider, attr in REDIRECT_ATTRS.items():
        uri = getattr(settings, attr)
        assert uri, f"{attr} must have a default redirect URI"
        assert _expected_callback_path(provider) in uri, (
            f"{attr}={uri} does not point at the family callback route "
            f"(expected ...{_expected_callback_path(provider)})"
        )


def test_oauth_providers_registered():
    from app.services.integration_service import OAUTH_PROVIDERS

    assert set(OAUTH_PROVIDERS) == set(REDIRECT_ATTRS)


def test_family_callback_resolves_provider_from_state(db, monkeypatch):
    """A shared /oauth/callback/google hit must exchange for the provider
    encoded in the state token (e.g. google-drive), not 'google'. The org in
    the state must exist in the database."""
    import app.api.v1.integrations.routes as routes_module
    from app.models.organization import Organization

    org = Organization(name="Callback Org", slug=f"cb-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)

    captured = {}

    async def fake_exchange(provider, code):
        captured["provider"] = provider
        return {"access_token": "at", "refresh_token": "rt"}

    def fake_save(db_, org_id, provider, tokens):
        captured["saved_provider"] = provider
        return type("R", (), {"id": "x"})()

    monkeypatch.setattr(routes_module, "exchange_code", fake_exchange)
    monkeypatch.setattr(routes_module, "save_credentials", fake_save)

    from fastapi.testclient import TestClient
    from app.main import app

    try:
        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/integrations/oauth/callback/google",
                params={
                    "code": "c1",
                    "state": f"{org.id}:google-drive:random123",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "provider=google-drive" in resp.headers["location"]
        assert captured["provider"] == "google-drive"
        assert captured["saved_provider"] == "google-drive"
    finally:
        db.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org.id})
        db.commit()


def test_family_callback_rejects_state_with_unknown_provider(db, monkeypatch):
    """A family callback with a state that doesn't name a family member must
    bounce back flagged as an error, never crash."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/integrations/oauth/callback/microsoft",
            params={"code": "c1", "state": f"{uuid.uuid4()}:not-a-member:r"},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert "status=error" in resp.headers["location"]


def test_oauth_start_rejects_unconfigured_provider(db, monkeypatch):
    """Without client credentials in env, connect must 400 with a clear message."""
    from app.core.auth import get_current_user
    from app.core.config import settings
    from app.main import app
    from app.models.organization import Organization
    from app.models.user import User

    # Deterministic regardless of what the dev .env has: force gmail unconfigured.
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", None)

    org = Organization(name="OAuth Org", slug=f"oa-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)
    user = User(full_name="Tester", email="t@t.co", organization_id=org.id)
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: {"sub": str(user.id)}
    try:
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            resp = client.get("/api/v1/integrations/oauth/connect/gmail")
        assert resp.status_code == 400
        assert "not configured" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
        for stmt in (
            "DELETE FROM users WHERE id = :id",
            "DELETE FROM organizations WHERE id = :id",
        ):
            db.execute(text(stmt), {"id": user.id if "users" in stmt else org.id})
        db.commit()


def test_integration_status_returns_provider_rows(db, monkeypatch):
    """Status endpoint returns every provider with configured/connected flags
    and never any tokens."""
    from app.core.auth import get_current_user
    from app.main import app
    from app.models.organization import Organization
    from app.models.user import User

    org = Organization(name="Status Org", slug=f"st-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)
    user = User(full_name="Tester", email="s@t.co", organization_id=org.id)
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: {"sub": str(user.id)}
    try:
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            resp = client.get("/api/v1/integrations/status")
        assert resp.status_code == 200
        rows = resp.json()
        # OAuth providers + the env-key providers (whatsapp/stripe/r2).
        assert len(rows) == len(REDIRECT_ATTRS) + 3
        by_provider = {r["provider"]: r for r in rows}
        for provider in (*REDIRECT_ATTRS, "whatsapp", "stripe", "r2"):
            assert provider in by_provider
            keys = set(by_provider[provider])
            # base keys always present; only whatsapp may add phone_number_id
            # (the org's own number id, not a credential) — never tokens
            assert {"provider", "configured", "connected"} <= keys
            assert keys <= {"provider", "configured", "connected", "phone_number_id"}
    finally:
        app.dependency_overrides.clear()
        for stmt in (
            "DELETE FROM users WHERE id = :id",
            "DELETE FROM organizations WHERE id = :id",
        ):
            db.execute(text(stmt), {"id": user.id if "users" in stmt else org.id})
        db.commit()


def test_key_check_persists_connected_flag(db, monkeypatch):
    """A successful env-key check must write the connected flag into the
    integrations table so /integrations/status keeps reporting Connected after
    a page refresh (the OAuth providers already behave this way). A subsequent
    failed check flips the flag back off."""
    import httpx as httpx_module

    from app.core.auth import get_current_user
    from app.core.config import settings
    from app.main import app
    from app.models.integration import Integration
    from app.models.organization import Organization
    from app.models.user import User

    org = Organization(name="Key Org", slug=f"ky-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)
    user = User(full_name="Tester", email="k@t.co", organization_id=org.id)
    db.add(user)
    db.commit()
    db.refresh(user)

    # Force whatsapp configured + fake Meta's Graph API response.
    monkeypatch.setattr(settings, "WHATSAPP_API_TOKEN", "tok")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_ID", "123")

    class FakeResp:
        status_code = 200
        text = "{}"

    monkeypatch.setattr(httpx_module, "get", lambda *a, **k: FakeResp())

    app.dependency_overrides[get_current_user] = lambda: {"sub": str(user.id)}
    try:
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            resp = client.get("/api/v1/integrations/check/whatsapp")
        assert resp.status_code == 200
        assert resp.json()["connected"] is True

        row = (
            db.query(Integration)
            .filter(
                Integration.organization_id == org.id,
                Integration.provider == "whatsapp",
            )
            .first()
        )
        assert row is not None and row.connected is True

        # A fresh status fetch (what a page refresh triggers) shows Connected.
        with TestClient(app) as client:
            status_resp = client.get("/api/v1/integrations/status")
        by_provider = {r["provider"]: r for r in status_resp.json()}
        assert by_provider["whatsapp"]["connected"] is True

        # A failed check later flips the flag back off.
        class BadResp:
            status_code = 401
            text = "expired"

        monkeypatch.setattr(httpx_module, "get", lambda *a, **k: BadResp())
        with TestClient(app) as client:
            resp2 = client.get("/api/v1/integrations/check/whatsapp")
        assert resp2.json()["connected"] is False
        db.expire_all()
        row2 = (
            db.query(Integration)
            .filter(
                Integration.organization_id == org.id,
                Integration.provider == "whatsapp",
            )
            .first()
        )
        assert row2 is not None and row2.connected is False
    finally:
        app.dependency_overrides.clear()
        for stmt in (
            "DELETE FROM users WHERE id = :id",
            "DELETE FROM organizations WHERE id = :id",
        ):
            db.execute(text(stmt), {"id": user.id if "users" in stmt else org.id})
        db.commit()


def test_save_credentials_preserves_refresh_token_when_omitted(db):
    """save_credentials must keep the stored refresh token when the payload
    lacks one — provider refresh responses routinely omit it, and blanking it
    would lock the integration out of future refreshes (regression)."""
    from app.models.integration import Integration
    from app.models.organization import Organization
    from app.services.integration_service import save_credentials
    from app.utils.encryption import decrypt_value

    org = Organization(name="Tok Org", slug=f"tk-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)
    try:
        # Initial OAuth write stores both tokens.
        row = save_credentials(db, org.id, "gmail", {"access_token": "at1", "refresh_token": "rt1"})
        assert decrypt_value(row.refresh_token) == "rt1"

        # Access-token rotation: payload omits the refresh token — keep rt1.
        save_credentials(db, org.id, "gmail", {"access_token": "at2"})
        db.expire_all()
        row2 = (
            db.query(Integration)
            .filter(Integration.organization_id == org.id, Integration.provider == "gmail")
            .first()
        )
        assert decrypt_value(row2.access_token) == "at2"
        assert decrypt_value(row2.refresh_token) == "rt1"

        # An explicit new refresh token (re-connect) replaces the old one.
        save_credentials(db, org.id, "gmail", {"access_token": "at3", "refresh_token": "rt3"})
        db.expire_all()
        row3 = (
            db.query(Integration)
            .filter(Integration.organization_id == org.id, Integration.provider == "gmail")
            .first()
        )
        assert decrypt_value(row3.refresh_token) == "rt3"
    finally:
        db.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org.id})
        db.commit()


def test_oauth_callback_redirects_to_frontend_on_success(db, monkeypatch):
    """After exchanging the code, the browser bounces back to the frontend
    settings page with status=connected."""
    import app.api.v1.integrations.routes as routes_module
    from app.models.organization import Organization

    org = Organization(name="Gmail Org", slug=f"gm-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)

    captured = {}

    async def fake_exchange(provider, code):
        captured["provider"] = provider
        captured["code"] = code
        return {"access_token": "at", "refresh_token": "rt"}

    def fake_save(db_, org_id, provider, tokens):
        captured["org_id"] = str(org_id)
        captured["tokens"] = tokens
        return type("R", (), {"id": uuid.uuid4()})()

    monkeypatch.setattr(routes_module, "exchange_code", fake_exchange)
    monkeypatch.setattr(routes_module, "save_credentials", fake_save)

    from fastapi.testclient import TestClient
    from app.main import app

    try:
        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/integrations/oauth/callback/gmail",
                params={"code": "the-code", "state": f"{org.id}:random-state"},
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert resp.headers["location"].startswith(
            "http://localhost:3000/dashboard/settings?"
        )
        assert "tab=integrations" in resp.headers["location"]
        assert "status=connected" in resp.headers["location"]
        assert "provider=gmail" in resp.headers["location"]
        assert captured["provider"] == "gmail"
        assert captured["code"] == "the-code"
        assert captured["org_id"] == str(org.id)
        assert captured["tokens"]["access_token"] == "at"
    finally:
        db.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org.id})
        db.commit()


def test_oauth_callback_rejects_unknown_org(db, monkeypatch):
    """A state token naming a valid-UUID but nonexistent organization must
    bounce with an error redirect — never reach the code exchange or crash on
    the foreign-key insert (regression: a forged state used to 500)."""
    import app.api.v1.integrations.routes as routes_module

    async def fake_exchange(provider, code):
        raise AssertionError("exchange_code must not run for an unknown org")

    def fake_save(db_, org_id, provider, tokens):
        raise AssertionError("save_credentials must not run for an unknown org")

    monkeypatch.setattr(routes_module, "exchange_code", fake_exchange)
    monkeypatch.setattr(routes_module, "save_credentials", fake_save)

    from fastapi.testclient import TestClient
    from app.main import app

    fake_org_id = uuid.uuid4()  # well-formed UUID, but no such organization
    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/integrations/oauth/callback/slack",
            params={"code": "c1", "state": f"{fake_org_id}:slack:r"},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert "status=error" in resp.headers["location"]
    assert "provider=slack" in resp.headers["location"]
    assert "error_description=" in resp.headers["location"]


def test_oauth_callback_handles_credential_save_failure(db, monkeypatch):
    """If storing the exchanged tokens trips a foreign-key/integrity error
    (e.g. the org was deleted mid-flight), the callback must bounce with an
    error redirect and roll back — never a raw 500."""
    import app.api.v1.integrations.routes as routes_module
    from sqlalchemy.exc import IntegrityError

    from app.models.organization import Organization

    org = Organization(name="Fail Org", slug=f"fl-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)

    async def fake_exchange(provider, code):
        return {"access_token": "at", "refresh_token": "rt"}

    def failing_save(db_, org_id, provider, tokens):
        raise IntegrityError("INSERT ...", {}, Exception("foreign key violation"))

    monkeypatch.setattr(routes_module, "exchange_code", fake_exchange)
    monkeypatch.setattr(routes_module, "save_credentials", failing_save)

    from fastapi.testclient import TestClient
    from app.main import app

    try:
        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/integrations/oauth/callback/gmail",
                params={"code": "c1", "state": f"{org.id}:random-state"},
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "status=error" in resp.headers["location"]
        assert "provider=gmail" in resp.headers["location"]
    finally:
        db.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org.id})
        db.commit()


def test_oauth_callback_rejects_malformed_state_org(db, monkeypatch):
    """A state whose org segment isn't a UUID must bounce with an error
    redirect — never a 500 (regression: ``invalid input syntax for type uuid``
    crashed the Slack/Zoho callbacks on malformed or forged state)."""
    import app.api.v1.integrations.routes as routes_module

    async def fake_exchange(provider, code):
        return {"access_token": "at", "refresh_token": "rt"}

    monkeypatch.setattr(routes_module, "exchange_code", fake_exchange)

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/integrations/oauth/callback/slack",
            params={"code": "c1", "state": "not-a-uuid:slack:r"},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert "status=error" in resp.headers["location"]


def test_exchange_code_detects_provider_error_body(monkeypatch):
    """Slack returns HTTP 200 with {"ok": false} on failures; Zoho may return
    200 with an error field. Both must raise instead of returning a garbage
    token payload that later crashes the callback."""
    import asyncio

    import httpx

    import app.services.integration_service as svc
    from app.core.config import settings

    class FakeResp:
        status_code = 200
        text = '{"ok": false, "error": "invalid_code"}'

        def json(self):
            return {"ok": False, "error": "invalid_code"}

    class FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, **kwargs):
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    # Deterministic regardless of dev .env: force slack configured.
    monkeypatch.setattr(settings, "SLACK_CLIENT_ID", "slack-test-id")
    monkeypatch.setattr(settings, "SLACK_CLIENT_SECRET", "slack-test-secret")

    with pytest.raises(RuntimeError, match="token exchange failed"):
        asyncio.run(svc.exchange_code("slack", "bad-code"))


def test_oauth_callback_redirects_error_when_exchange_fails(db, monkeypatch):
    """A failed code exchange must still land the user back on the frontend,
    flagged as an error — never a raw 5xx page."""
    import app.api.v1.integrations.routes as routes_module

    async def failing_exchange(provider, code):
        raise RuntimeError("bad code")

    monkeypatch.setattr(routes_module, "exchange_code", failing_exchange)

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/integrations/oauth/callback/slack",
            params={"code": "bad", "state": f"{uuid.uuid4()}:s"},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert "status=error" in resp.headers["location"]
    assert "provider=slack" in resp.headers["location"]


def _auth_user(db, admin=False):
    """Create an org + user and override auth; returns (org, user, teardown fn).

    The trg_seed_default_roles DB trigger already seeds the org's default
    roles (incl. Company Admin) on INSERT — reuse that row instead of
    inserting a duplicate."""
    from app.core.auth import get_current_user
    from app.main import app
    from app.models.organization import Organization
    from app.models.role import Role
    from app.models.user import User
    from app.models.user_role import UserRole

    db.rollback()  # clear any failed-transaction state from a prior test
    org = Organization(name="Guard Org", slug=f"gu-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)
    user = User(full_name="Tester", email=f"gu-{uuid.uuid4().hex[:6]}@t.co", organization_id=org.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    if admin:
        role = (
            db.query(Role)
            .filter(Role.organization_id == org.id, Role.name == "Company Admin")
            .first()
        )
        if role is None:
            role = Role(organization_id=org.id, name="Company Admin")
            db.add(role)
            db.commit()
            db.refresh(role)
        db.add(UserRole(user_id=user.id, role_id=role.id, organization_id=org.id))
        db.commit()

    app.dependency_overrides[get_current_user] = lambda: {"sub": str(user.id)}

    def teardown():
        from app.main import app as _app

        _app.dependency_overrides.clear()
        for stmt in (
            "DELETE FROM user_roles WHERE organization_id = :id",
            "DELETE FROM roles WHERE organization_id = :id",
            "DELETE FROM users WHERE organization_id = :id",
            "DELETE FROM organizations WHERE id = :id",
        ):
            db.execute(text(stmt), {"id": org.id})
        db.commit()

    return org, user, teardown


def test_generic_integration_post_rejected(db):
    """POST /api/v1/integrations/ must refuse to store credentials — a dummy
    key with connected=true can never land in the table through the generic
    endpoint (only the provider-verified flows may write credentials)."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.integration import Integration

    org, _, teardown = _auth_user(db)
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/integrations/",
                json={
                    "provider": "stripe",
                    "access_token": "sk_test_dummy",
                    "connected": True,
                },
            )
        assert resp.status_code == 400
        assert "validated" in resp.json()["detail"].lower()
        assert (
            db.query(Integration)
            .filter(
                Integration.organization_id == org.id,
                Integration.provider == "stripe",
            )
            .first()
            is None
        )
    finally:
        teardown()


def test_generic_integration_patch_rejects_credential_writes(db):
    """PATCH /api/v1/integrations/{id} must reject any change to
    access_token / refresh_token / connected with a 400 (they are only set
    after live verification), while metadata-only updates still work."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.integration import Integration

    org, _, teardown = _auth_user(db, admin=True)
    try:
        row = Integration(
            organization_id=org.id,
            provider="gmail",
            access_token="encrypted-at",
            connected=False,
            metadata_json={"kind": "oauth"},
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        with TestClient(app) as client:
            resp = client.patch(
                f"/api/v1/integrations/{row.id}",
                json={"connected": True, "access_token": "sk_live_dummy"},
            )
        assert resp.status_code == 400
        assert "live provider verification" in resp.json()["detail"]

        db.expire_all()
        untouched = db.query(Integration).filter(Integration.id == row.id).first()
        assert untouched.connected is False
        assert untouched.access_token == "encrypted-at"

        # metadata-only updates remain allowed for org admins.
        with TestClient(app) as client:
            ok = client.patch(
                f"/api/v1/integrations/{row.id}",
                json={"metadata": {"kind": "oauth", "label": "work"}},
            )
        assert ok.status_code == 200
        db.expire_all()
        updated = db.query(Integration).filter(Integration.id == row.id).first()
        assert updated.metadata_json.get("label") == "work"
    finally:
        teardown()


def test_generic_integration_list_never_leaks_tokens(db):
    """The generic integration list is org-scoped and must never serialize
    access/refresh tokens — only the /status endpoint is meant for the UI."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.integration import Integration

    org, _, teardown = _auth_user(db)
    try:
        row = Integration(
            organization_id=org.id,
            provider="slack",
            access_token="encrypted-at",
            refresh_token="encrypted-rt",
            connected=True,
        )
        db.add(row)
        db.commit()

        with TestClient(app) as client:
            resp = client.get("/api/v1/integrations/")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["provider"] == "slack"
        assert rows[0]["connected"] is True
        assert "access_token" not in rows[0]
        assert "refresh_token" not in rows[0]
    finally:
        teardown()


def test_generic_integration_delete_org_scoped(db):
    """DELETE on an integration row is org-scoped: another org's row is
    invisible (404), the caller's own row is removed for org admins."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.integration import Integration
    from app.models.organization import Organization

    org, _, teardown = _auth_user(db, admin=True)
    other = Organization(name="Other Org", slug=f"oo-{uuid.uuid4().hex[:10]}", settings={})
    db.add(other)
    db.commit()
    db.refresh(other)
    try:
        mine = Integration(organization_id=org.id, provider="zoho", connected=False)
        theirs = Integration(organization_id=other.id, provider="xero", connected=False)
        db.add_all([mine, theirs])
        db.commit()
        db.refresh(mine)
        db.refresh(theirs)

        with TestClient(app) as client:
            # Foreign org row: org-scoped query sees nothing -> 404.
            resp_foreign = client.delete(f"/api/v1/integrations/{theirs.id}")
            # Own row: deleted.
            resp_own = client.delete(f"/api/v1/integrations/{mine.id}")
        assert resp_foreign.status_code == 404
        assert resp_own.status_code == 200
        assert resp_own.json()["deleted"] is True
        assert db.query(Integration).filter(Integration.id == theirs.id).first() is not None
        assert db.query(Integration).filter(Integration.id == mine.id).first() is None
    finally:
        teardown()
