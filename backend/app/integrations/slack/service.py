"""Lookup helper: resolve a connected Slack integration into a client."""

from app.core.config import settings
from app.integrations.gmail.client import IntegrationNotConnectedError
from app.integrations.slack.client import SlackClient
from app.models.integration import Integration
from app.utils.encryption import decrypt_value


def get_client(db, organization_id, channel: str | None = None) -> SlackClient:
    """Return a SlackClient for the org's connected Slack integration.

    Raises ``IntegrationNotConnectedError`` when no connected ``slack``
    integration row exists for the organization.
    """
    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == organization_id,
            Integration.provider == "slack",
            Integration.connected.is_(True),
        )
        .first()
    )
    if row is None:
        raise IntegrationNotConnectedError(
            "No connected Slack integration for this organization"
        )
    return SlackClient(
        access_token=decrypt_value(row.access_token),
        channel=channel,
    )


def _bot_client(channel: str | None = None) -> SlackClient | None:
    """Build a client from the global SLACK_BOT_TOKEN, if configured."""
    if not settings.SLACK_BOT_TOKEN:
        return None
    return SlackClient(access_token=settings.SLACK_BOT_TOKEN, channel=channel)


def post_message(db, organization_id, text: str, channel: str | None = None) -> dict | None:
    """Post a message to Slack; returns None when nothing is configured.

    Best-effort helper for workflow/notification hooks — never raises for a
    missing integration, only for a genuine Slack API failure (which callers
    should treat as non-fatal). Uses the org's connected OAuth token when
    available, otherwise falls back to the global SLACK_BOT_TOKEN so Slack
    works before the Connect flow is completed.
    """
    try:
        client = get_client(db, organization_id, channel=channel)
    except IntegrationNotConnectedError:
        client = _bot_client(channel=channel)
        if client is None:
            return None
    return client.post_message(text=text, channel=channel)


def is_connected(db, organization_id) -> bool:
    """Whether the org has a connected Slack integration (no token access)."""
    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == organization_id,
            Integration.provider == "slack",
            Integration.connected.is_(True),
        )
        .first()
    )
    return row is not None
