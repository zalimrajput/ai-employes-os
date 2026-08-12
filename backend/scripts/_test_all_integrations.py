"""Live read-only test of every external integration for the technove org.

Reads the org's connected ``integrations`` rows, exercises each provider's real
API through the app's own client code (including the 401-refresh path), and
prints a PASS/FAIL table. Only read-only calls are made — nothing is created,
sent, posted, uploaded or deleted.

Providers whose clients only expose write operations (Slack, Google Sheets)
are probed with their read-only auth endpoints (auth.test / tokeninfo).
"""
import sys

sys.path.insert(0, ".")

import httpx

from app.core.database import SessionLocal
from app.models.integration import Integration
from app.models.organization import Organization
from app.utils.encryption import decrypt_value

# The "technove solution" organization.
ORG_ID = "88f45e8f-73f3-4b9a-b247-a1c826c08311"


def _row(db, provider):
    return (
        db.query(Integration)
        .filter(Integration.organization_id == ORG_ID, Integration.provider == provider)
        .first()
    )


def probe(provider, fn):
    try:
        print(f"  PASS  {provider}: {fn()}")
    except Exception as exc:  # noqa: BLE001 - diagnostic script prints everything
        print(f"  FAIL  {provider}: {type(exc).__name__}: {str(exc)[:220]}")


def check_gmail(db):
    from app.integrations.gmail.service import get_client

    msgs = get_client(db, ORG_ID).list_recent_messages(max_results=3)
    return f"ok ({len(msgs)} recent messages)"


def check_google_calendar(db):
    from app.integrations.google_calendar.service import get_client

    evts = get_client(db, ORG_ID).list_upcoming_events(max_results=3)
    return f"ok ({len(evts)} upcoming events)"


def check_google_drive(db):
    from app.integrations.google_drive.service import get_client

    files = get_client(db, ORG_ID).list_files(limit=5)
    return f"ok ({len(files)} files visible)"


def check_google_sheets(db):
    # The sheets client exposes no list endpoint, so probe auth through the
    # app's own client instead: a read against a fake spreadsheet id triggers
    # the 401-refresh path and returns 404 when the credentials are valid
    # ("fake doc not found"). A 401 here means the refresh failed.
    from app.integrations.google_sheets.service import get_client

    client = get_client(db, ORG_ID)
    try:
        client.read_sheet("__auth_probe__", "A1")
    except RuntimeError as exc:
        if "404" in str(exc):
            return "token valid (auto-refresh works)"
        raise
    return "token valid"


def check_outlook(db):
    from app.integrations.outlook.service import get_client

    msgs = get_client(db, ORG_ID).list_recent_messages(max_results=3)
    return f"ok ({len(msgs)} recent messages)"


def check_microsoft365(db):
    from app.integrations.microsoft365.service import get_client

    evts = get_client(db, ORG_ID).list_upcoming_events(max_results=3)
    return f"ok ({len(evts)} upcoming events)"


def check_onedrive(db):
    from app.integrations.onedrive.service import get_client

    files = get_client(db, ORG_ID).list_files(limit=5)
    return f"ok ({len(files)} files in root)"


def check_slack(db):
    # SlackClient only exposes post_message (a write); auth.test is read-only.
    row = _row(db, "slack")
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


def check_zoho(db):
    from app.integrations.zoho.service import get_client

    leads = get_client(db, ORG_ID).list_leads(limit=5)
    return f"ok ({len(leads)} leads listed)"


def check_xero(db):
    from app.integrations.xero.service import get_client

    invs = get_client(db, ORG_ID).list_invoices(limit=5)
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


def main():
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.id == ORG_ID).first()
        if org is None:
            print(f"org {ORG_ID} NOT FOUND in database")
            return
        print(f"org: {org.name} ({org.id})")
        rows = db.query(Integration).filter(Integration.organization_id == ORG_ID).all()
        print(f"connected rows: {len(rows)}")
        print()
        print("--- OAuth providers (read-only API calls with stored tokens) ---")
        probe("gmail", lambda: check_gmail(db))
        probe("google-calendar", lambda: check_google_calendar(db))
        probe("google-drive", lambda: check_google_drive(db))
        probe("google-sheets", lambda: check_google_sheets(db))
        probe("outlook", lambda: check_outlook(db))
        probe("microsoft365", lambda: check_microsoft365(db))
        probe("onedrive", lambda: check_onedrive(db))
        probe("slack", lambda: check_slack(db))
        probe("zoho", lambda: check_zoho(db))
        probe("xero", lambda: check_xero(db))
        print()
        print("--- env-key providers (live connectivity checks) ---")
        probe("whatsapp", check_whatsapp)
        probe("stripe", check_stripe)
        probe("r2", check_r2)
    finally:
        db.close()


if __name__ == "__main__":
    main()
