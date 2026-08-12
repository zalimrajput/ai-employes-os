from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.v1._crud import crud_router
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.subscription import BillingTransaction, Plan, Subscription


router = APIRouter(
    prefix="/billing",
    tags=["Billing"]
)


@router.get("/plans")
# Public catalog: subscription plans are platform-level, not tenant-scoped.
def list_plans(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return (
        db.query(Plan)
        .order_by(Plan.price_monthly)
        .all()
    )


router.include_router(
    crud_router(
        Subscription,
        prefix="/subscriptions",
        tags=["Billing"],
        search_fields=["status"],
    )
)


router.include_router(
    crud_router(
        BillingTransaction,
        prefix="/transactions",
        tags=["Billing"],
    )
)


@router.post("/stripe/webhook")
# Public endpoint: Stripe signs every payload; verifies via the webhook secret.
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("stripe-signature", "")
    # Each Stripe webhook endpoint has its own signing secret; fall back to the
    # invoice webhook secret when STRIPE_BILLING_WEBHOOK_SECRET is not set.
    webhook_secret = (
        getattr(settings, "STRIPE_BILLING_WEBHOOK_SECRET", None)
        or getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    )
    if webhook_secret:
        try:
            import stripe

            stripe.api_key = settings.STRIPE_SECRET_KEY or ""
            event = stripe.Webhook.construct_event(body, signature, webhook_secret)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        try:
            event = __import__("json").loads(body)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("type") if isinstance(event, dict) else event.type
    event_data = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event.data.object

    org_id = event_data.get("metadata", {}).get("organization_id") if isinstance(event_data, dict) else None
    if not org_id:
        return {"received": True, "type": event_type, "applied": False}
    subscription = (
        db.query(Subscription)
        .filter(Subscription.organization_id == org_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if subscription:
        if event_type.startswith("customer.subscription.updated"):
            subscription.status = "active"
        elif event_type.startswith("customer.subscription.deleted"):
            subscription.status = "canceled"
        subscription.external_subscription_id = event_data.get("id") or subscription.external_subscription_id
        subscription.payment_provider = "stripe"
        db.commit()

    transaction = BillingTransaction(
        organization_id=org_id,
        subscription_id=subscription.id if "subscription" in locals() and subscription else None,
        amount=event_data.get("amount_total") if isinstance(event_data, dict) else None,
        currency=(event_data.get("currency") or "usd").upper()
        if isinstance(event_data, dict) else "USD",
        payment_status="succeeded",
        payment_provider="stripe",
        transaction_reference=event_data.get("payment_intent") if isinstance(event_data, dict) else None,
        paid_at=None,
    )
    db.add(transaction)
    db.commit()
    return {"received": True, "type": event_type}
