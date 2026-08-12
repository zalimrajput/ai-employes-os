"""Transactional email worker.

Sends email best-effort through the org's connected email provider: Gmail
first, then Outlook (Microsoft Graph), then Microsoft 365. Each client
handles attachments and 401 token refresh. When no email integration is
connected the task records the attempt and returns a benign result so the
caller's flow never fails. Runs under Celery.
"""
import importlib
import logging

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.integrations.gmail.client import IntegrationAuthError, IntegrationNotConnectedError
from workers.celery_app import celery_app

logger = logging.getLogger("workers.email")

# Provider modules tried in order; the first with a connected integration wins.
# Resolved via importlib at call time so tests can monkeypatch the service
# module attributes.
_EMAIL_PROVIDER_MODULES = [
    ("gmail", "app.integrations.gmail.service"),
    ("outlook", "app.integrations.outlook.service"),
    ("microsoft365", "app.integrations.microsoft365.service"),
]


@celery_app.task(name="workers.send_email", bind=True, max_retries=3)
def send_email_task(
    self,
    organization_id: str,
    to_email: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
):
    from app.models.email import Email

    db: Session = SessionLocal()
    try:
        client = None
        used_provider = None
        for provider, module_name in _EMAIL_PROVIDER_MODULES:
            try:
                module = importlib.import_module(module_name)
                client = module.get_client(db, organization_id)
                used_provider = provider
                break
            except IntegrationNotConnectedError:
                continue
        if client is None:
            logger.info("no email integration connected; skipping send for %s", to_email)
            return {"queued": True, "delivered": False, "reason": "no integration"}

        client.send_email(to=to_email, subject=subject, body=body)
        logger.info("email delivered via %s to %s", used_provider, to_email)

        if thread_id:
            email_row = (
                db.query(Email)
                .filter(Email.id == thread_id, Email.organization_id == organization_id)
                .first()
            )
            if email_row is not None:
                email_row.ai_generated = False
                db.commit()
        return {"queued": True, "delivered": True, "provider": used_provider}
    except IntegrationAuthError as exc:
        logger.error("email auth failed for %s: %s", to_email, exc)
        return {"queued": True, "delivered": False, "reason": "auth_error"}
    except Exception as exc:
        logger.exception("email task failed; will retry")
        raise self.retry(exc=exc)
    finally:
        db.close()