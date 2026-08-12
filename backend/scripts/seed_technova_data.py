"""Seed TechNova Solution (org 88f45e8f-73f3-4b9a-b247-a1c826c08311) with
customers, leads, and quotations (+ line items). Idempotent: skips a table
when the org already has rows in it.

Run:  python scripts/seed_technova_data.py
"""
import json
import os
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from sqlalchemy import create_engine, text


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip(chr(34)).strip(chr(39)))


load_env(".env")
url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
engine = create_engine(url)

ORG_ID = "88f45e8f-73f3-4b9a-b247-a1c826c08311"


def line_total(quantity, unit_price, tax_rate=0, discount=0):
    gross = Decimal(quantity) * Decimal(str(unit_price))
    discounted = gross * (Decimal("1") - Decimal(str(discount)) / Decimal("100"))
    return (discounted * (Decimal("1") + Decimal(str(tax_rate)) / Decimal("100"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def doc_totals(items, doc_tax=0, doc_discount=0):
    """Mirror app.ai.tools.invoice_tools._create_quotation math."""
    subtotal = Decimal("0.00")
    total = Decimal("0.00")
    rows = []
    for order, it in enumerate(items):
        qty = int(it["quantity"])
        price = Decimal(str(it["unit_price"]))
        tax = Decimal(str(it.get("tax_rate", doc_tax)))
        disc = Decimal(str(it.get("discount", doc_discount)))
        gross = Decimal(qty) * price
        subtotal += gross
        lt = line_total(qty, price, tax, disc)
        total += lt
        rows.append(
            dict(
                description=it["description"],
                quantity=qty,
                unit_price=price,
                tax_rate=tax,
                discount=disc,
                line_total=lt,
                sort_order=order,
            )
        )
    return rows, subtotal.quantize(Decimal("0.01")), total.quantize(Decimal("0.01"))


CUSTOMERS = [
    ("John Smith", "john.smith@acmecorp.com", "+1-512-555-0110", "Acme Corporation", "1 Enterprise Way, Austin, TX 78701", "Key enterprise account — interested in a full CRM rollout.", "active"),
    ("Sarah Johnson", "sarah.johnson@bluepeak.io", "+1-415-555-0142", "BluePeak Industries", "400 Market St, San Francisco, CA 94105", "Managed services + cloud migration prospect.", "active"),
    ("Michael Chen", "michael.chen@northwindlabs.com", "+1-206-555-0177", "Northwind Labs", "88 Harbor Ave, Seattle, WA 98109", "Wants an AI customer-support chatbot for their SaaS platform.", "active"),
    ("Emma Rodriguez", "emma.rodriguez@greentech-energy.com", "+1-303-555-0133", "GreenTech Energy", "12 Solar Rd, Denver, CO 80202", "Evaluating ERP implementation for the manufacturing division.", "active"),
    ("David Kim", "david.kim@vertexmfg.com", "+1-312-555-0166", "Vertex Manufacturing", "750 Industrial Pkwy, Chicago, IL 60616", "Needs legacy data migration + inventory digitization.", "active"),
    ("Priya Patel", "priya.patel@medlinkhealth.com", "+1-617-555-0188", "MedLink Health", "5 CarePoint Plaza, Boston, MA 02115", "Cybersecurity audit & compliance for patient data systems.", "active"),
    ("Ahmed Hassan", "ahmed.hassan@swiftretail.com", "+971-4-555-0199", "Swift Retail Group", "Sheikh Zayed Rd, Dubai, UAE", "POS + inventory management for 40 retail outlets.", "active"),
    ("Lisa Thompson", "lisa.thompson@oceanviewhotels.com", "+1-808-555-0121", "Oceanview Hotels", "2300 Kalakaua Ave, Honolulu, HI 96815", "Booking-system refresh and revenue analytics.", "active"),
]

LEADS = [
    ("Rachel Adams", "rachel.adams@freshbrew.co", "+1-720-555-0211", "FreshBrew Coffee", "Website", "qualified", 72, "basiqazhar827@gmail.com", {"notes": "Needs POS + loyalty integration for 25 locations."}),
    ("Tom Wilson", "tom.wilson@wilsonlogistics.com", "+1-901-555-0234", "Wilson Logistics", "Referral", "contacted", 55, "basiqazhar827@gmail.com", {"notes": "Interested in fleet-tracking dashboard; follow up next week."}),
    ("Nina Petrova", "nina.petrova@orbit-aero.com", "+1-425-555-0247", "Orbit Aerospace", "LinkedIn", "new", 48, "basiqazhar827@gmail.com", {"notes": "Requested product brochure; no call yet."}),
    ("Carlos Mendez", "carlos.mendez@mendezfoods.com", "+52-55-5555-0280", "Mendez Foods", "Trade show", "proposal", 88, "basiqazhar827@gmail.com", {"notes": "Quotation sent for supply-chain module; awaiting decision."}),
    ("Grace Liu", "grace.liu@edusmart.academy", "+1-646-555-0256", "EduSmart Academy", "Cold email", "qualified", 64, "basiqazhar827@gmail.com", {"notes": "Wants student-enrollment CRM; demo scheduled."}),
    ("Omar Farooq", "omar.farooq@gulftech-trading.com", "+971-2-555-0301", "GulfTech Trading", "Website", "new", 35, "hali49537@gmail.com", {"notes": "Enquired about ERP; to be assigned to sales."}),
    ("Hannah Baker", "hannah.baker@bakerlegal.com", "+1-212-555-0320", "Baker Legal Group", "Referral", "contacted", 51, "basiqazhar827@gmail.com", {"notes": "Asked about document automation for the firm."}),
]

QUOTATIONS = [
    (
        "QUO-2026-001", "John Smith", "approved", 0, 0,
        [
            ("Enterprise CRM Suite — 50 user licenses (1 yr)", 50, "120.00", 0, 0),
            ("Implementation & data migration", 1, "2500.00", 0, 0),
            ("Staff training (5 days)", 5, "800.00", 0, 0),
        ],
    ),
    (
        "QUO-2026-002", "Sarah Johnson", "approved", 5, 0,
        [
            ("IT Managed Services (monthly retainer)", 12, "750.00", 5, 0),
            ("Cloud migration setup", 1, "3000.00", 5, 0),
        ],
    ),
    (
        "QUO-2026-003", "Michael Chen", "pending_approval", 5, 3,
        [
            ("AI chatbot design & prototyping", 1, "4000.00", 5, 0),
            ("Chatbot development (custom NLP)", 1, "12000.00", 5, 3),
            ("Deployment & support (3 months)", 3, "2000.00", 5, 0),
        ],
    ),
    (
        "QUO-2026-004", "Emma Rodriguez", "draft", 5, 0,
        [
            ("ERP software license (perpetual)", 1, "25000.00", 5, 0),
            ("Process consulting (hours)", 20, "180.00", 5, 0),
            ("User training sessions", 5, "800.00", 5, 0),
        ],
    ),
    (
        "QUO-2026-005", "David Kim", "rejected", 0, 0,
        [
            ("Legacy data migration service", 1, "6500.00", 0, 0),
            ("Data validation & testing", 1, "1800.00", 0, 0),
        ],
    ),
    (
        "QUO-2026-006", "Priya Patel", "sent", 5, 0,
        [
            ("Cybersecurity audit (on-site)", 1, "7500.00", 5, 0),
            ("Compliance report & remediation plan", 1, "1500.00", 5, 0),
        ],
    ),
]


def main():
    with engine.begin() as c:
        users = {
            r.email: r.id
            for r in c.execute(
                text("SELECT id, email FROM users WHERE organization_id = :o"), {"o": ORG_ID}
            )
        }

        # ---- customers ----
        existing = c.execute(
            text("SELECT email FROM customers WHERE organization_id = :o"), {"o": ORG_ID}
        ).scalars().all()
        if existing:
            print(f"customers: SKIP (already has {len(existing)} rows)")
        else:
            n = 0
            for i, (name, email, phone, company, address, notes, status) in enumerate(CUSTOMERS):
                cid = str(uuid4())
                created = datetime.utcnow() - timedelta(days=len(CUSTOMERS) - i, hours=3)
                c.execute(
                    text("""INSERT INTO customers (id, organization_id, name, email, phone, company, address, notes, status, created_at, updated_at)
                        VALUES (:id, :o, :name, :email, :phone, :company, :address, :notes, :status, :created, :created)"""),
                    dict(id=cid, o=ORG_ID, name=name, email=email, phone=phone,
                         company=company, address=address, notes=notes, status=status, created=created),
                )
                n += 1
            print(f"customers: inserted {n}")

        # ---- leads ----
        existing = c.execute(
            text("SELECT id FROM leads WHERE organization_id = :o"), {"o": ORG_ID}
        ).scalars().all()
        if existing:
            print(f"leads: SKIP (already has {len(existing)} rows)")
        else:
            n = 0
            for i, (name, email, phone, company, source, status, score, assignee, meta) in enumerate(LEADS):
                lid = str(uuid4())
                created = datetime.utcnow() - timedelta(days=len(LEADS) - i, hours=2)
                c.execute(
                    text("""INSERT INTO leads (id, organization_id, name, email, phone, company, source, status, score, assigned_to, metadata, created_at, updated_at)
                        VALUES (:id, :o, :name, :email, :phone, :company, :source, :status, :score, :assignee, :meta, :created, :created)"""),
                    dict(id=lid, o=ORG_ID, name=name, email=email, phone=phone, company=company,
                         source=source, status=status, score=score,
                         assignee=users.get(assignee), meta=json.dumps(meta or {}), created=created),
                )
                n += 1
            print(f"leads: inserted {n}")

        # ---- quotations + items ----
        existing = c.execute(
            text("SELECT id FROM quotations WHERE organization_id = :o"), {"o": ORG_ID}
        ).scalars().all()
        if existing:
            print(f"quotations: SKIP (already has {len(existing)} rows)")
        else:
            n = 0
            for i, (qnum, customer_name, status, doc_tax, doc_disc, items) in enumerate(QUOTATIONS):
                cust = c.execute(
                    text("SELECT id FROM customers WHERE organization_id = :o AND name = :n"),
                    {"o": ORG_ID, "n": customer_name},
                ).scalar()
                if cust is None:
                    print(f"  !! quotation {qnum}: customer '{customer_name}' missing, skipped")
                    continue
                rows, subtotal, total = doc_totals(
                    [dict(description=d, quantity=q, unit_price=p, tax_rate=t, discount=di) for d, q, p, t, di in items],
                    doc_tax=doc_tax, doc_discount=doc_disc,
                )
                qid = str(uuid4())
                created = datetime.utcnow() - timedelta(days=len(QUOTATIONS) - i, hours=5)
                c.execute(
                    text("""INSERT INTO quotations (id, organization_id, customer_id, quotation_number, status, subtotal, tax, discount, total, created_at)
                        VALUES (:id, :o, :cust, :qnum, :status, :subtotal, :tax, :disc, :total, :created)"""),
                    dict(id=qid, o=ORG_ID, cust=cust, qnum=qnum, status=status,
                         subtotal=subtotal, tax=doc_tax, disc=doc_disc, total=total, created=created),
                )
                for r in rows:
                    c.execute(
                        text("""INSERT INTO quotation_items (id, organization_id, quotation_id, description, quantity, unit_price, tax_rate, discount, line_total, sort_order, created_at)
                            VALUES (:id, :o, :qid, :desc, :qty, :price, :tax, :disc, :lt, :so, :created)"""),
                        dict(id=str(uuid4()), o=ORG_ID, qid=qid, desc=r["description"], qty=r["quantity"],
                             price=r["unit_price"], tax=r["tax_rate"], disc=r["discount"],
                             lt=r["line_total"], so=r["sort_order"], created=created),
                    )
                n += 1
                print(f"  {qnum}: {customer_name} | status={status} | subtotal={subtotal} | total={total} | items={len(rows)}")
            print(f"quotations: inserted {n}")

    # summary
    with engine.connect() as c:
        print()
        print("=== SUMMARY ===")
        for t in ["customers", "leads", "quotations", "quotation_items"]:
            n = c.execute(
                text(f"SELECT COUNT(*) FROM {t} WHERE organization_id = :o"), {"o": ORG_ID}
            ).scalar()
            print(f"  {t}: {n}")


if __name__ == "__main__":
    main()
