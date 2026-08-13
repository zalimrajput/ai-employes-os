"""Permanently delete Chaudary (ahq0319@gmail.com) + the entire Qadari org.

No auth.users row exists for this user (created directly in DB). Deletes the
public.users profile, its user_roles assignment, then the Qadari org (cascades
to roles, ai_employees, and any org-scoped rows via FKs). Pre-flight scan runs
in AUTOCOMMIT. Never prints credentials.
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

USER_ID = "2af26079-f837-4327-9d44-e972b451e403"  # ahq0319@gmail.com (Chaudary)
ORG_ID = "4145ebd8-bb28-4cd0-8bb1-803d907ab3bb"  # Qadari
EMAIL = "ahq0319@gmail.com"

engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})

# --- Phase 1: read-only scan, autocommit ---
print("=== PRE-FLIGHT (read-only) ===")
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    print(f"- auth.users for {EMAIL}: "
          f"{conn.execute(text('SELECT count(*) FROM auth.users WHERE email = :e'), {'e': EMAIL}).scalar()} row(s)")
    print(f"- public.users profile: "
          f"{conn.execute(text('SELECT count(*) FROM public.users WHERE id = :i'), {'i': USER_ID}).scalar()} row(s)")
    for table, col in [("public.user_roles", "user_id"), ("public.platform_roles", "user_id")]:
        try:
            print(f"- {table}.{col}: {conn.execute(text(f'SELECT count(*) FROM {table} WHERE {col} = :i'), {'i': USER_ID}).scalar()} row(s)")
        except Exception as exc:
            print(f"- {table}.{col}: skipped ({type(exc).__name__})")
    # org-scoped rows
    checks = [
        ("public.users", "organization_id"), ("public.user_roles", "organization_id"),
        ("public.roles", "organization_id"), ("public.customers", "organization_id"),
        ("public.employees", "organization_id"), ("public.campaigns", "organization_id"),
        ("public.invoices", "organization_id"), ("public.quotations", "organization_id"),
        ("public.expenses", "organization_id"), ("public.budgets", "organization_id"),
        ("public.leads", "organization_id"), ("public.deals", "organization_id"),
        ("public.tasks", "organization_id"), ("public.activities", "organization_id"),
        ("public.workflows", "organization_id"), ("public.meetings", "organization_id"),
        ("public.ai_employees", "organization_id"), ("public.ai_conversations", "organization_id"),
        ("public.subscriptions", "organization_id"), ("public.integrations", "organization_id"),
        ("public.leave_requests", "organization_id"),
    ]
    org_total = 0
    for table, col in checks:
        try:
            n = conn.execute(text(f"SELECT count(*) FROM {table} WHERE {col} = :o"), {"o": ORG_ID}).scalar()
            if n:
                print(f"- {table}.{col}: {n} row(s)")
                org_total += n
        except Exception as exc:
            print(f"- {table}.{col}: skipped ({type(exc).__name__})")
    print(f"  Qadari org-scoped rows total: {org_total}")

# --- Phase 2: deletes in their own transaction ---
with engine.begin() as conn:
    print()
    print("=== DELETING user_roles for Chaudary ===")
    r = conn.execute(text("DELETE FROM public.user_roles WHERE user_id = :i"), {"i": USER_ID})
    print(f"deleted: {r.rowcount}")

    print()
    print("=== DELETING public.users profile ===")
    r = conn.execute(text("DELETE FROM public.users WHERE id = :i"), {"i": USER_ID})
    print(f"deleted: {r.rowcount}")

    print()
    print("=== DELETING Qadari organization (cascades to roles/ai_employees/etc.) ===")
    r = conn.execute(text("DELETE FROM public.organizations WHERE id = :o"), {"o": ORG_ID})
    print(f"deleted: {r.rowcount}")

    print()
    print("=== VERIFY ===")
    print(f"organizations with id: {conn.execute(text('SELECT count(*) FROM public.organizations WHERE id = :o'), {'o': ORG_ID}).scalar()}")
    print(f"users with id: {conn.execute(text('SELECT count(*) FROM public.users WHERE id = :i'), {'i': USER_ID}).scalar()}")
    print(f"users with email: {conn.execute(text('SELECT count(*) FROM public.users WHERE email = :e'), {'e': EMAIL}).scalar()}")
    print(f"auth.users with email: {conn.execute(text('SELECT count(*) FROM auth.users WHERE email = :e'), {'e': EMAIL}).scalar()}")
    print(f"user_roles for user: {conn.execute(text('SELECT count(*) FROM public.user_roles WHERE user_id = :i'), {'i': USER_ID}).scalar()}")

print()
print("DONE — Chaudary and the Qadari org are fully removed.")
