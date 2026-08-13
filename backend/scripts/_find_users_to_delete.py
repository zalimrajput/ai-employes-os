"""Read-only: find users matching the names flagged for deletion.

Prints only user rows (id, email, full_name, org, dates) — never credentials.
"""
import os
from pathlib import Path

# Load backend/.env into the environment (no secrets printed).
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

engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})

NAMES = ["hali", "zalim kuri", "rehan khan", "khan"]

with engine.connect() as conn:
    print("=== AUTH + PROFILE MATCHES (auth.users) ===")
    rows = conn.execute(
        text(
            """
            SELECT a.id, a.email, a.email_confirmed_at IS NOT NULL AS confirmed,
                   u.full_name, o.name AS org_name, a.created_at
            FROM auth.users a
            LEFT JOIN public.users u ON u.id = a.id
            LEFT JOIN public.organizations o ON o.id = u.organization_id
            WHERE u.full_name ILIKE '%hali%'
               OR u.full_name ILIKE '%zalim%'
               OR u.full_name ILIKE '%rehan%'
               OR u.full_name ILIKE '%khan%'
            ORDER BY a.created_at
            """
        )
    ).fetchall()
    for r in rows:
        print(f"- {r.email}  |  {r.full_name}  |  id={r.id}  |  confirmed={r.confirmed}  |  org={r.org_name}  |  created={r.created_at}")

    print()
    print("=== ORPHAN PROFILES (public.users WITHOUT auth.users) ===")
    orphans = conn.execute(
        text(
            """
            SELECT u.id, u.email, u.full_name, o.name AS org_name, u.created_at
            FROM public.users u
            LEFT JOIN public.organizations o ON o.id = u.organization_id
            WHERE NOT EXISTS (SELECT 1 FROM auth.users a WHERE a.id = u.id)
              AND (u.full_name ILIKE '%hali%'
                OR u.full_name ILIKE '%zalim%'
                OR u.full_name ILIKE '%rehan%'
                OR u.full_name ILIKE '%khan%')
            ORDER BY u.created_at
            """
        )
    ).fetchall()
    for r in orphans:
        print(f"- {r.email}  |  {r.full_name}  |  id={r.id}  |  org={r.org_name}  |  created={r.created_at}")

    print()
    print("=== TOTAL auth.users in project ===")
    total = conn.execute(text("SELECT count(*) FROM auth.users")).scalar()
    print(total)
