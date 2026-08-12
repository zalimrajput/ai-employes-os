"""Third-party integrations: OAuth connect/disconnect + Stripe webhook.

All tokens are encrypted at rest via ``app.utils.encryption``.  The frontend
settings page lists integrations and shows Connected/Connect state from the
``integrations`` table.
"""
import logging
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.models.integration import Integration
from app.utils.encryption import encrypt_value

logger = logging.getLogger("app.services.integration_service")

# OAuth providers exposed to the UI (keys of _PROVIDER_CONFIG).
OAUTH_PROVIDERS = (
    "gmail",
    "google-calendar",
    "outlook",
    "microsoft365",
    "slack",
    "zoho",
    "xero",
    "google-drive",
    "google-sheets",
    "onedrive",
)

# provider key -> (client id setting, client secret setting, redirect setting,
#                  auth url, token url, scope, token-auth style)
# token_auth: "form" posts client_id/secret in the body (Google/Zoho/Microsoft),
#             "basic" sends them as HTTP Basic auth (Xero requires this).
_PROVIDER_CONFIG = {
    "gmail": (
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "GMAIL_REDIRECT_URI",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly",
        "form",
    ),
    "google-calendar": (
        "GOOGLE_CAL_CLIENT_ID",
        "GOOGLE_CAL_CLIENT_SECRET",
        "GOOGLE_CAL_REDIRECT_URI",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/auth/calendar.events",
        "form",
    ),
    "google-drive": (
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "GOOGLE_DRIVE_REDIRECT_URI",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/auth/drive.file",
        "form",
    ),
    "google-sheets": (
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "GOOGLE_SHEETS_REDIRECT_URI",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/auth/spreadsheets",
        "form",
    ),
    "slack": (
        "SLACK_CLIENT_ID",
        "SLACK_CLIENT_SECRET",
        "SLACK_REDIRECT_URI",
        "https://slack.com/oauth/v2/authorize",
        "https://slack.com/api/oauth.v2.access",
        "channels:read chat:write",
        "form",
    ),
    "outlook": (
        "OUTLOOK_CLIENT_ID",
        "OUTLOOK_CLIENT_SECRET",
        "OUTLOOK_REDIRECT_URI",
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "Mail.Read Mail.Send offline_access",
        "form",
    ),
    "microsoft365": (
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_CLIENT_SECRET",
        "MICROSOFT_REDIRECT_URI",
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "Calendars.ReadWrite Mail.ReadWrite Tasks.ReadWrite offline_access",
        "form",
    ),
    "onedrive": (
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_CLIENT_SECRET",
        "ONEDRIVE_REDIRECT_URI",
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "Files.ReadWrite offline_access",
        "form",
    ),
    "zoho": (
        "ZOHO_CLIENT_ID",
        "ZOHO_CLIENT_SECRET",
        "ZOHO_REDIRECT_URI",
        "https://accounts.zoho.com/oauth/v2/auth",
        "https://accounts.zoho.com/oauth/v2/token",
        "ZohoCRM.modules.leads.ALL ZohoCRM.modules.contacts.ALL ZohoCRM.modules.deals.ALL",
        "form",
    ),
    "xero": (
        "XERO_CLIENT_ID",
        "XERO_CLIENT_SECRET",
        "XERO_REDIRECT_URI",
        "https://login.xero.com/identity/connect/authorize",
        "https://identity.xero.com/connect/token",
        "openid profile email accounting.transactions accounting.contacts accounting.settings offline_access",
        "basic",
    ),
}


def get_provider_config(provider: str) -> dict | None:
    cfg = _PROVIDER_CONFIG.get(provider)
    if cfg is None:
        return None
    cid, secret, redirect, auth_url, token_url, scope, token_auth = cfg
    if not getattr(settings, cid, None):
        return None
    # Zoho OAuth clients are bound to the data center where they were created
    # AND where the signed-in account lives. Non-US centers (eu / in / com.au /
    # jp / sa) use accounts.zoho.<dc> for auth + token; the CRM API base is
    # resolved per data center in the zoho client as well.
    if provider == "zoho":
        dc = (settings.ZOHO_DATA_CENTER or "com").strip().lower()
        if dc != "com":
            auth_url = f"https://accounts.zoho.{dc}/oauth/v2/auth"
            token_url = f"https://accounts.zoho.{dc}/oauth/v2/token"
    # Xero rejects any scope the app hasn't enabled with "invalid_scope" on its
    # own authorize page — make the requested list configurable so it can match
    # what is enabled in developer.xero.com > My Apps.
    if provider == "xero":
        scope = settings.XERO_SCOPES or scope
    return {
        "client_id": getattr(settings, cid),
        "client_secret": getattr(settings, secret),
        "redirect_uri": getattr(settings, redirect),
        "auth_url": auth_url,
        "token_url": token_url,
        "scope": scope,
        "token_auth": token_auth or "form",
    }


def build_authorize_url(provider: str, state: str) -> str:
    cfg = get_provider_config(provider)
    if cfg is None:
        raise ValueError("provider not configured")
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": cfg["scope"],
        "state": state,
    }
    # access_type/prompt are supported by Google AND Zoho (both require
    # access_type=offline to issue a refresh token); other providers reject
    # the extra params (Xero/Slack/Microsoft handle offline via scope). Match
    # on "zoho" (not "zoho.com") so region URLs like accounts.zoho.in still
    # get the offline grant.
    if "accounts.google.com" in cfg["auth_url"] or "zoho" in cfg["auth_url"]:
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    return f"{cfg['auth_url']}?{urlencode(params)}"


async def exchange_code(provider: str, code: str) -> dict:
    cfg = get_provider_config(provider)
    if cfg is None:
        raise ValueError("provider not configured")
    data = {
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri": cfg["redirect_uri"],
        "grant_type": "authorization_code",
        "code": code,
    }
    # Slack's oauth.v2.access does not accept a grant_type field (it would
    # reply invalid_arguments); the other providers require it.
    if provider == "slack":
        data.pop("grant_type", None)
    kwargs = {}
    if cfg.get("token_auth") == "basic":
        # Xero authenticates the token endpoint with HTTP Basic credentials.
        kwargs["auth"] = (cfg["client_id"], cfg["client_secret"])
        data.pop("client_id", None)
        data.pop("client_secret", None)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(cfg["token_url"], data=data, **kwargs)
    if resp.status_code >= 300:
        raise RuntimeError(f"token exchange failed: {resp.status_code} {resp.text[:200]}")
    payload = resp.json()
    # Slack reports errors as HTTP 200 with {"ok": false, ...}; Zoho may
    # return 200 with an "error" field. Detect both so the OAuth callback
    # redirects to a clean error instead of crashing on a 200 body.
    if isinstance(payload, dict) and (payload.get("ok") is False or payload.get("error")):
        raise RuntimeError(f"token exchange failed: {str(payload)[:200]}")
    return payload


def save_credentials(
    db,
    organization_id,
    provider: str,
    tokens: dict,
    metadata: dict | None = None,
) -> Integration:
    """Upsert encrypted credentials for an org/provider pair."""
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
            connected=True,
        )
        db.add(row)

    row.access_token = encrypt_value(tokens.get("access_token"))
    # Only overwrite the refresh token when the payload actually contains one.
    # Refresh responses routinely omit it (access-token rotation only), and
    # blanking the stored value here would leave the integration unable to
    # refresh after its next access-token rotation — a one-way lockout.
    if tokens.get("refresh_token"):
        row.refresh_token = encrypt_value(tokens["refresh_token"])
    if metadata:
        row.metadata_json = {**(row.metadata_json or {}), **metadata}
    row.connected = True
    db.commit()
    db.refresh(row)
    return row


def disconnect(db, integration: Integration) -> Integration:
    integration.connected = False
    db.commit()
    db.refresh(integration)
    return integration