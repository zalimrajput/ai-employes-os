"""Read-only probe of the org's Gmail integration.

Decrypts the stored OAuth tokens (never printed) and calls the Gmail API
profile endpoint to show (a) which account is connected and (b) whether the
token still works. Falls back to a token-refresh attempt when a 401 occurs,
exactly like GmailClient does. No emails are sent or modified.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key, value)

from sqlalchemy import create_engine, text  # noqa: E402

url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
engine = create_engine(url, connect_args={"connect_timeout": 10})

from app.utils.encryption import decrypt_value  # noqa: E402
from app.core.config import settings  # noqa: E402

import httpx  # noqa: E402

PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def probe(org_id, provider="gmail"):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT access_token, refresh_token, metadata, updated_at "
                "FROM public.integrations "
                "WHERE organization_id = :o AND provider = :p AND connected = TRUE "
                "ORDER BY updated_at DESC LIMIT 1"
            ),
            {"o": org_id, "p": provider},
        ).first()
    if row is None:
        print(f"  no connected {provider} integration for org {org_id}")
        return
    try:
        access = decrypt_value(row.access_token)
        refresh = decrypt_value(row.refresh_token) if row.refresh_token else None
    except Exception as exc:  # noqa: BLE001
        print(f"  token decryption failed: {type(exc).__name__}: {exc}")
        return

    headers = {"Authorization": f"Bearer {access}"}
    resp = httpx.get(PROFILE_URL, headers=headers, timeout=30)
    print(f"  direct GET profile -> {resp.status_code}")
    if resp.status_code == 401 and refresh:
        print("  token expired; trying refresh...")
        r = httpx.post(
            TOKEN_URL,
            data={
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        print(f"  refresh POST -> {r.status_code}")
        if r.status_code >= 300:
            print(f"  refresh body: {r.text[:200]}")
            return
        access = r.json().get("access_token")
        resp = httpx.get(PROFILE_URL, headers={"Authorization": f"Bearer {access}"}, timeout=30)
        print(f"  GET profile after refresh -> {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  connected account: {data.get('emailAddress')}")
    else:
        print(f"  body: {resp.text[:300]}")


if __name__ == "__main__":
    org_ids = sys.argv[1:] or None
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT o.name, i.organization_id, i.provider "
                "FROM public.integrations i JOIN public.organizations o ON o.id = i.organization_id "
                "WHERE i.provider = 'gmail' AND i.connected = TRUE"
            )
        ).fetchall()
    for name, oid, provider in rows:
        if org_ids and str(oid) not in org_ids:
            continue
        print(f"=== {name} ({oid}) ===")
        probe(oid, provider)
        print()
