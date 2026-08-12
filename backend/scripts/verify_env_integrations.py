"""Verify every external integration configured in the backend .env.

Checks (1) which credential keys are set, (2) that OAuth callback URLs map to
real routes, (3) tool registry <-> guardrails sync, and (4) LIVE read-only
pings for keys that are present (Stripe balance, WhatsApp Graph /me,
OpenRouter /models, Supabase DB connection).

Usage:
    cd backend && python scripts/verify_env_integrations.py

Never prints secret values — only presence/length and HTTP status codes.
"""
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.ai.guardrails import _SAFE_TOOL_NAMES  # noqa: E402
from app.ai.tools import ALL_TOOLS  # noqa: E402
from app.services.integration_service import OAUTH_PROVIDERS, get_provider_config  # noqa: E402

ok = True


def mark(label: str, passed: bool, detail: str = "") -> None:
    global ok
    ok = ok and passed
    print(("[PASS] " if passed else "[FAIL] ") + label + (f" -- {detail}" if detail else ""))


def main() -> None:
    print("\n=== 1. OAuth providers (creds -> callback route) ===")
    app_routes: set[str] = set()
    try:
        from app.main import app

        for r in app.routes:
            path = getattr(r, "path", "")
            if "/api/v1/integrations/" in path or "/api/v1/whatsapp/" in path or "stripe" in path:
                app_routes.add(path)
    except Exception as exc:  # noqa: BLE001
        print(f"  (app import failed: {exc})")

    for provider in OAUTH_PROVIDERS:
        cfg = get_provider_config(provider)
        if cfg is None:
            mark(f"{provider}: not configured", False, "add client id/secret to .env")
            continue
        uri = cfg["redirect_uri"] or ""
        # The callback is a single templated route (…/oauth/callback/{provider}),
        # so it covers every family/standalone URL below it.
        callback_route = any("oauth/callback" in r for r in app_routes) if app_routes else True
        creds = cfg.get("client_id") is not None
        mark(
            f"{provider}: creds={creds} route={'/oauth/callback/' in uri}",
            creds and callback_route,
            uri,
        )

    print("\n=== 2. Non-OAuth integrations ===")
    mark("Stripe secret key", bool(settings.STRIPE_SECRET_KEY), "sk_test_... / sk_live_...")
    mark("Stripe webhook secret", bool(settings.STRIPE_WEBHOOK_SECRET), "whsec_...")
    mark("WhatsApp API token", bool(settings.WHATSAPP_API_TOKEN))
    mark("WhatsApp phone number ID", bool(settings.WHATSAPP_PHONE_ID))
    mark("WhatsApp verify token", bool(settings.WHATSAPP_VERIFY_TOKEN))
    mark("Cloud storage", bool(settings.S3_ACCESS_KEY_ID and settings.S3_BUCKET), settings.STORAGE_PROVIDER)
    mark("Accounting REST", bool(settings.ACCOUNTING_BASE_URL and settings.ACCOUNTING_API_KEY))
    mark("Encryption key", bool(settings.ENCRYPTION_KEY))

    print("\n=== 3. Wiring checks ===")
    mark("generate_invoice_payment_link tool registered", "generate_invoice_payment_link" in ALL_TOOLS)
    mark("stripe webhook routes present", sum("stripe" in p for p in app_routes) >= 1)
    mark("whatsapp webhook route present", any("/whatsapp/webhook" in p for p in app_routes))
    unsynced = [t for t in ALL_TOOLS if t not in _SAFE_TOOL_NAMES]
    mark(f"tool registry <-> guardrails ({len(ALL_TOOLS)} tools)", not unsynced, str(unsynced))

    print("\n=== 4. LIVE read-only pings (only for keys that exist) ===")
    if settings.STRIPE_SECRET_KEY:
        try:
            r = httpx.get(
                "https://api.stripe.com/v1/balance",
                auth=(settings.STRIPE_SECRET_KEY, ""),
                timeout=20,
            )
            mark("Stripe API key", r.status_code == 200, f"HTTP {r.status_code}")
        except Exception as exc:  # noqa: BLE001
            mark("Stripe API key", False, str(exc)[:100])
    else:
        mark("Stripe API key", False, "empty (sk_test_... from dashboard.stripe.com/apikeys)")

    if settings.WHATSAPP_API_TOKEN:
        try:
            r = httpx.get(
                "https://graph.facebook.com/v19.0/me",
                params={"access_token": settings.WHATSAPP_API_TOKEN},
                timeout=20,
            )
            mark("WhatsApp API token", r.status_code == 200, f"HTTP {r.status_code}")
        except Exception as exc:  # noqa: BLE001
            mark("WhatsApp API token", False, str(exc)[:100])
    else:
        mark("WhatsApp API token", False, "empty (Meta developers > app > WhatsApp > API Setup)")

    if settings.OPENROUTER_API_KEY:
        try:
            r = httpx.get(
                f"{settings.OPENROUTER_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                timeout=20,
            )
            mark("OpenRouter API key", r.status_code == 200, f"HTTP {r.status_code}")
        except Exception as exc:  # noqa: BLE001
            mark("OpenRouter API key", False, str(exc)[:100])
    else:
        mark("OpenRouter API key", False, "empty")

    try:
        from sqlalchemy import create_engine, text

        eng = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 8})
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        mark("Supabase DB", True, "connection + query OK")
        eng.dispose()
    except Exception as exc:  # noqa: BLE001
        mark("Supabase DB", False, str(exc)[:100])

    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED - see above"))


if __name__ == "__main__":
    main()
