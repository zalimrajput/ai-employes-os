"""WhatsApp integration helpers: resolve orgs and clients for the webhook.

Tenant isolation happens here: an inbound Meta webhook event carries only a
``phone_number_id``, and we resolve the owning organization through the
``integrations`` table row whose encrypted WhatsApp credentials were stored
under ``provider == "whatsapp"`` with the matching metadata key.
"""
import logging

from app.core.config import settings
from app.integrations.whatsapp.client import (
    WhatsAppClient,
    WhatsAppNotConnectedError,
)
from app.models.integration import Integration
from app.utils.encryption import decrypt_value

logger = logging.getLogger("app.integrations.whatsapp.service")


def resolve_organization_id(db, phone_number_id: str) -> str | None:
    """Return the organization id that owns ``phone_number_id``.

    Scans connected ``whatsapp`` integration rows whose owning organization
    still exists (inner join drops orphaned rows left behind by deleted
    orgs, so stale data can never hijack webhook routing). A given phone
    number maps to exactly one tenant; the oldest match wins deterministically.
    """
    from app.models.organization import Organization

    rows = (
        db.query(Integration)
        .join(Organization, Organization.id == Integration.organization_id)
        .filter(
            Integration.provider == "whatsapp",
            Integration.connected.is_(True),
        )
        .order_by(Integration.created_at.asc(), Integration.id.asc())
        .all()
    )
    wanted = str(phone_number_id)
    for row in rows:
        if str((row.metadata_json or {}).get("phone_number_id") or "") == wanted:
            return row.organization_id
    return None


def get_client(
    db,
    organization_id: str,
    *,
    phone_number_id: str | None = None,
) -> WhatsAppClient:
    """Resolve the org's connected WhatsApp integration into a client.

    Raises ``WhatsAppNotConnectedError`` when no connected ``whatsapp``
    integration exists for the organization.
    """
    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == organization_id,
            Integration.provider == "whatsapp",
            Integration.connected.is_(True),
        )
        .first()
    )

    def _raise():
        raise WhatsAppNotConnectedError(
            "No connected WhatsApp integration for this organization"
        )

    if row is None:
        _raise()

    token = decrypt_value(row.access_token)
    if not token:
        # Fall back to the platform-level credential only when no per-org
        # token is stored (e.g. single-tenant deployments).
        token = settings.WHATSAPP_API_TOKEN
    if not token:
        _raise()

    pnid = (
        phone_number_id
        or (row.metadata_json or {}).get("phone_number_id")
        or settings.WHATSAPP_PHONE_ID
    )
    if not pnid:
        _raise()

    return WhatsAppClient(api_token=token, phone_number_id=str(pnid))


def get_or_create_contact(db, organization_id, phone_number: str, name: str | None = None):
    """Create-or-fetch the WhatsApp contact for a phone in an org."""
    from app.models.whatsapp import WhatsAppContact

    phone_number = str(phone_number or "").replace(" ", "")
    contact = (
        db.query(WhatsAppContact)
        .filter(
            WhatsAppContact.organization_id == organization_id,
            WhatsAppContact.phone == phone_number,
        )
        .first()
    )
    if contact is None:
        contact = WhatsAppContact(
            organization_id=organization_id,
            phone=phone_number,
            name=name,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
    return contact