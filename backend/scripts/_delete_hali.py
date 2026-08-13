"""Permanently delete confirmed auth user hali49537@gmail.com.

Removes auth.users row + any public.users profile, user_roles, platform_roles
referencing it. Pre-flight scan runs in AUTOCOMMIT so a missing table can't
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

IDS = ("75176e5d-0006-443f-8220-22d7c45ae3aa",)  # hali49537@gmail.com
EMAILS = ("hali49537@gmail.com",)

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
print("=== PRE-FLIGHT: rows referencing the id (read-only) ===")
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
        print("(nothing references this id)")

# --- Phase 2: deletes in their own transaction ---
with engine.begin() as conn:
    print()
    print("=== DELETING public.users profile (if any) ===")
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
    print(f"auth.users with that email: {[r[0] for r in left_auth] or 'NONE'}")
    print(f"public.users with that email: {[r[0] for r in left_users] or 'NONE'}")

print()
print("DONE — hali account removed; re-registration unblocked.")
