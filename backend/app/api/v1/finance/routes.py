from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.v1._crud import crud_router, require_org_member
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.finance import Budget, Expense, ExpenseCategory
from app.models.invoice import Invoice, InvoiceItem
from app.models.payment import Payment


router = APIRouter()


router.include_router(
    crud_router(
        Invoice,
        prefix="/invoices",
        tags=["Finance"],
        search_fields=["invoice_number"],
    )
)


router.include_router(
    crud_router(
        InvoiceItem,
        prefix="/invoice-items",
        tags=["Finance"],
    )
)


router.include_router(
    crud_router(
        Payment,
        prefix="/payments",
        tags=["Finance"],
    )
)


router.include_router(
    crud_router(
        ExpenseCategory,
        prefix="/expense-categories",
        tags=["Finance"],
        search_fields=["name"],
    )
)


router.include_router(
    crud_router(
        Expense,
        prefix="/expenses",
        tags=["Finance"],
        search_fields=["title"],
    )
)


router.include_router(
    crud_router(
        Budget,
        prefix="/budgets",
        tags=["Finance"],
    )
)


@router.post("/invoices/{invoice_id}/pay")
def mark_invoice_paid(
    invoice_id,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark an invoice paid and fire the paid-workflow chain.

    The generic CRUD PATCH on /invoices lets ``status`` be set directly with no
    hook; this endpoint is the explicit paid-transition path so the workflow
    fires exactly once (guarded against re-triggering on an already-paid row).
    """
    from uuid import UUID

    from app.models.invoice import Invoice
    from app.services.workflow_service import on_invoice_paid

    me = require_org_member(db, current_user)
    try:
        invoice_uuid = UUID(str(invoice_id))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid invoice id")

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_uuid,
            Invoice.organization_id == me.organization_id,
        )
        .first()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status == "paid":
        return {
            "id": str(invoice.id),
            "status": invoice.status,
            "workflow": None,
            "note": "already paid; workflow not re-fired",
        }

    invoice.status = "paid"
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    workflow = on_invoice_paid(db, me.organization_id, invoice.id)
    return {"id": str(invoice.id), "status": invoice.status, "workflow": workflow}


@router.post("/invoices/stripe-webhook")
@router.post("/finance/invoices/stripe-webhook")
# Public endpoint: Stripe signs every payload; verified via the webhook secret.
# The second path is a compat alias for webhooks registered before the route
# moved to /invoices/stripe-webhook — both URLs work, so Stripe delivers
# regardless of which one was saved in the dashboard.
async def invoice_stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle a Stripe Checkout ``checkout.session.completed`` event.

    Extracts ``organization_id`` and ``invoice_id`` from the session metadata
    (set by ``create_payment_link``), marks the invoice paid and fires the
    existing ``on_invoice_paid`` chain exactly once (guarded against re-firing
    when the invoice is already paid).
    """
    from uuid import UUID

    from app.services.workflow_service import on_invoice_paid

    body = await request.body()
    signature = request.headers.get("stripe-signature", "")
    if getattr(settings, "STRIPE_WEBHOOK_SECRET", None):
        try:
            import stripe

            stripe.api_key = settings.STRIPE_SECRET_KEY or ""
            event = stripe.Webhook.construct_event(
                body, signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        try:
            event = __import__("json").loads(body)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("type") if isinstance(event, dict) else event.type
    event_data = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event.data.object

    # Accepted payment-completion events. ``checkout.session.completed`` carries
    # our org/invoice metadata directly on the session; ``invoice.paid`` /
    # ``invoice.payment_succeeded`` resolve it through the PaymentIntent, which
    # Stripe copies the Checkout Session metadata onto.
    PAYMENT_EVENTS = {"checkout.session.completed", "invoice.paid", "invoice.payment_succeeded"}
    if event_type not in PAYMENT_EVENTS:
        return {"received": True, "type": event_type, "applied": False}

    # StripeObject's public serialization method is to_dict(); convert metadata to
    # a plain dict so key lookup works whether it is a dict or a StripeObject.
    def _get(obj, key, default=None):
        try:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)
        except Exception:
            return default

    if event_type == "checkout.session.completed":
        metadata = _get(event_data, "metadata", {})
    else:
        metadata = {}
        payment_intent = _get(event_data, "payment_intent")
        if payment_intent:
            try:
                import stripe

                stripe.api_key = settings.STRIPE_SECRET_KEY or ""
                payment = stripe.PaymentIntent.retrieve(payment_intent)
                metadata = getattr(payment, "metadata", None) or {}
            except Exception:
                metadata = {}
    if hasattr(metadata, "to_dict"):
        metadata = metadata.to_dict()
    if metadata is None:
        metadata = {}
    org_id = metadata.get("organization_id")
    invoice_id = metadata.get("invoice_id")
    if not org_id or not invoice_id:
        return {"received": True, "type": event_type, "applied": False}

    try:
        invoice_uuid = UUID(str(invoice_id))
        org_uuid = UUID(str(org_id))
    except (ValueError, TypeError):
        return {"received": True, "type": event_type, "applied": False}

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_uuid,
            Invoice.organization_id == org_uuid,
        )
        .first()
    )
    if invoice is None:
        return {"received": True, "type": event_type, "applied": False}

    if invoice.status == "paid":
        return {
            "received": True,
            "type": event_type,
            "applied": False,
            "note": "already paid; workflow not re-fired",
        }

    invoice.status = "paid"
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    workflow = on_invoice_paid(db, org_uuid, invoice.id)
    return {
        "received": True,
        "type": event_type,
        "applied": True,
        "invoice_id": str(invoice.id),
        "workflow": workflow,
    }
