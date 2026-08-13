"""Live read-only test of every external integration across all orgs.

Reads each org's connected ``integrations`` rows, exercises each provider's
real API through the app's own client code (including the 401-refresh path),
and prints a PASS/FAIL table per org. Only read-only calls are made — nothing
is created, sent, posted, uploaded or deleted.

Providers whose clients only expose write operations (Slack, Google Sheets)
are probed with their read-only auth endpoints (auth.test / tokeninfo).
"""
import sys

sys.path.insert(0, ".")

import httpx

from app.core.database import SessionLocal
from app.models.integration import Integration
from app.utils.encryption import decrypt_value

# Optional: pass an org id to probe only that org.
FILTER_ORG = sys.argv[1] if len(sys.argv) > 1 else None


def _row(db, org_id, provider):
    return (
        db.query(Integration)
        .filter(Integration.organization_id == org_id, Integration.provider == provider)
        .first()
    )


def probe(provider, fn):
    try:
        print(f"  PASS  {provider}: {fn()}")
    except Exception as exc:  # noqa: BLE001 - diagnostic script prints everything
        print(f"  FAIL  {provider}: {type(exc).__name__}: {str(exc)[:220]}")


def check_gmail(db, org_id):
    from app.integrations.gmail.service import get_client

    msgs = get_client(db, org_id).list_recent_messages(max_results=3)
    return f"ok ({len(msgs)} recent messages)"


def check_google_calendar(db, org_id):
    from app.integrations.google_calendar.service import get_client

    evts = get_client(db, org_id).list_upcoming_events(max_results=3)
    return f"ok ({len(evts)} upcoming events)"


def check_google_drive(db, org_id):
    from app.integrations.google_drive.service import get_client

    files = get_client(db, org_id).list_files(limit=5)
    return f"ok ({len(files)} files visible)"


def check_google_sheets(db, org_id):
    from app.integrations.google_sheets.service import get_client

    client = get_client(db, org_id)
    try:
        client.read_sheet("__auth_probe__", "A1")
    except RuntimeError as exc:
        if "404" in str(exc):
            return "token valid (auto-refresh works)"
        raise
    return "token valid"


def check_outlook(db, org_id):
    from app.integrations.outlook.service import get_client

    msgs = get_client(db, org_id).list_recent_messages(max_results=3)
    return f"ok ({len(msgs)} recent messages)"


def check_microsoft365(db, org_id):
    from app.integrations.microsoft365.service import get_client

    evts = get_client(db, org_id).list_upcoming_events(max_results=3)
    return f"ok ({len(evts)} upcoming events)"


def check_onedrive(db, org_id):
    from app.integrations.onedrive.service import get_client

    files = get_client(db, org_id).list_files(limit=5)
    return f"ok ({len(files)} files in root)"


def check_slack(db, org_id):
    row = _row(db, org_id, "slack")
    token = decrypt_value(row.access_token)
    resp = httpx.post(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    data = resp.json()
    if data.get("ok"):
        return f"ok (workspace={data.get('team') or '?'}, user={data.get('user') or '?'})"
    raise RuntimeError(data.get("error") or resp.text[:150])


def check_zoho(db, org_id):
    from app.integrations.zoho.service import get_client

    leads = get_client(db, org_id).list_leads(limit=5)
    return f"ok ({len(leads)} leads listed)"


def check_xero(db, org_id):
    from app.integrations.xero.service import get_client

    invs = get_client(db, org_id).list_invoices(limit=5)
    return f"ok ({len(invs)} invoices listed)"


def check_whatsapp():
    from app.core.config import settings

    resp = httpx.get(
        f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_ID}",
        params={"access_token": settings.WHATSAPP_API_TOKEN},
        timeout=15,
    )
    if resp.status_code == 200:
        return f"ok (phone name={resp.json().get('name') or '?'})"
    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:150]}")


def check_stripe():
    from app.core.config import settings

    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    bal = stripe.Balance.retrieve()
    total = sum(a["amount"] for a in bal.available) / 100.0
    return f"ok (available balance ${total:,.2f})"


def check_r2():
    from app.integrations.cloud_storage import get_client

    client = get_client()
    if client is None:
        raise RuntimeError("not configured (no STORAGE_PROVIDER/S3 keys)")
    client.check_connection()
    return "bucket reachable (read/write credentials valid)"


# provider -> (check_fn, needs_db)
_OAUTH_CHECKS = {
    "gmail": check_gmail,
    "google-calendar": check_google_calendar,
    "google-drive": check_google_drive,
    "google-sheets": check_google_sheets,
    "outlook": check_outlook,
    "microsoft365": check_microsoft365,
    "onedrive": check_onedrive,
    "slack": check_slack,
    "zoho": check_zoho,
    "xero": check_xero,
}


def main():
    db = SessionLocal()
    try:
        query = (
            db.query(Integration.organization_id)
            .filter(Integration.connected.is_(True))
            .distinct()
        )
        org_ids = [r[0] for r in query.all()]
        if FILTER_ORG:
            org_ids = [o for o in org_ids if str(o) == FILTER_ORG]

        if not org_ids:
            print("no orgs with connected integrations found")
            return

        for org_id in org_ids:
            from app.models.organization import Organization

            org = db.query(Organization).filter(Organization.id == org_id).first()
            name = org.name if org else org_id
            rows = (
                db.query(Integration)
                .filter(
                    Integration.organization_id == org_id,
                    Integration.connected.is_(True),
                )
                .all()
            )
            providers = sorted({r.provider for r in rows})
            print(f"=== {name} ({org_id}) — {len(providers)} connected ===")
            for provider in providers:
                fn = _OAUTH_CHECKS.get(provider)
                if fn is None:
                    print(f"  SKIP  {provider}: no read-only probe defined")
                    continue
                probe(provider, lambda p=provider, f=fn: f(db, org_id))
            print()

        print("--- env-key providers (org-independent) ---")
        probe("whatsapp", check_whatsapp)
        probe("stripe", check_stripe)
        probe("r2", check_r2)
    finally:
        db.close()


if __name__ == "__main__":
    main()
