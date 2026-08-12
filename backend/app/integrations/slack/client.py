"""Slack Web API client built on the stored integration credentials.

Unlike the OAuth-driven Gmail/Outlook clients, Slack posting is done with the
workspace access token stored (encrypted) in the ``integrations`` table under
provider ``slack``. The token is decrypted with ``app.utils.encryption`` and
calls go to the Slack Web API via httpx.
"""
import httpx

from app.integrations.gmail.client import IntegrationNotConnectedError  # noqa: F401  (shared contract)

SLACK_API = "https://slack.com/api/chat.postMessage"


class SlackError(Exception):
    """Raised when Slack rejects a request (API-level error)."""


class SlackClient:
    """Minimal Slack Web API client for posting messages."""

    def __init__(self, *, access_token: str | None, channel: str | None = None):
        self._access_token = access_token
        self._channel = channel

    def post_message(
        self,
        channel: str | None = None,
        text: str = "",
        blocks: list | None = None,
    ) -> dict:
        """Post a message to a Slack channel.

        ``channel`` may be a channel id, a #channel name, or a user id.
        ``blocks`` is an optional Slack Blocks payload for richer messages.
        """
        if not self._access_token:
            raise SlackError("Slack integration is not configured")
        payload = {"channel": channel or self._channel}
        if text:
            payload["text"] = text
        if blocks:
            payload["blocks"] = blocks
        resp = httpx.post(
            SLACK_API,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        if resp.status_code >= 300:
            raise SlackError(f"Slack request failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        if not data.get("ok"):
            raise SlackError(f"Slack error: {data.get('error') or resp.text[:200]}")
        return {"ts": data.get("ts"), "channel": data.get("channel"), "ok": True}
