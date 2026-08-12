"""One-off dev-DB cleanup: remove leftover 'WhatsApp Test Org' rows.

These accumulate when a test run is killed before its teardown (e.g. the
full-suite timeout), and they can hijack whatsapp webhook resolution because
resolve_organization_id matches the phone_number_id across all orgs.

Safe to re-run; deletes only orgs named 'WhatsApp Test Org' or with a
whatsapp- slug, plus their child rows (FK-safe order first).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.database import engine

CHILD_TABLES = [
    "ai_messages",
    "ai_conversations",
    "whatsapp_messages",
    "whatsapp_contacts",
    "users",
    "integrations",
]

# Autocommit: one failed statement must not poison the rest.
conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")

orgs = conn.execute(
    text(
        "SELECT id FROM organizations "
        "WHERE name = 'WhatsApp Test Org' OR slug LIKE 'whatsapp-%'"
    )
).fetchall()
print(f"test orgs found: {len(orgs)}")
if not orgs:
    conn.close()
    raise SystemExit(0)

# Bind as native uuid objects so `= ANY(:ids)` produces uuid[].
ids = [row[0] for row in orgs]

tables = [
    row[0]
    for row in conn.execute(
        text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE column_name = 'organization_id' AND table_schema = 'public'"
        )
    ).fetchall()
]
for table in sorted(set(tables) - set(CHILD_TABLES) - {"organizations"}):
    try:
        n = conn.execute(
            text(f"DELETE FROM {table} WHERE organization_id = ANY(:ids)"),
            {"ids": ids},
        ).rowcount
        if n:
            print(f"  deleted {n} rows from {table}")
    except Exception as exc:  # noqa: BLE001
        print(f"  skipped {table}: {type(exc).__name__}")
for table in CHILD_TABLES:
    try:
        n = conn.execute(
            text(f"DELETE FROM {table} WHERE organization_id = ANY(:ids)"),
            {"ids": ids},
        ).rowcount
        if n:
            print(f"  deleted {n} rows from {table}")
    except Exception as exc:  # noqa: BLE001
        print(f"  skipped {table}: {type(exc).__name__}")
try:
    n = conn.execute(
        text("DELETE FROM organizations WHERE id = ANY(:ids)"), {"ids": ids}
    ).rowcount
    print(f"  deleted {n} organizations")
except Exception as exc:  # noqa: BLE001
    print(f"  org delete failed: {type(exc).__name__}")

conn.close()
print("cleanup done")
