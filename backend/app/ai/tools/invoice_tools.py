"""Invoice, expense & quotation tools."""
from typing import Any

from app.ai.tools.base import ToolSpec

QUOTATION_STATUSES = {"draft", "pending_approval", "approved", "rejected", "sent"}


def _to_optional_uuid(value):
    from uuid import UUID

    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _compute_item_totals(items: list) -> tuple[list[dict], "Decimal"]:
    """Compute per-line totals and the invoice total from line items.

    Formula per line (tax applied on the DISCOUNTED price):
        gross = quantity * unit_price
        discounted = gross * (1 - discount / 100)
        line_total = discounted * (1 + tax_rate / 100)
    Each line is rounded to 2 decimals (ROUND_HALF_UP), then summed into the
    invoice total (also rounded to 2 decimals).
    """
    from decimal import ROUND_HALF_UP, Decimal

    parsed = []
    total = Decimal("0.00")
    for order, it in enumerate(items):
        quantity = int(it.get("quantity") or 1)
        unit_price = Decimal(str(it.get("unit_price") or 0))
        tax_rate = Decimal(str(it.get("tax_rate") or 0))
        discount = Decimal(str(it.get("discount") or 0))

        gross = Decimal(quantity) * unit_price
        discounted = gross * (Decimal("1") - discount / Decimal("100"))
        line_total = (discounted * (Decimal("1") + tax_rate / Decimal("100"))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        total += line_total
        parsed.append(
            {
                "description": it.get("description"),
                "quantity": quantity,
                "unit_price": unit_price,
                "tax_rate": tax_rate,
                "discount": discount,
                "line_total": line_total,
                "sort_order": order,
            }
        )
    total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return parsed, total


def _next_billing_date(arguments: dict):
    """Return next_billing_date for a recurring invoice (or None).

    Anchored on ``due_date`` when provided, else today; advanced by
    recurrence_interval in recurrence_period units (daily/weekly/monthly/yearly).
    """
    interval = arguments.get("recurrence_interval")
    period = (arguments.get("recurrence_period") or "").lower()
    if not interval or not period:
        return None
    if period not in {"daily", "weekly", "monthly", "yearly"}:
        return None

    from datetime import date

    from dateutil.relativedelta import relativedelta

    due_date = arguments.get("due_date")
    if due_date is None:
        base = date.today()
    elif isinstance(due_date, date):
        base = due_date
    else:
        from datetime import datetime

        base = datetime.strptime(str(due_date), "%Y-%m-%d").date()
    if period == "daily":
        return base + relativedelta(days=interval)
    if period == "weekly":
        return base + relativedelta(weeks=interval)
    if period == "monthly":
        return base + relativedelta(months=interval)
    return base + relativedelta(years=interval)


def _create_invoice(db, org_id, user_id, arguments: dict):
    from app.models.invoice import Invoice, InvoiceItem

    items = arguments.get("items")
    if items:
        parsed, total = _compute_item_totals(items)
    else:
        # Backward-compatible flat amount path (no items).
        parsed = []
        total = arguments.get("amount") or 0

    invoice = Invoice(
        organization_id=org_id,
        customer_id=_to_optional_uuid(arguments.get("customer_id")),
        invoice_number=arguments.get("invoice_number"),
        amount=total,
        status="unpaid",
        due_date=arguments.get("due_date"),
        recurrence_interval=arguments.get("recurrence_interval"),
        recurrence_period=arguments.get("recurrence_period"),
        next_billing_date=_next_billing_date(arguments),
    )
    db.add(invoice)
    db.flush()
    for it in parsed:
        db.add(
            InvoiceItem(
                organization_id=org_id,
                invoice_id=invoice.id,
                description=it["description"],
                quantity=it["quantity"],
                unit_price=it["unit_price"],
                tax_rate=it["tax_rate"],
                discount=it["discount"],
                line_total=it["line_total"],
                sort_order=it["sort_order"],
            )
        )
    db.commit()
    db.refresh(invoice)
    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "amount": float(invoice.amount or 0),
        "status": invoice.status,
        "items": len(parsed),
    }


def _get_invoice(db, org_id, user_id, arguments: dict):
    from app.models.invoice import Invoice

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == _to_optional_uuid(arguments.get("id")),
            Invoice.organization_id == org_id,
        )
        .first()
    )
    if invoice is None:
        return {"error": "Invoice not found"}
    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "amount": float(invoice.amount or 0),
        "status": invoice.status,
        "due_date": str(invoice.due_date) if invoice.due_date else None,
    }


def _list_invoices(db, org_id, user_id, arguments: dict):
    from app.models.invoice import Invoice

    query = db.query(Invoice).filter(Invoice.organization_id == org_id)
    if arguments.get("status"):
        query = query.filter(Invoice.status == arguments["status"])
    rows = query.order_by(Invoice.created_at.desc()).limit(arguments.get("limit", 50)).all()
    return [
        {
            "id": str(i.id),
            "invoice_number": i.invoice_number,
            "amount": float(i.amount or 0),
            "status": i.status,
        }
        for i in rows
    ]


def _create_expense(db, org_id, user_id, arguments: dict):
    from app.models.finance import Expense

    expense = Expense(
        organization_id=org_id,
        submitted_by=_to_optional_uuid(user_id),
        title=arguments.get("title") or "Expense",
        description=arguments.get("description"),
        amount=arguments.get("amount") or 0,
        currency=arguments.get("currency") or "USD",
        status="pending",
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return {"id": str(expense.id), "title": expense.title, "amount": float(expense.amount or 0)}


def _list_expenses(db, org_id, user_id, arguments: dict):
    from app.models.finance import Expense

    query = db.query(Expense).filter(Expense.organization_id == org_id)
    if arguments.get("status"):
        query = query.filter(Expense.status == arguments["status"])
    rows = query.order_by(Expense.created_at.desc()).limit(arguments.get("limit", 50)).all()
    return [
        {
            "id": str(e.id),
            "title": e.title,
            "amount": float(e.amount or 0),
            "currency": e.currency,
            "status": e.status,
        }
        for e in rows
    ]


def _create_quotation(db, org_id, user_id, arguments: dict):
    """Create a Quotation with its line items and compute totals from items.

    Per-line totals use the same formula as invoices (tax on discounted
    price): ``(quantity * unit_price * (1 - discount/100)) * (1 + tax_rate/100)``.
    Line-level ``tax_rate`` / ``discount`` override the document-level values
    when present.
    """
    from decimal import Decimal

    from app.models.quotation import Quotation, QuotationItem

    items = arguments.get("items") or []
    document_tax_rate = Decimal(str(arguments.get("tax_rate") or 0))
    document_discount = Decimal(str(arguments.get("discount") or 0))

    subtotal = Decimal("0.00")
    parsed_items = []
    for order, it in enumerate(items):
        quantity = int(it.get("quantity") or 1)
        unit_price = Decimal(str(it.get("unit_price") or 0))
        tax_rate = it.get("tax_rate")
        discount = it.get("discount")
        tax_rate = (
            Decimal(str(tax_rate)) if tax_rate is not None else document_tax_rate
        )
        discount = (
            Decimal(str(discount)) if discount is not None else document_discount
        )

        gross = Decimal(quantity) * unit_price
        subtotal += gross
        discounted = gross * (Decimal("1") - discount / Decimal("100"))
        line_total = (discounted * (Decimal("1") + tax_rate / Decimal("100"))).quantize(
            Decimal("0.01")
        )
        parsed_items.append(
            {
                "description": it.get("description"),
                "quantity": quantity,
                "unit_price": unit_price,
                "tax_rate": tax_rate,
                "discount": discount,
                "line_total": line_total,
                "sort_order": order,
            }
        )
    total = sum((Decimal(p["line_total"]) for p in parsed_items), Decimal("0")).quantize(
        Decimal("0.01")
    )

    quotation = Quotation(
        organization_id=org_id,
        customer_id=_to_optional_uuid(arguments.get("customer_id")),
        quotation_number=arguments.get("quotation_number"),
        status=arguments.get("status") or "draft",
        subtotal=subtotal,
        tax=document_tax_rate,
        discount=document_discount,
        total=total,
    )
    db.add(quotation)
    db.flush()
    for it in parsed_items:
        db.add(
            QuotationItem(
                organization_id=org_id,
                quotation_id=quotation.id,
                description=it["description"],
                quantity=it["quantity"],
                unit_price=it["unit_price"],
                tax_rate=it["tax_rate"],
                discount=it["discount"],
                line_total=it["line_total"],
                sort_order=it["sort_order"],
            )
        )
    db.commit()
    db.refresh(quotation)
    return {
        "id": str(quotation.id),
        "quotation_number": quotation.quotation_number,
        "subtotal": str(quotation.subtotal),
        "total": str(quotation.total),
        "items": len(parsed_items),
        "status": quotation.status,
    }


def _generate_quotation_pdf(db, org_id, user_id, arguments: dict):
    """Generate a quotation PDF via the invoice service and persist it."""
    from app.models.quotation import Quotation
    from app.services.invoice_service import generate_quotation_pdf

    quotation = (
        db.query(Quotation)
        .filter(
            Quotation.id == _to_optional_uuid(arguments.get("quotation_id")),
            Quotation.organization_id == org_id,
        )
        .first()
    )
    if quotation is None:
        return {"error": "Quotation not found"}
    try:
        buffer = generate_quotation_pdf(db, org_id, quotation)
    except Exception as exc:  # noqa: BLE001 - report to the caller, never crash
        return {"error": f"{exc.__class__.__name__}: {exc}"}

    data = buffer.getvalue()
    filename = f"quotation_{quotation.id}.pdf"
    from app.services.storage_service import save_blob

    stored = save_blob(
        db,
        org_id,
        filename,
        data,
        mime_type="application/pdf",
        uploaded_by=_to_optional_uuid(user_id),
        entity_type="quotation",
        entity_id=quotation.id,
    )

    quotation.pdf_url = stored["storage_path"]
    db.add(quotation)
    db.commit()
    return {
        "quotation_id": str(quotation.id),
        "pdf_url": stored["storage_path"],
        "file": stored["file"],
        "storage_provider": stored["storage_provider"],
    }


def _generate_invoice_pdf(db, org_id, user_id, arguments: dict):
    """Generate an invoice PDF via the invoice service and persist it."""
    from app.models.invoice import Invoice
    from app.services.invoice_service import generate_invoice_pdf

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == _to_optional_uuid(arguments.get("invoice_id")),
            Invoice.organization_id == org_id,
        )
        .first()
    )
    if invoice is None:
        return {"error": "Invoice not found"}
    try:
        buffer = generate_invoice_pdf(db, org_id, invoice.id)
    except Exception as exc:  # noqa: BLE001 - report to the caller, never crash
        return {"error": f"{exc.__class__.__name__}: {exc}"}

    data = buffer.getvalue()
    filename = f"invoice_{invoice.id}.pdf"
    from app.services.storage_service import save_blob

    stored = save_blob(
        db,
        org_id,
        filename,
        data,
        mime_type="application/pdf",
        uploaded_by=_to_optional_uuid(user_id),
        entity_type="invoice",
        entity_id=invoice.id,
    )

    invoice.pdf_url = stored["storage_path"]
    db.add(invoice)
    db.commit()
    return {
        "invoice_id": str(invoice.id),
        "pdf_url": stored["storage_path"],
        "file": stored["file"],
        "storage_provider": stored["storage_provider"],
    }


def _mark_invoice_paid(db, org_id, user_id, arguments: dict):
    """Mark an invoice paid and fire the paid-workflow chain (best-effort)."""
    from app.models.invoice import Invoice
    from app.services.workflow_service import on_invoice_paid

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == _to_optional_uuid(arguments.get("invoice_id")),
            Invoice.organization_id == org_id,
        )
        .first()
    )
    if invoice is None:
        return {"error": "Invoice not found"}

    if invoice.status == "paid":
        return {
            "invoice_id": str(invoice.id),
            "status": invoice.status,
            "workflow": None,
            "note": "already paid; workflow not re-fired",
        }

    invoice.status = "paid"
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    workflow = on_invoice_paid(db, org_id, invoice.id)
    return {"invoice_id": str(invoice.id), "status": invoice.status, "workflow": workflow}


def _generate_invoice_payment_link(db, org_id, user_id, arguments: dict):
    """Create a Stripe checkout link (and QR code) for a customer invoice."""
    from decimal import ROUND_HALF_UP, Decimal

    from app.core.config import settings
    from app.integrations.stripe.client import (
        IntegrationAuthError,
        IntegrationNotConnectedError,
        create_payment_link,
        generate_qr_code_png,
    )
    from app.models.invoice import Invoice

    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == _to_optional_uuid(arguments.get("invoice_id")),
            Invoice.organization_id == org_id,
        )
        .first()
    )
    if invoice is None:
        return {"error": "Invoice not found"}

    amount = Decimal(str(invoice.amount or 0))
    amount_cents = int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    currency = (arguments.get("currency") or "usd").lower()
    description = f"Invoice {invoice.invoice_number or invoice.id}"

    org_url = getattr(settings, "FRONTEND_ORIGIN", None) or "http://localhost:3000"
    success_url = f"{org_url}/invoices/{invoice.id}?status=paid"
    cancel_url = f"{org_url}/invoices/{invoice.id}"

    try:
        link = create_payment_link(
            amount_cents=amount_cents,
            currency=currency,
            description=description,
            metadata={
                "organization_id": str(org_id),
                "invoice_id": str(invoice.id),
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except IntegrationNotConnectedError as exc:
        return {"error": str(exc)}
    except IntegrationAuthError as exc:
        return {"error": str(exc)}

    qr_bytes = generate_qr_code_png(link["url"])

    filename = f"payment_qr_{invoice.id}.png"
    from app.services.storage_service import save_blob

    stored = save_blob(
        db,
        org_id,
        filename,
        qr_bytes,
        mime_type="image/png",
        uploaded_by=_to_optional_uuid(user_id),
        entity_type="invoice",
        entity_id=invoice.id,
    )

    invoice.payment_link_url = link["url"]
    invoice.qr_code_url = stored["storage_path"]
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return {
        "invoice_id": str(invoice.id),
        "payment_link_url": invoice.payment_link_url,
        "qr_code_url": invoice.qr_code_url,
        "storage_provider": stored["storage_provider"],
    }


def _get_quotation(db, org_id, quotation_id):
    from app.models.quotation import Quotation

    return (
        db.query(Quotation)
        .filter(
            Quotation.id == _to_optional_uuid(quotation_id),
            Quotation.organization_id == org_id,
        )
        .first()
    )


def _list_quotations(db, org_id, user_id, arguments: dict):
    """List the org's quotations, optionally filtered by customer or status.

    Returns id + number + customer id so agents can find a quotation to
    send/approve without guessing UUIDs.
    """
    from app.models.quotation import Quotation

    query = db.query(Quotation).filter(Quotation.organization_id == org_id)
    customer_id = _to_optional_uuid(arguments.get("customer_id"))
    if customer_id:
        query = query.filter(Quotation.customer_id == customer_id)
    status = arguments.get("status")
    if status:
        query = query.filter(Quotation.status == status)
    rows = (
        query.order_by(Quotation.created_at.desc())
        .limit(arguments.get("limit", 50))
        .all()
    )
    return [
        {
            "id": str(q.id),
            "quotation_number": q.quotation_number,
            "customer_id": str(q.customer_id) if q.customer_id else None,
            "status": q.status,
            "subtotal": float(q.subtotal or 0),
            "total": float(q.total or 0),
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
        for q in rows
    ]


def _submit_quotation_for_approval(db, org_id, user_id, arguments: dict):
    """Move a draft quotation into pending_approval."""
    from app.services.crm_service import log_activity

    quotation = _get_quotation(db, org_id, arguments.get("quotation_id"))
    if quotation is None:
        return {"error": "Quotation not found"}
    if quotation.status != "draft":
        return {
            "error": (
                f"Cannot submit quotation for approval — it is in status "
                f"'{quotation.status}'; only 'draft' quotations can be submitted."
            )
        }

    quotation.status = "pending_approval"
    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    log_activity(
        db,
        org_id,
        user_id,
        target_type="quotation",
        target_id=quotation.id,
        activity_type="quotation_submitted_for_approval",
        description="Quotation submitted for approval",
        metadata={
            "quotation_id": str(quotation.id),
            "status": quotation.status,
        },
    )
    return {"quotation_id": str(quotation.id), "status": quotation.status}


def _approve_quotation(db, org_id, user_id, arguments: dict):
    """Approve a pending_approval quotation."""
    from app.services.crm_service import log_activity

    quotation = _get_quotation(db, org_id, arguments.get("quotation_id"))
    if quotation is None:
        return {"error": "Quotation not found"}
    if quotation.status != "pending_approval":
        return {
            "error": (
                f"Cannot approve quotation — it is in status "
                f"'{quotation.status}'; only 'pending_approval' quotations "
                "can be approved."
            )
        }

    quotation.status = "approved"
    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    log_activity(
        db,
        org_id,
        user_id,
        target_type="quotation",
        target_id=quotation.id,
        activity_type="quotation_approved",
        description="Quotation approved",
        metadata={
            "quotation_id": str(quotation.id),
            "status": quotation.status,
            "notes": arguments.get("notes"),
        },
    )
    return {"quotation_id": str(quotation.id), "status": quotation.status}


def _reject_quotation(db, org_id, user_id, arguments: dict):
    """Reject a pending_approval quotation; a reason is required."""
    from app.services.crm_service import log_activity

    reason = (arguments.get("reason") or "").strip()
    if not reason:
        return {"error": "reason is required to reject a quotation"}

    quotation = _get_quotation(db, org_id, arguments.get("quotation_id"))
    if quotation is None:
        return {"error": "Quotation not found"}
    if quotation.status != "pending_approval":
        return {
            "error": (
                f"Cannot reject quotation — it is in status "
                f"'{quotation.status}'; only 'pending_approval' quotations "
                "can be rejected."
            )
        }

    quotation.status = "rejected"
    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    log_activity(
        db,
        org_id,
        user_id,
        target_type="quotation",
        target_id=quotation.id,
        activity_type="quotation_rejected",
        description=f"Quotation rejected: {reason}",
        metadata={
            "quotation_id": str(quotation.id),
            "status": quotation.status,
            "reason": reason,
        },
    )
    return {"quotation_id": str(quotation.id), "status": quotation.status}


INVOICE_TOOLS: dict[str, ToolSpec] = {
    "create_invoice": ToolSpec(
        name="create_invoice",
        description=(
            "Create a new unpaid invoice for a customer. Pass either a flat "
            "`amount`, or a list of `items`; when items are given the amount "
            "is computed as the sum of each line "
            "`(quantity * unit_price * (1 - discount/100)) * (1 + tax_rate/100)`. "
            "Optionally set recurrence (recurrence_interval + "
            "recurrence_period) to schedule automatic re-billing."
        ),
        parameters={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "invoice_number": {"type": "string"},
                "amount": {"type": "number"},
                "due_date": {"type": "string", "format": "date"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "unit_price": {"type": "number"},
                            "tax_rate": {"type": "number"},
                            "discount": {"type": "number"},
                        },
                    },
                },
                "recurrence_interval": {"type": "integer"},
                "recurrence_period": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly", "yearly"],
                },
            },
        },
        handler=_create_invoice,
    ),
    "get_invoice": ToolSpec(
        name="get_invoice",
        description="Fetch a single invoice by id.",
        parameters={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
        handler=_get_invoice,
    ),
    "list_invoices": ToolSpec(
        name="list_invoices",
        description="List the organization's invoices, optionally by status.",
        parameters={
            "type": "object",
            "properties": {"status": {"type": "string"}, "limit": {"type": "integer"}},
        },
        handler=_list_invoices,
    ),
    "create_expense": ToolSpec(
        name="create_expense",
        description="Create a pending expense record.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string"},
            },
            "required": ["title", "amount"],
        },
        handler=_create_expense,
    ),
    "list_expenses": ToolSpec(
        name="list_expenses",
        description="List expenses, optionally by status.",
        parameters={
            "type": "object",
            "properties": {"status": {"type": "string"}, "limit": {"type": "integer"}},
        },
        handler=_list_expenses,
    ),
    "create_quotation": ToolSpec(
        name="create_quotation",
        description="Create a quotation with line items (totals computed from items).",
        parameters={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "quotation_number": {"type": "string"},
                "status": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "unit_price": {"type": "number"},
                            "tax_rate": {"type": "number"},
                            "discount": {"type": "number"},
                        },
                    },
                },
                "tax_rate": {"type": "number"},
                "discount": {"type": "number"},
            },
            "required": ["items"],
        },
        handler=_create_quotation,
    ),
    "list_quotations": ToolSpec(
        name="list_quotations",
        description=(
            "List the organization's quotations, optionally filtered by "
            "customer_id (UUID from search_crm) or status (draft, "
            "pending_approval, approved, rejected, sent). Use this to find a "
            "quotation's id before sending or approving it."
        ),
        parameters={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "status": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
        handler=_list_quotations,
    ),
    "generate_quotation_pdf_tool": ToolSpec(
        name="generate_quotation_pdf_tool",
        description="Generate and persist a PDF for an existing quotation.",
        parameters={
            "type": "object",
            "properties": {"quotation_id": {"type": "string"}},
            "required": ["quotation_id"],
        },
        handler=_generate_quotation_pdf,
    ),
    "generate_invoice_pdf_tool": ToolSpec(
        name="generate_invoice_pdf_tool",
        description="Generate and persist a PDF for an existing invoice.",
        parameters={
            "type": "object",
            "properties": {"invoice_id": {"type": "string"}},
            "required": ["invoice_id"],
        },
        handler=_generate_invoice_pdf,
    ),
    "mark_invoice_paid": ToolSpec(
        name="mark_invoice_paid",
        description=(
            "Mark an existing invoice as paid and run the paid-workflow "
            "chain (receipt, CRM activity, sales notification, thank-you "
            "email, follow-up reminder) in the background."
        ),
        parameters={
            "type": "object",
            "properties": {"invoice_id": {"type": "string"}},
            "required": ["invoice_id"],
        },
        handler=_mark_invoice_paid,
    ),
    "generate_invoice_payment_link": ToolSpec(
        name="generate_invoice_payment_link",
        description=(
            "Create a Stripe payment link (and QR code) for a customer "
            "invoice so the customer can pay online, storing the URLs on the "
            "invoice."
        ),
        parameters={
            "type": "object",
            "properties": {"invoice_id": {"type": "string"}},
            "required": ["invoice_id"],
        },
        handler=_generate_invoice_payment_link,
    ),
    "submit_quotation_for_approval": ToolSpec(
        name="submit_quotation_for_approval",
        description=(
            "Submit a draft quotation for approval, moving it to "
            "pending_approval. Only 'draft' quotations can be submitted."
        ),
        parameters={
            "type": "object",
            "properties": {"quotation_id": {"type": "string"}},
            "required": ["quotation_id"],
        },
        handler=_submit_quotation_for_approval,
    ),
    "approve_quotation": ToolSpec(
        name="approve_quotation",
        description=(
            "Approve a quotation that is awaiting approval, moving it to "
            "'approved' so it may be sent. Only 'pending_approval' quotations "
            "can be approved."
        ),
        parameters={
            "type": "object",
            "properties": {
                "quotation_id": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["quotation_id"],
        },
        handler=_approve_quotation,
    ),
    "reject_quotation": ToolSpec(
        name="reject_quotation",
        description=(
            "Reject a quotation awaiting approval, moving it to 'rejected'. "
            "A reason is required. Only 'pending_approval' quotations can be "
            "rejected."
        ),
        parameters={
            "type": "object",
            "properties": {
                "quotation_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["quotation_id", "reason"],
        },
        handler=_reject_quotation,
    ),
}