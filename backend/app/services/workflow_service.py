"""Invoice-paid workflow automation.

Runs the PDF's named chain when an invoice is marked paid:
Customer Pays Invoice -> Receipt -> Update CRM -> Notify Sales -> Thank You
Email -> Schedule Follow-up.

Every step is best-effort: a failure in one step is logged and never blocks
the others (same resilience pattern used throughout the codebase). The
function is safe to call repeatedly — it does NOT mutate invoice status (the
caller owns the status transition), so re-calls would happily re-run; callers
must guard against re-triggering by checking the old status themselves.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger("app.services.workflow")

FOLLOWUP_DAYS = 30


def on_invoice_paid(db: Session, organization_id, invoice_id) -> dict:
    """Run the post-payment workflow for an invoice.

    Returns per-step success flags, e.g.
    ``{"receipt": true, "crm_logged": true, "notified": true,
    "email_sent": false, "reminder_created": true}``.
    """
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.reminder import Reminder

    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.organization_id == organization_id)
        .first()
    )
    if invoice is None:
        return {
            "receipt": False,
            "crm_logged": False,
            "notified": False,
            "email_sent": False,
            "reminder_created": False,
            "error": "Invoice not found",
        }

    customer = None
    if invoice.customer_id is not None:
        customer = (
            db.query(Customer)
            .filter(Customer.id == invoice.customer_id)
            .first()
        )

    number = invoice.invoice_number or str(invoice.id)
    customer_name = customer.name if customer is not None else "the customer"
    customer_email = customer.email if customer is not None else None

    result = {}

    # a. Receipt: reuse the existing invoice PDF generation; no separate
    #    template needed. Returns the stored document size (best-effort).
    result["receipt"] = _step(
        "receipt",
        lambda: _store_receipt(db, organization_id, invoice_id, number),
    )

    # b. Update CRM — log an activity on the linked customer.
    result["crm_logged"] = _step(
        "crm_logged",
        lambda: _log_crm_activity(db, organization_id, invoice, customer),
    )

    # c. Notify sales team.
    result["notified"] = _step(
        "notified",
        lambda: _notify_sales(db, organization_id, number, customer_name),
    )

    # d. Thank-you email (skip gracefully when Gmail not connected).
    result["email_sent"] = _step(
        "email_sent",
        lambda: _send_thank_you_email(
            db, organization_id, customer_email, number, customer_name
        ),
    )

    # e. Schedule a follow-up reminder 30 days out.
    result["reminder_created"] = _step(
        "reminder_created",
        lambda: _schedule_followup(db, organization_id, invoice, customer_name),
    )

    return result


def _step(name: str, fn) -> bool:
    try:
        return bool(fn())
    except Exception:  # noqa: BLE001 - one step must never block the chain
        logger.exception("workflow step %r failed", name)
        return False


def _store_receipt(db, organization_id, invoice_id, number):
    """Generate and persist a receipt PDF copy. Returns bytes written or False."""
    from app.services import invoice_service

    buffer = invoice_service.generate_invoice_pdf(db, organization_id, invoice_id)
    data = buffer.getvalue()
    if not data:
        return False

    from pathlib import Path

    out_dir = Path(__file__).resolve().parent.parent / "generated_documents"
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"receipt_{invoice_id}.pdf"
    (out_dir / filename).write_bytes(data)
    return len(data) > 0


def _log_crm_activity(db, organization_id, invoice, customer):
    from app.models.activity import Activity

    number = invoice.invoice_number or str(invoice.id)
    if customer is None:
        # No customer to attach the activity to; use the invoice as the entity.
        entity_type, entity_id = "invoice", invoice.id
    else:
        entity_type, entity_id = "customer", customer.id

    row = Activity(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=f"Invoice {number} paid",
        metadata_json={"invoice_id": str(invoice.id), "status": "paid"},
    )
    db.add(row)
    db.commit()
    return row.id is not None


def _notify_sales(db, organization_id, invoice_number, customer_name):
    from app.services.notification_service import create_notification

    note = create_notification(
        db,
        organization_id,
        None,  # org-wide notification to the sales team
        title="Invoice paid",
        message=(
            f"Invoice {invoice_number} paid by {customer_name} — receipt "
            "generated and follow-up scheduled."
        ),
    )

    # Best-effort Slack post when the org has Slack connected (never blocks
    # the workflow if Slack is missing or the API call fails).
    try:
        from app.integrations.slack.service import post_message as slack_post

        slack_post(
            db,
            organization_id,
            text=(
                f":tada: Invoice {invoice_number} paid by {customer_name} — "
                "receipt generated and follow-up scheduled."
            ),
        )
    except Exception:  # noqa: BLE001 - Slack is optional
        logger.info("slack post skipped (not connected or failed)")

    return note.id is not None


def _send_thank_you_email(db, organization_id, customer_email, invoice_number, customer_name):
    if not customer_email:
        logger.info("no customer email; skipping thank-you email")
        return False

    from app.integrations.gmail.service import get_client

    try:
        client = get_client(db, organization_id)
    except Exception as exc:
        # not connected / auth not ready — skip gracefully, never block chain
        logger.info("gmail not connected; skipping thank-you email: %s", exc)
        return False

    client.send_email(
        to=customer_email,
        subject=f"Thank you {customer_name}",
        body=(
            f"Hi {customer_name},\n\nThank you for your recent payment "
            f"(invoice {invoice_number}). We appreciate your business."
        ),
    )
    return True


def _schedule_followup(db, organization_id, invoice, customer_name):
    from app.models.reminder import Reminder

    remind_at = datetime.now(timezone.utc) + timedelta(days=FOLLOWUP_DAYS)
    reminder = Reminder(
        organization_id=organization_id,
        target_type="deal",
        target_id=None,  # follow-up is on the customer, not a specific deal
        remind_at=remind_at,
        message=f"Check in on {customer_name} post-purchase.",
    )
    db.add(reminder)
    db.commit()
    return reminder.id is not None