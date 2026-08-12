"""Create the live-payment fixture and a real Stripe Checkout link.

Leaves the DB rows in place (deleted by _finish_live_pay.py after the payment).
"""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, ".")

from app.core.database import SessionLocal  # noqa: E402
from app.ai.tools.invoice_tools import INVOICE_TOOLS  # noqa: E402

db = SessionLocal()

from app.models.customer import Customer  # noqa: E402
from app.models.invoice import Invoice  # noqa: E402
from app.models.organization import Organization  # noqa: E402

org = Organization(name="Live Pay E2E", slug=f"pay-{uuid.uuid4().hex[:8]}", settings={})
db.add(org)
db.commit()
db.refresh(org)
customer = Customer(organization_id=org.id, name="Live Pay Customer", email=None)
db.add(customer)
db.commit()
db.refresh(customer)
invoice = Invoice(
    organization_id=org.id,
    customer_id=customer.id,
    invoice_number=f"INV-LIVE-{uuid.uuid4().hex[:6].upper()}",
    amount="199.00",
    status="unpaid",
)
db.add(invoice)
db.commit()
db.refresh(invoice)

result = INVOICE_TOOLS["generate_invoice_payment_link"].handler(
    db, org.id, None, {"invoice_id": str(invoice.id)}
)
pay_url = result.get("payment_link_url", "")
qr_url = result.get("qr_code_url", "")
print("CHECKOUT_URL:", pay_url)
print("INVOICE_ID:", invoice.id)
print("ORG_ID:", org.id)
print("INVOICE_NUMBER:", invoice.invoice_number)
print("QR_URL:", qr_url)

Path("_live_pay_state.json").write_text(
    json.dumps({
        "org_id": str(org.id),
        "invoice_id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "qr_basename": qr_url.split("/")[-1] if qr_url else None,
    }),
    encoding="utf-8",
)
db.close()
