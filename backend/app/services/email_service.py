"""Email sending.

Sends best-effort via the org's Gmail integration when available, otherwise
falls back to a Celery task that attempts the configured provider.  Never
blocks a request: dispatch is asynchronous by default.
"""
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.email import Email, EmailThread
from app.models.integration import Integration
from app.utils.encryption import decrypt_value

logger = logging.getLogger("app.email")


def get_gmail_credentials(db: Session, organization_id) -> dict | None:
    """Decrypted Gmail OAuth tokens for an org, when a live integration exists."""
    row = (
        db.query(Integration)
        .filter(
            Integration.organization_id == organization_id,
            Integration.provider == "gmail",
            Integration.connected.is_(True),
        )
        .first()
    )
    if row is None:
        return None
    return {
        "access_token": decrypt_value(row.access_token),
        "refresh_token": decrypt_value(row.refresh_token),
    }


def send_email(
    db: Session,
    organization_id,
    to_email: str,
    subject: str,
    body: str,
    thread_id=None,
    record_thread: bool = True,
) -> dict:
    """Create an outgoing Email row and dispatch delivery to the worker."""
    result = {
        "queued": True,
        "provider": None,
        "thread_id": str(thread_id) if thread_id else None,
    }

    if record_thread:
        if thread_id is None:
            thread = EmailThread(
                organization_id=organization_id,
                subject=subject,
                participants={"to": [to_email]},
            )
            db.add(thread)
            db.flush()
            thread_id = thread.id

        email_row = Email(
            organization_id=organization_id,
            thread_id=thread_id,
            sender=None,
            receiver=to_email,
            body=body,
            direction="outbound",
            ai_generated=False,
        )
        db.add(email_row)
        db.commit()
        db.refresh(email_row)
        result["email_id"] = str(email_row.id)

    try:
        from workers.email_worker import send_email_task

        send_email_task.delay(
            organization_id=str(organization_id),
            to_email=to_email,
            subject=subject,
            body=body,
            thread_id=str(thread_id) if thread_id else None,
        )
        result["queued"] = True
    except Exception:
        # Redis/Celery not running: the Email row is kept (sent_at stays NULL)
        # so the failed attempt is visible, but the caller must not believe
        # the email was queued.
        logger.exception("failed to enqueue email task")
        result["queued"] = False
        result["error"] = (
            "Email queue unavailable — the Celery worker is not running. "
            "Start Redis + the worker to deliver emails."
        )

    return result