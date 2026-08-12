"""Stripe payment-link / QR / webhook tests (Stripe SDK mocked; no real calls)."""
import json
import sys
import uuid

sys.path.insert(0, ".")

import pytest

from sqlalchemy import text


def _teardown(db, org):
    deletes = [
        "DELETE FROM storage_files WHERE organization_id = :id",
        "DELETE FROM storage_quotas WHERE organization_id = :id",
        "DELETE FROM quotation_items WHERE organization_id = :id",
        "DELETE FROM invoice_items WHERE organization_id = :id",
        "DELETE FROM invoices WHERE organization_id = :id",
        "DELETE FROM quotations WHERE organization_id = :id",
        "DELETE FROM reminders WHERE organization_id = :id",
        "DELETE FROM activities WHERE organization_id = :id",
        "DELETE FROM notifications WHERE organization_id = :id",
        "DELETE FROM customers WHERE organization_id = :id",
        "DELETE FROM users WHERE organization_id = :id",
        "DELETE FROM ai_employees WHERE organization_id = :id",
        "DELETE FROM organizations WHERE id = :id",
    ]
    for statement in deletes:
        db.execute(text(statement), {"id": org.id})
    db.commit()


def _org(db):
    from app.models.organization import Organization

    org = Organization(name="Stripe Org", slug=f"stripe-{uuid.uuid4().hex[:10]}", settings={})
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _invoice(db, org, status="unpaid", amount="120.00"):
    from app.models.invoice import Invoice

    inv = Invoice(
        organization_id=org.id,
        invoice_number=f"INV-S-{uuid.uuid4().hex[:6].upper()}",
        amount=amount,
        status=status,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def _mock_stripe_sdk(monkeypatch, fake_session):
    """Fake stripe.checkout.Session.create (return object has .url and .id)."""
    import types

    class FakeSession:
        url = "https://checkout.stripe.com/c/pay/cs_test_abc123"
        id = "cs_test_abc123"

    session_api = types.SimpleNamespace(create=lambda **kwargs: fake_session or FakeSession())
    monkeypatch.setattr(
        "app.integrations.stripe.client.stripe",
        types.SimpleNamespace(checkout=types.SimpleNamespace(Session=session_api)),
    )


# ----------------------------------------------------------------- tool tests


def test_generate_invoice_payment_link_success_sets_columns(db, monkeypatch):
    from app.ai.tools.invoice_tools import INVOICE_TOOLS
    from app.models.invoice import Invoice

    _mock_stripe_sdk(monkeypatch, None)
    monkeypatch.setattr(
        "app.integrations.stripe.client.settings",
        type("S", (), {"STRIPE_SECRET_KEY": "sk_test_dummy", "FRONTEND_ORIGIN": "http://localhost:3000"}),
    )

    org = _org(db)
    inv = _invoice(db, org, amount="120.00")

    try:
        result = INVOICE_TOOLS["generate_invoice_payment_link"].handler(
            db, org.id, None, {"invoice_id": str(inv.id)}
        )
        assert result["invoice_id"] == str(inv.id)
        assert result["payment_link_url"] == "https://checkout.stripe.com/c/pay/cs_test_abc123"
        assert result["qr_code_url"].startswith("/documents/payment_qr_")

        fresh = db.query(Invoice).filter(Invoice.id == inv.id).first()
        assert fresh.payment_link_url == result["payment_link_url"]
        assert fresh.qr_code_url == result["qr_code_url"]
    finally:
        _teardown(db, org)


def test_generate_invoice_payment_link_no_key_returns_error(db, monkeypatch):
    from app.ai.tools.invoice_tools import INVOICE_TOOLS

    monkeypatch.setattr(
        "app.integrations.stripe.client.settings",
        type("S", (), {"STRIPE_SECRET_KEY": None, "FRONTEND_ORIGIN": "http://localhost:3000"}),
    )

    org = _org(db)
    inv = _invoice(db, org)

    try:
        result = INVOICE_TOOLS["generate_invoice_payment_link"].handler(
            db, org.id, None, {"invoice_id": str(inv.id)}
        )
        assert "error" in result
        assert "Stripe isn't configured" in result["error"]
    finally:
        _teardown(db, org)


def test_generate_invoice_payment_link_stripe_api_error(db, monkeypatch):
    from app.ai.tools.invoice_tools import INVOICE_TOOLS

    _mock_stripe_sdk(monkeypatch, None)

    def boom(**kwargs):
        from app.integrations.stripe.client import IntegrationAuthError

        raise IntegrationAuthError("Stripe request failed: StripeError: nope")

    import types

    class FakeStripeError(Exception):
        pass

    monkeypatch.setattr(
        "app.integrations.stripe.client.stripe",
        types.SimpleNamespace(
            checkout=types.SimpleNamespace(Session=types.SimpleNamespace(create=boom)),
            error=types.SimpleNamespace(StripeError=FakeStripeError),
        ),
    )
    monkeypatch.setattr(
        "app.integrations.stripe.client.settings",
        type("S", (), {"STRIPE_SECRET_KEY": "sk_test_dummy", "FRONTEND_ORIGIN": "http://localhost:3000"}),
    )

    org = _org(db)
    inv = _invoice(db, org)

    try:
        result = INVOICE_TOOLS["generate_invoice_payment_link"].handler(
            db, org.id, None, {"invoice_id": str(inv.id)}
        )
        assert "error" in result
        assert "Stripe" in result["error"]
    finally:
        _teardown(db, org)


def test_generate_invoice_payment_link_not_found(db, monkeypatch):
    from app.ai.tools.invoice_tools import INVOICE_TOOLS

    org = _org(db)
    try:
        result = INVOICE_TOOLS["generate_invoice_payment_link"].handler(
            db, org.id, None, {"invoice_id": str(uuid.uuid4())}
        )
        assert result == {"error": "Invoice not found"}
    finally:
        _teardown(db, org)


def test_qr_code_png_nonempty_for_url():
    from app.integrations.stripe.client import generate_qr_code_png

    png = generate_qr_code_png("https://checkout.stripe.com/c/pay/cs_test_xyz")
    assert isinstance(png, bytes)
    assert len(png) > 0
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# ----------------------------------------------------------------- webhook tests


def _signed_event_payload(inv, org, webhook_secret):
    import hashlib
    import hmac
    import time

    payload = {
        "id": "evt_test_1",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "metadata": {"organization_id": str(org.id), "invoice_id": str(inv.id)},
            }
        },
    }
    body = json.dumps(payload).encode()
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode() + body
    signature = hmac.new(webhook_secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={signature}"
    return body, header


def test_webhook_marks_paid_and_fires_chain_once(db, monkeypatch):
    import stripe

    webhook_secret = "whsec_test_dummy"
    monkeypatch.setattr("app.core.config.settings.STRIPE_WEBHOOK_SECRET", webhook_secret)
    monkeypatch.setattr("app.core.config.settings.STRIPE_SECRET_KEY", "sk_test_dummy")

    from fastapi.testclient import TestClient
    from app.main import app

    org = _org(db)
    inv = _invoice(db, org, status="unpaid")
    calls = {"n": 0}

    def fake_on_invoice_paid(db, organization_id, invoice_id):
        calls["n"] += 1
        return {"receipt": True, "crm_logged": True, "notified": True, "email_sent": True, "reminder_created": True}

    monkeypatch.setattr("app.services.workflow_service.on_invoice_paid", fake_on_invoice_paid)

    body, signature = _signed_event_payload(inv, org, webhook_secret)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/invoices/stripe-webhook",
                content=body,
                headers={"stripe-signature": signature},
            )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["applied"] is True
        assert payload["invoice_id"] == str(inv.id)
        assert calls["n"] == 1

        # fresh read: status flipped to paid
        from app.models.invoice import Invoice

        db.expire_all()
        fresh = db.query(Invoice).filter(Invoice.id == inv.id).first()
        assert fresh.status == "paid"
    finally:
        _teardown(db, org)


def test_webhook_already_paid_does_not_refire(db, monkeypatch):
    import stripe

    webhook_secret = "whsec_test_dummy"
    monkeypatch.setattr("app.core.config.settings.STRIPE_WEBHOOK_SECRET", webhook_secret)
    monkeypatch.setattr("app.core.config.settings.STRIPE_SECRET_KEY", "sk_test_dummy")

    from fastapi.testclient import TestClient
    from app.main import app

    org = _org(db)
    inv = _invoice(db, org, status="paid")
    calls = {"n": 0}

    def fake_on_invoice_paid(db, organization_id, invoice_id):
        calls["n"] += 1
        return {}

    monkeypatch.setattr("app.services.workflow_service.on_invoice_paid", fake_on_invoice_paid)

    body, signature = _signed_event_payload(inv, org, webhook_secret)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/invoices/stripe-webhook",
                content=body,
                headers={"stripe-signature": signature},
            )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["applied"] is False
        assert "already paid" in payload["note"]
        assert calls["n"] == 0
    finally:
        _teardown(db, org)


def test_webhook_invoice_paid_event_marks_paid_via_payment_intent(db, monkeypatch):
    """The webhook also accepts invoice.paid / invoice.payment_succeeded by
    resolving org+invoice from the PaymentIntent metadata (which Stripe copies
    from the Checkout Session). This matches the events registered in the
    Stripe dashboard."""
    import stripe

    webhook_secret = "whsec_test_dummy"
    monkeypatch.setattr("app.core.config.settings.STRIPE_WEBHOOK_SECRET", webhook_secret)
    monkeypatch.setattr("app.core.config.settings.STRIPE_SECRET_KEY", "sk_test_dummy")

    from fastapi.testclient import TestClient
    from app.main import app

    org = _org(db)
    inv = _invoice(db, org, status="unpaid")

    monkeypatch.setattr(
        "app.services.workflow_service.on_invoice_paid",
        lambda db_, oid, iid: {"email_sent": False},
    )

    class FakePI:
        metadata = {"organization_id": str(org.id), "invoice_id": str(inv.id)}

    monkeypatch.setattr(stripe.PaymentIntent, "retrieve", staticmethod(lambda *a, **k: FakePI()))

    body = json.dumps({
        "id": "evt_inv_paid",
        "object": "event",
        "type": "invoice.paid",
        "data": {"object": {"id": "in_test_1", "payment_intent": "pi_test_1"}},
    }).encode()
    import hashlib
    import hmac
    import time

    ts = int(time.time())
    signature = hmac.new(webhook_secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={signature}"

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/invoices/stripe-webhook",
                content=body,
                headers={"stripe-signature": header},
            )
        assert resp.status_code == 200
        assert resp.json()["applied"] is True
        assert resp.json()["invoice_id"] == str(inv.id)
        from app.models.invoice import Invoice

        db.expire_all()
        fresh = db.query(Invoice).filter(Invoice.id == inv.id).first()
        assert fresh.status == "paid"
    finally:
        _teardown(db, org)


def test_webhook_alias_path_finance_invoices_works(db, monkeypatch):
    """Webhooks registered at the legacy /finance/invoices/stripe-webhook URL
    must still work — the handler is mounted at both paths."""
    webhook_secret = "whsec_test_dummy"
    monkeypatch.setattr("app.core.config.settings.STRIPE_WEBHOOK_SECRET", webhook_secret)
    monkeypatch.setattr("app.core.config.settings.STRIPE_SECRET_KEY", "sk_test_dummy")

    from fastapi.testclient import TestClient
    from app.main import app

    org = _org(db)
    inv = _invoice(db, org, status="unpaid")

    monkeypatch.setattr(
        "app.services.workflow_service.on_invoice_paid",
        lambda db_, oid, iid: {"email_sent": False},
    )

    body, signature = _signed_event_payload(inv, org, webhook_secret)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/finance/invoices/stripe-webhook",
                content=body,
                headers={"stripe-signature": signature},
            )
        assert resp.status_code == 200
        assert resp.json()["applied"] is True
        assert resp.json()["invoice_id"] == str(inv.id)
    finally:
        _teardown(db, org)


def test_webhook_bad_signature_rejected(db, monkeypatch):
    import stripe

    monkeypatch.setattr("app.core.config.settings.STRIPE_WEBHOOK_SECRET", "whsec_real")
    monkeypatch.setattr("app.core.config.settings.STRIPE_SECRET_KEY", "sk_test_dummy")

    from fastapi.testclient import TestClient
    from app.main import app

    org = _org(db)
    inv = _invoice(db, org)

    # sign with a DIFFERENT secret than configured -> construct_event fails
    wrong = "whsec_wrong"
    body, _ = _signed_event_payload(inv, org, wrong)

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/invoices/stripe-webhook",
                content=body,
                headers={"stripe-signature": "t=1,v1=deadbeef"},
            )
        assert resp.status_code == 400
    finally:
        _teardown(db, org)