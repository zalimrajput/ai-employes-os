"""Lookup helper: resolve a connected OneDrive integration into a client."""

from app.integrations.gmail.client import IntegrationNotConnectedError
from app.integrations.onedrive.client import (
    OAUTH_TOKEN_URL,
    OneDriveClient,
)
from app.models.integration import Integration
from app.services.integration_service import get_provider_config
from app.utils.encryption import decrypt_value


def get_client(db, organization_id) -> OneDriveClient:
    """Return a OneDriveClient for the org's connected OneDrive integration.

    Raises ``IntegrationNotConnectedError`` when no connected ``onedrive``
    integration row exists for the organization.
    """
    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == organization_id,
            Integration.provider == "onedrive",
            Integration.connected.is_(True),
        )
        .first()
    )
    if row is None:
        raise IntegrationNotConnectedError(
            "No connected OneDrive integration for this organization"
        )

    cfg = get_provider_config("onedrive") or {}
    return OneDriveClient(
        db=db,
        organization_id=organization_id,
        access_token=decrypt_value(row.access_token),
        refresh_token=decrypt_value(row.refresh_token),
        client_id=cfg.get("client_id"),
        client_secret=cfg.get("client_secret"),
        token_url=cfg.get("token_url") or OAUTH_TOKEN_URL,
        scope=cfg.get("scope"),
    )
