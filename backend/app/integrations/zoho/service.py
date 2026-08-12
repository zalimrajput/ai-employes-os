"""Lookup helper: resolve a connected Zoho integration into a client."""

from app.core.config import settings
from app.integrations.gmail.client import IntegrationNotConnectedError
from app.integrations.zoho.client import ZOHO_API_BASE, ZOHO_AUTH_TOKEN_URL, ZohoCRMClient
from app.models.integration import Integration
from app.services.integration_service import get_provider_config
from app.utils.encryption import decrypt_value


def _zoho_api_base() -> str:
    """CRM API base for the configured data center (zoho.in / zoho.eu / ...)."""
    dc = (settings.ZOHO_DATA_CENTER or "com").strip()
    if dc and dc != "com":
        return f"https://www.zohoapis.{dc}/crm/v2"
    return ZOHO_API_BASE


def get_client(db, organization_id) -> ZohoCRMClient:
    """Return a ZohoCRMClient for the org's connected Zoho integration.

    Raises ``IntegrationNotConnectedError`` when no connected ``zoho``
    integration row exists for the organization.
    """
    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == organization_id,
            Integration.provider == "zoho",
            Integration.connected.is_(True),
        )
        .first()
    )
    if row is None:
        raise IntegrationNotConnectedError(
            "No connected Zoho integration for this organization"
        )

    cfg = get_provider_config("zoho") or {}
    return ZohoCRMClient(
        db=db,
        organization_id=organization_id,
        access_token=decrypt_value(row.access_token),
        refresh_token=decrypt_value(row.refresh_token),
        client_id=cfg.get("client_id"),
        client_secret=cfg.get("client_secret"),
        token_url=cfg.get("token_url") or ZOHO_AUTH_TOKEN_URL,
        api_base=settings.ZOHO_API_BASE_URL or _zoho_api_base(),
    )
