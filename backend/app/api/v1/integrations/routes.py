import logging
from secrets import token_urlsafe
from urllib.parse import urlencode

logger = logging.getLogger("app.api.v1.integrations")

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1._crud import crud_router, require_org_member
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.integration import Integration
from app.services.integration_service import (
    OAUTH_PROVIDERS,
    build_authorize_url,
    disconnect,
    exchange_code,
    get_provider_config,
    save_credentials,
)


router = APIRouter()

# Providers that share a single registered callback URL (so only one redirect
# URI is needed per console). The real provider is encoded in the OAuth state
# token and resolved by _resolve_callback_provider on the way back.
_PROVIDER_FAMILIES = {
    "google": ("gmail", "google-calendar", "google-drive", "google-sheets"),
    "microsoft": ("outlook", "microsoft365", "onedrive"),
}


def _resolve_callback_provider(provider: str, state: str) -> str | None:
    """Resolve the actual provider for a callback hit.

    Family callbacks (/oauth/callback/google, /oauth/callback/microsoft) carry
    the real provider inside the state token: ``<org_id>:<provider>:<random>``.
    Standalone providers (slack, zoho, xero) are used directly.
    """
    if provider not in _PROVIDER_FAMILIES:
        return provider
    parts = state.split(":")
    if len(parts) >= 2 and parts[1] in _PROVIDER_FAMILIES[provider]:
        return parts[1]
    return None


@router.get("/integrations/status", tags=["Integrations"])
# Protected endpoint: per-provider configured/connected state. Never returns
# tokens — the generic CRUD list would, so the UI must use this instead.
# NOTE: registered before the CRUD router so "/status" is not swallowed by
# the UUID "{item_id}" route.
def integration_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    me = require_org_member(db, current_user)
    rows = (
        db.query(Integration)
        .filter(Integration.organization_id == me.organization_id)
        .all()
    )
    connected_map = {r.provider: bool(r.connected) for r in rows}
    statuses = [
        {
            "provider": provider,
            "configured": get_provider_config(provider) is not None,
            "connected": bool(connected_map.get(provider, False)),
        }
        for provider in OAUTH_PROVIDERS
    ]
    statuses.extend(
        _key_provider_statuses(db, connected_map, me.organization_id)
    )
    return statuses


def _key_provider_statuses(
    db: Session,
    connected_map: dict[str, bool] | None = None,
    organization_id: str | None = None,
) -> list[dict]:
    """Configured/connected flags for env-key providers (no network calls).

    The Connect button runs the live check via /integrations/check/{provider};
    a successful check persists the connected flag in the integrations table
    (see _persist_key_connection) so the badge survives page refreshes — the
    same source the OAuth providers use. ``connected_map`` is org -> provider ->
    connected from that table. WhatsApp may also be configured per-org (own
    token + phone number ID stored in the org's integration row), which counts
    as configured for that org even without platform-level env keys.
    """
    from app.core.config import settings as app_settings
    from app.integrations.cloud_storage import get_client as get_storage_client

    connected_map = connected_map or {}
    org_has_whatsapp = False
    whatsapp_phone_id: str | None = None
    if organization_id:
        wa_row = (
            db.query(Integration)
            .filter(
                Integration.organization_id == organization_id,
                Integration.provider == "whatsapp",
                Integration.access_token.isnot(None),
                Integration.access_token != "",
            )
            .first()
        )
        if wa_row is not None:
            org_has_whatsapp = True
            # The org's OWN number id — lets the UI show which number this
            # workspace is connected to (each org stores its own).
            whatsapp_phone_id = (wa_row.metadata_json or {}).get("phone_number_id")

    def entry(provider: str, configured: bool) -> dict:
        return {
            "provider": provider,
            "configured": configured,
            # Only report connected while the credentials are still present.
            "connected": bool(configured and connected_map.get(provider, False)),
        }

    whatsapp_entry = entry(
        "whatsapp",
        bool(app_settings.WHATSAPP_API_TOKEN and app_settings.WHATSAPP_PHONE_ID)
        or org_has_whatsapp,
    )
    whatsapp_entry["phone_number_id"] = whatsapp_phone_id

    return [
        whatsapp_entry,
        entry("stripe", bool(app_settings.STRIPE_SECRET_KEY)),
        entry("r2", get_storage_client() is not None),
    ]


def _persist_key_connection(db, organization_id, provider: str, connected: bool) -> None:
    """Remember an env-key provider's last live-check outcome in the
    integrations table so the Connected badge survives a page refresh —
    mirroring how OAuth providers store their connected row. The keys
    themselves stay in the backend .env; only the flag is persisted."""
    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == organization_id,
            Integration.provider == provider,
        )
        .first()
    )
    if row is None:
        row = Integration(
            organization_id=organization_id,
            provider=provider,
            connected=connected,
            metadata_json={"kind": "env-key"},
        )
        db.add(row)
    else:
        row.connected = connected
    db.commit()


@router.get("/integrations/check/{provider}", tags=["Integrations"])
# Protected endpoint: live connectivity test for the env-key providers
# (whatsapp / stripe / r2). Read-only — never sends messages or creates
# anything. Returns {provider, configured, connected, detail}. The outcome is
# persisted (see _persist_key_connection) so /integrations/status reports
# Connected after a refresh.
def integration_check(
    provider: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    me = require_org_member(db, current_user)
    result = _run_key_check(provider)
    _persist_key_connection(db, me.organization_id, provider, bool(result["connected"]))
    return result


def _run_key_check(provider: str) -> dict:
    """Live read-only connectivity test for one env-key provider."""
    from app.core.config import settings as app_settings

    if provider == "whatsapp":
        token = app_settings.WHATSAPP_API_TOKEN
        pnid = app_settings.WHATSAPP_PHONE_ID
        if not (token and pnid):
            return {
                "provider": provider,
                "configured": False,
                "connected": False,
                "detail": "Not configured — set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_ID in the backend .env",
            }
        import httpx

        try:
            resp = httpx.get(
                f"https://graph.facebook.com/v21.0/{pnid}",
                params={"access_token": token},
                timeout=15,
            )
        except httpx.HTTPError as exc:
            return {
                "provider": provider,
                "configured": True,
                "connected": False,
                "detail": f"Could not reach Meta's Graph API: {exc.__class__.__name__}",
            }
        if resp.status_code == 200:
            return {
                "provider": provider,
                "configured": True,
                "connected": True,
                "detail": "WhatsApp Cloud API reachable with the configured token",
            }
        return {
            "provider": provider,
            "configured": True,
            "connected": False,
            "detail": f"Meta rejected the token ({resp.status_code}): {resp.text[:200]}",
        }

    if provider == "stripe":
        if not app_settings.STRIPE_SECRET_KEY:
            return {
                "provider": provider,
                "configured": False,
                "connected": False,
                "detail": "Not configured — set STRIPE_SECRET_KEY in the backend .env",
            }
        import stripe

        stripe.api_key = app_settings.STRIPE_SECRET_KEY
        try:
            stripe.Balance.retrieve()
        except stripe.error.AuthenticationError as exc:
            return {
                "provider": provider,
                "configured": True,
                "connected": False,
                "detail": f"Stripe rejected the secret key: {exc}",
            }
        except stripe.error.StripeError as exc:
            return {
                "provider": provider,
                "configured": True,
                "connected": False,
                "detail": f"Stripe error: {exc.__class__.__name__}: {exc}",
            }
        return {
            "provider": provider,
            "configured": True,
            "connected": True,
            "detail": "Stripe API reachable with the configured secret key",
        }

    if provider == "r2":
        from app.integrations.cloud_storage import (
            CloudStorageError,
            get_client as get_storage_client,
        )

        client = get_storage_client()
        if client is None:
            return {
                "provider": provider,
                "configured": False,
                "connected": False,
                "detail": (
                    "Not configured — set STORAGE_PROVIDER=s3|r2 plus "
                    "S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY "
                    "and S3_BUCKET in the backend .env"
                ),
            }
        try:
            client.check_connection()
        except CloudStorageError as exc:
            return {
                "provider": provider,
                "configured": True,
                "connected": False,
                "detail": str(exc),
            }
        return {
            "provider": provider,
            "configured": True,
            "connected": True,
            "detail": "Bucket reachable with the configured credentials",
        }

    raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")


class WhatsAppCredentialsIn(BaseModel):
    """Per-organization WhatsApp Cloud API credentials."""

    api_token: str
    phone_number_id: str


@router.post("/integrations/whatsapp/credentials", tags=["Integrations"])
# Protected endpoint: stores the ORGANIZATION'S OWN WhatsApp credentials
# (encrypted in its integration row, with the phone number id in metadata so
# the inbound webhook can route to the right tenant). The token is verified
# live against Meta before anything is saved.
def save_whatsapp_credentials(
    body: WhatsAppCredentialsIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    me = require_org_member(db, current_user)
    token = (body.api_token or "").strip()
    pnid = (body.phone_number_id or "").strip()
    if not token or not pnid:
        raise HTTPException(
            status_code=400,
            detail="Both the WhatsApp API token and phone number ID are required",
        )
    import httpx

    try:
        resp = httpx.get(
            f"https://graph.facebook.com/v21.0/{pnid}",
            params={"access_token": token},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Meta's Graph API: {exc.__class__.__name__}",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Meta rejected the token ({resp.status_code}): {resp.text[:200]}",
        )

    from app.utils.encryption import encrypt_value

    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == me.organization_id,
            Integration.provider == "whatsapp",
        )
        .first()
    )
    if row is None:
        row = Integration(
            organization_id=me.organization_id,
            provider="whatsapp",
            connected=True,
            access_token=encrypt_value(token),
            metadata_json={"kind": "whatsapp", "phone_number_id": pnid},
        )
        db.add(row)
    else:
        row.connected = True
        row.access_token = encrypt_value(token)
        row.metadata_json = {"kind": "whatsapp", "phone_number_id": pnid}
    db.commit()
    return {
        "provider": "whatsapp",
        "configured": True,
        "connected": True,
        "detail": "WhatsApp connected with your own number",
    }


router.include_router(
    crud_router(
        Integration,
        prefix="/integrations",
        tags=["Integrations"],
        search_fields=["provider"],
    )
)


def _frontend_settings_url(provider: str, status: str, detail: str | None = None) -> str:
    """Build the URL the browser lands on after an OAuth round-trip.

    FRONTEND_ORIGIN may be a comma-separated list (CORS); use the first entry.
    ``detail`` carries the provider's error text so the UI can show the real
    reason instead of a generic message.
    """
    origin = str(settings.FRONTEND_ORIGIN or "http://localhost:3000").split(",")[0].strip()
    params = {"tab": "integrations", "status": status, "provider": provider}
    if detail:
        params["error_description"] = detail
    return f"{origin}/dashboard/settings?{urlencode(params)}"


@router.get("/integrations/oauth/connect/{provider}", tags=["Integrations"])
# Protected endpoint: returns the provider authorization URL to redirect to.
def oauth_start(
    provider: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    me = require_org_member(db, current_user)
    if get_provider_config(provider) is None:
        raise HTTPException(
            status_code=400,
            detail="Provider not configured — add its client ID/secret to the backend .env",
        )
    # The state token carries org + provider so shared family callback URLs
    # (e.g. /oauth/callback/google) know which provider to exchange for.
    state = f"{me.organization_id}:{provider}:{token_urlsafe(16)}"
    try:
        return {"authorize_url": build_authorize_url(provider, state)}
    except ValueError:
        raise HTTPException(status_code=400, detail="Provider not configured")


@router.get("/integrations/oauth/callback/{provider}", tags=["Integrations"])
# Public callback: exchanges the provider code, stores encrypted tokens, then
# bounces the browser back to the frontend settings page.
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    db: Session = Depends(get_db),
):
    # Family callbacks need the provider resolved from state before anything
    # else; the resolved name is what the frontend should display.
    resolved = _resolve_callback_provider(provider, state)
    if resolved is None:
        logger.warning("oauth callback with invalid state provider=%s", provider)
        return RedirectResponse(
            _frontend_settings_url(provider, "error"),
            status_code=302,
        )
    provider = resolved
    if error:
        detail = error_description or error
        logger.warning("oauth callback error provider=%s error=%s detail=%s", provider, error, detail)
        return RedirectResponse(
            _frontend_settings_url(provider, "error", detail=detail),
            status_code=302,
        )
    try:
        # Guard against malformed/forged state: org_id must be a valid UUID
        # before it is used in any DB query (an invalid value would 500).
        from uuid import UUID

        org_id = UUID(state.split(":", 1)[0])
    except (ValueError, IndexError, AttributeError, TypeError):
        return RedirectResponse(
            _frontend_settings_url(provider, "error"),
            status_code=302,
        )
    # The org named in the state token must actually exist — otherwise the
    # credential upsert below would trip the foreign key and surface as a raw
    # 500 to the browser. Bounce with a clean error redirect instead.
    from app.models.organization import Organization

    org_exists = (
        db.query(Organization.id).filter(Organization.id == org_id).first() is not None
    )
    if not org_exists:
        logger.warning("oauth callback for unknown organization org_id=%s", org_id)
        return RedirectResponse(
            _frontend_settings_url(
                provider,
                "error",
                detail=(
                    "Invalid organization in OAuth state — start Connect again "
                    "from your workspace settings"
                ),
            ),
            status_code=302,
        )
    try:
        tokens = await exchange_code(provider, code)
    except RuntimeError as exc:
        logger.warning("oauth exchange failed provider=%s error=%s", provider, exc)
        return RedirectResponse(
            _frontend_settings_url(provider, "error", detail=str(exc)),
            status_code=302,
        )
    try:
        save_credentials(db, org_id, provider, tokens)
    except IntegrityError as exc:
        # An org deleted mid-flight (between the existence check and the
        # insert) trips the foreign key — bounce with an error, never a 500.
        # Anything else is a genuine bug and is allowed to surface.
        logger.warning("oauth credential save failed provider=%s error=%s", provider, exc)
        db.rollback()
        return RedirectResponse(
            _frontend_settings_url(
                provider, "error", detail="Could not store credentials — please try again"
            ),
            status_code=302,
        )
    return RedirectResponse(
        _frontend_settings_url(provider, "connected"),
        status_code=302,
    )