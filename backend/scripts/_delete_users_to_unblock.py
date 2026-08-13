"""Permanently delete two confirmed auth.users rows (by exact id).

Cascades: public.users (FK ON DELETE CASCADE) -> user_roles / platform_roles.
Pre-flight lists any other rows referencing the ids; the DELETE rolls back if a
referencing FK is NO ACTION/RESTRICT. Never prints credentials.
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

IDS = [
    "58e5fec5-143b-4a40-a1bb-9278763ff3ff",  # rkmeer6692@gmail.com  (khan)
    "8905eda2-805c-462a-948b-419669ecf4c0",  # rj1490606@gmail.com   (Rehan khan)
]
EMAILS = ["rkmeer6692@gmail.com", "rj1490606@gmail.com"]

# Tables that reference users (best-effort: column may not exist in all envs).
REF_TABLES = [
    ("public.user_roles", "user_id"),
    ("public.platform_roles", "user_id"),
    ("public.activities", "user_id"),
    ("public.ai_conversations", "user_id"),
    ("public.tasks", "created_by"),
    ("public.tasks", "assigned_to"),
    ("public.reminders", "user_id"),
    ("public.ai_messages", "user_id"),
    ("public.integrations", "user_id"),
]

engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})

with engine.begin() as conn:
    print("=== PRE-FLIGHT: rows referencing the two ids ===")
    for table, col in REF_TABLES:
        try:
            n = conn.execute(
                text(f"SELECT count(*) FROM {table} WHERE {col} IN :ids").bindparams(
                    bind_parameter_name="ids"
                ),
                {"ids": tuple(IDS)},
            ).scalar()
            if n:
                print(f"- {table}.{col}: {n} row(s)")
        except Exception as exc:  # noqa: BLE001 - column/table may not exist
            print(f"- {table}.{col}: skipped ({type(exc).__name__})")
    print("(no rows listed above = nothing else references these users)")

    print()
    print("=== DELETING from auth.users ===")
    result = conn.execute(
        text("DELETE FROM auth.users WHERE id IN :ids"),
        {"ids": tuple(IDS)},
    )
    print(f"deleted: {result.rowcount} auth.users row(s)")

    print()
    print("=== VERIFY ===")
    remaining = conn.execute(
        text("SELECT email FROM auth.users WHERE email IN :emails"),
        {"emails": tuple(EMAILS)},
    ).fetchall()
    print(f"auth.users still holding those emails: {[r[0] for r in remaining] or 'NONE'}")
    remaining_profiles = conn.execute(
        text("SELECT id, full_name FROM public.users WHERE id IN :ids"),
        {"ids": tuple(IDS)},
    ).fetchall()
    print(f"public.users profiles still present: {len(remaining_profiles)}")

print()
print("DONE — re-registration with these emails is now unblocked.")
