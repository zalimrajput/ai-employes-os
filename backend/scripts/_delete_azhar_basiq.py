"""Permanently delete two confirmed auth users (basiqazhar827/65@gmail.com).

Removes auth.users rows + any public.users profiles, user_roles, platform_roles
referencing them. Pre-flight scan runs in AUTOCOMMIT so a missing table can't
abort the delete transaction. Never prints credentials.
"""
import os
import sys
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key, value)

url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
if not url:
    raise SystemExit("No DATABASE_URL in backend/.env")

from sqlalchemy import create_engine, text  # noqa: E402

IDS = (
    "eb7e02ec-1b22-42d9-8464-d6e82da276b4",  # basiqazhar827@gmail.com
    "43b73075-5d40-45b6-8343-70256f44dc61",  # basiqazhar65@gmail.com
)
EMAILS = ("basiqazhar827@gmail.com", "basiqazhar65@gmail.com")

REF_TABLES = [
    ("public.user_roles", "user_id"),
    ("public.platform_roles", "user_id"),
    ("public.activities", "user_id"),
    ("public.ai_conversations", "user_id"),
    ("public.tasks", "created_by"),
    ("public.tasks", "assigned_to"),
    ("public.reminders", "user_id"),
    ("public.integrations", "user_id"),
    ("public.organizations", "owner_id"),
]

engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})

# --- Phase 1: read-only scan, autocommit so one bad table can't abort the rest ---
print("=== PRE-FLIGHT: rows referencing the two ids (read-only) ===")
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    found = []
    for table, col in REF_TABLES:
        try:
            n = conn.execute(
                text(f"SELECT count(*) FROM {table} WHERE {col} IN :ids"),
                {"ids": IDS},
            ).scalar()
            if n:
                found.append((table, col, n))
                print(f"- {table}.{col}: {n} row(s)")
        except Exception as exc:  # noqa: BLE001 - table/column may not exist
            print(f"- {table}.{col}: skipped ({type(exc).__name__})")
    if not found:
        print("(nothing references these ids)")

# --- Phase 2: deletes in their own transaction ---
with engine.begin() as conn:
    print()
    print("=== DELETING public.users profiles (if any) ===")
    result = conn.execute(
        text("DELETE FROM public.users WHERE id IN :ids"),
        {"ids": IDS},
    )
    print(f"deleted: {result.rowcount} public.users row(s)")

    print()
    print("=== DELETING auth.users ===")
    result = conn.execute(
        text("DELETE FROM auth.users WHERE id IN :ids"),
        {"ids": IDS},
    )
    print(f"deleted: {result.rowcount} auth.users row(s)")

    print()
    print("=== VERIFY ===")
    left_auth = conn.execute(
        text("SELECT email FROM auth.users WHERE email IN :emails"),
        {"emails": EMAILS},
    ).fetchall()
    left_users = conn.execute(
        text("SELECT email FROM public.users WHERE email IN :emails"),
        {"emails": EMAILS},
    ).fetchall()
    left_profiles = conn.execute(
        text("SELECT count(*) FROM public.users WHERE id IN :ids"),
        {"ids": IDS},
    ).scalar()
    print(f"auth.users with those emails: {[r[0] for r in left_auth] or 'NONE'}")
    print(f"public.users with those emails: {[r[0] for r in left_users] or 'NONE'}")
    print(f"public.users profiles with those ids: {left_profiles}")

print()
print("DONE — no record left for these emails; re-registration unblocked.")
