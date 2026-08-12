"""Lookup helper: resolve a connected Xero integration into a client."""

from app.integrations.gmail.client import IntegrationNotConnectedError
from app.integrations.xero.client import XERO_API_BASE, XERO_TOKEN_URL, XeroClient
from app.models.integration import Integration
from app.services.integration_service import get_provider_config
from app.utils.encryption import decrypt_value


def get_client(db, organization_id) -> XeroClient:
    """Return a XeroClient for the org's connected Xero integration.

    Raises ``IntegrationNotConnectedError`` when no connected ``xero``
    integration row exists for the organization.
    """
    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == organization_id,
            Integration.provider == "xero",
            Integration.connected.is_(True),
        )
        .first()
    )
    if row is None:
        raise IntegrationNotConnectedError(
            "No connected Xero integration for this organization"
        )

    cfg = get_provider_config("xero") or {}
    return XeroClient(
        db=db,
        organization_id=organization_id,
        access_token=decrypt_value(row.access_token),
        refresh_token=decrypt_value(row.refresh_token),
        client_id=cfg.get("client_id"),
        client_secret=cfg.get("client_secret"),
        token_url=cfg.get("token_url") or XERO_TOKEN_URL,
        api_base=XERO_API_BASE,
        tenant_id=(row.metadata_json or {}).get("xero_tenant_id"),
    )
