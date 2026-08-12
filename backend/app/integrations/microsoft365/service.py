"""Lookup helper: resolve a connected Microsoft 365 integration into a client."""

from app.integrations.gmail.client import IntegrationNotConnectedError
from app.integrations.microsoft365.client import (
    OAUTH_TOKEN_URL,
    Microsoft365Client,
)
from app.models.integration import Integration
from app.utils.encryption import decrypt_value


def get_client(db, organization_id) -> Microsoft365Client:
    """Return a Microsoft365Client for the org's connected integration.

    Raises ``IntegrationNotConnectedError`` when no connected ``microsoft365``
    integration row exists for the organization.
    """
    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == organization_id,
            Integration.provider == "microsoft365",
            Integration.connected.is_(True),
        )
        .first()
    )
    if row is None:
        raise IntegrationNotConnectedError(
            "No connected Microsoft 365 integration for this organization"
        )

    from app.services.integration_service import get_provider_config

    cfg = get_provider_config("microsoft365") or {}
    return Microsoft365Client(
        db=db,
        organization_id=organization_id,
        access_token=decrypt_value(row.access_token),
        refresh_token=decrypt_value(row.refresh_token),
        client_id=cfg.get("client_id"),
        client_secret=cfg.get("client_secret"),
        token_url=cfg.get("token_url") or OAUTH_TOKEN_URL,
        scope=cfg.get("scope"),
    )
