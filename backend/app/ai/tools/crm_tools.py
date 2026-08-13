"""CRM tools callable by agents: search customers/leads, read deals."""
import json
from datetime import datetime, timezone

from app.ai import model_router
from app.ai.tools.base import ToolSpec

_DEAL_TERMINAL_STAGES = {"won", "lost", "closed_won", "closed_lost", "archived"}
_ACTIVITY_LIMIT = 20
_TEXT_LIMIT = 300
_METADATA_LIMIT = 200


def _to_uuid(value):
    from uuid import UUID

    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _truncate(value, limit=_TEXT_LIMIT) -> str:
    if value is None:
        return ""
    text = str(value)
    return text[:limit] + ("…" if len(text) > limit else "")


def _activity_brief(activity) -> dict:
    metadata = activity.metadata_json or {}
    try:
        metadata_text = _truncate(json.dumps(metadata, default=str), _METADATA_LIMIT)
    except (TypeError, ValueError):
        metadata_text = ""
    return {
        "action": _truncate(activity.action),
        "metadata": metadata_text,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
    }


def _deal_brief(deal) -> dict:
    return {
        "title": _truncate(deal.title),
        "stage": deal.stage,
        "value": float(deal.value or 0),
        "probability": deal.probability,
        "expected_close": (
            deal.expected_close.isoformat() if deal.expected_close else None
        ),
        "created_at": deal.created_at.isoformat() if deal.created_at else None,
    }


def _document_brief(record, kind: str) -> dict:
    number = (
        getattr(record, "invoice_number", None)
        or getattr(record, "quotation_number", None)
        or str(record.id)
    )
    return {
        "kind": kind,
        "number": number,
        "status": record.status,
        "total": float(getattr(record, "total", 0) or 0),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }



def _search_crm(db, org_id, user_id, arguments: dict):
    from app.models.customer import Customer
    from app.models.lead import Lead

    query = (arguments.get("query") or "").strip().lower()
    entity = arguments.get("entity", "all")
    results = {"customers": [], "leads": []}

    if entity in ("customer", "all"):
        rows = (
            db.query(Customer)
            .filter(Customer.organization_id == org_id)
            .all()
        )
        filtered = [
            row
            for row in rows
            if not query
            or query in (row.name or "").lower()
            or query in (row.email or "").lower()
            or query in (row.company or "").lower()
        ]
        results["customers"] = [
            {
                "id": str(c.id),
                "name": c.name,
                "email": c.email,
                "company": c.company,
                "phone": c.phone,
                "status": c.status,
            }
            for c in filtered[: arguments.get("limit", 10)]
        ]

    if entity in ("lead", "all"):
        leads = (
            db.query(Lead)
            .filter(Lead.organization_id == org_id)
            .all()
        )
        filtered = [
            l
            for l in leads
            if not query
            or query in (l.name or "").lower()
            or query in (l.email or "").lower()
            or query in (l.company or "").lower()
        ]
        results["leads"] = [
            {
                "id": str(l.id),
                "name": l.name,
                "email": l.email,
                "company": l.company,
                "status": l.status,
                "score": l.score,
            }
            for l in filtered[: arguments.get("limit", 10)]
        ]
    return results


def _get_customer(db, org_id, user_id, arguments: dict):
    from app.models.customer import Customer

    customer = (
        db.query(Customer)
        .filter(
            Customer.id == arguments.get("id"),
            Customer.organization_id == org_id,
        )
        .first()
    )
    if customer is None:
        return {"error": "Customer not found"}
    return {
        "id": str(customer.id),
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "company": customer.company,
        "address": customer.address,
        "notes": customer.notes,
        "ai_summary": customer.ai_summary,
        "status": customer.status,
    }


def _list_leads(db, org_id, user_id, arguments: dict):
    from app.models.lead import Lead

    query = db.query(Lead).filter(Lead.organization_id == org_id)
    status = arguments.get("status")
    if status and status.lower() != "all":
        query = query.filter(Lead.status == status)
    leads = query.order_by(Lead.created_at.desc()).limit(arguments.get("limit", 50)).all()
    return [
        {
            "id": str(l.id),
            "name": l.name,
            "email": l.email,
            "company": l.company,
            "status": l.status,
            "score": l.score,
        }
        for l in leads
    ]


def _list_deals(db, org_id, user_id, arguments: dict):
    from app.models.pipeline import Deal

    query = db.query(Deal).filter(Deal.organization_id == org_id)
    stage = arguments.get("stage")
    if stage:
        query = query.filter(Deal.stage == stage)
    deals = query.order_by(Deal.value.desc()).limit(arguments.get("limit", 50)).all()
    return [
        {
            "id": str(d.id),
            "title": d.title,
            "stage": d.stage,
            "value": float(d.value or 0),
            "probability": d.probability,
        }
        for d in deals
    ]


def _create_customer(db, org_id, user_id, arguments: dict):
    from app.models.customer import Customer

    name = str(arguments.get("name") or "").strip()
    if not name:
        return {"error": "name is required to create a customer"}

    customer = Customer(
        organization_id=org_id,
        name=name,
        email=arguments.get("email"),
        phone=arguments.get("phone"),
        company=arguments.get("company"),
        address=arguments.get("address"),
        notes=arguments.get("notes"),
        status=arguments.get("status") or "active",
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return {
        "id": str(customer.id),
        "name": customer.name,
        "email": customer.email,
        "company": customer.company,
        "phone": customer.phone,
        "status": customer.status,
    }


def _create_activity(db, org_id, user_id, arguments: dict):
    from app.services.crm_service import log_activity

    activity = log_activity(
        db,
        org_id,
        user_id,
        target_type=arguments.get("target_type", "note"),
        target_id=arguments.get("target_id"),
        activity_type=arguments.get("type", "note"),
        description=arguments.get("description"),
        metadata={"source": "ai"},
    )
    return {"id": str(activity.id), "created": True}


def _gather_customer_data(db, org_id, customer_id):
    """Pull real, bounded CRM data for a customer into a plain dict.

    Always returns a dict (even when sparse) so the summary layer can build
    a data-only fallback without the LLM.
    """
    from app.models.activity import Activity
    from app.models.invoice import Invoice
    from app.models.pipeline import Deal
    from app.models.quotation import Quotation

    activities = (
        db.query(Activity)
        .filter(
            Activity.organization_id == org_id,
            Activity.entity_type == "customer",
            Activity.entity_id == customer_id,
        )
        .order_by(Activity.created_at.desc())
        .limit(_ACTIVITY_LIMIT)
        .all()
    )
    deals = (
        db.query(Deal)
        .filter(Deal.organization_id == org_id, Deal.customer_id == customer_id)
        .order_by(Deal.created_at.desc())
        .all()
    )
    invoices = (
        db.query(Invoice)
        .filter(Invoice.organization_id == org_id, Invoice.customer_id == customer_id)
        .order_by(Invoice.created_at.desc())
        .all()
    )
    quotations = (
        db.query(Quotation)
        .filter(
            Quotation.organization_id == org_id, Quotation.customer_id == customer_id
        )
        .order_by(Quotation.created_at.desc())
        .all()
    )

    now = datetime.now(timezone.utc)
    last_contact_days_ago = None
    if activities and activities[0].created_at:
        delta = (now - activities[0].created_at).days
        last_contact_days_ago = max(0, int(delta))

    open_deals = [
        d for d in deals if (d.stage or "").lower() not in _DEAL_TERMINAL_STAGES
    ]
    open_deals_value = sum(float(d.value or 0) for d in open_deals)
    stalled_deals = [
        d
        for d in open_deals
        if d.created_at and (now - d.created_at).days >= 60
    ]
    unpaid_invoices = [i for i in invoices if (i.status or "").lower() == "unpaid"]

    flags = []
    if last_contact_days_ago is not None and last_contact_days_ago >= 30:
        flags.append("no contact in 30+ days")
    for d in stalled_deals:
        flags.append(f"deal stalled in {_truncate(d.stage or 'current', 40)} stage 60+ days")
    if unpaid_invoices:
        flags.append(f"{len(unpaid_invoices)} unpaid invoice(s)")
    if not deals and not activities:
        flags.append("no recorded pipeline or activity history")

    return {
        "activity_count": len(activities),
        "open_deal_count": len(open_deals),
        "stalled_deal_count": len(stalled_deals),
        "unpaid_invoice_count": len(unpaid_invoices),
        "last_contact_days_ago": last_contact_days_ago,
        "open_deals_value": open_deals_value,
        "flags": flags,
        "activities": [_activity_brief(a) for a in activities],
        "deals": [_deal_brief(d) for d in deals],
        "invoices": [_document_brief(i, "invoice") for i in invoices],
        "quotations": [_document_brief(q, "quotation") for q in quotations],
    }


def _summary_prompt(customer, data: dict) -> list[dict]:
    context = {
        "customer": {
            "name": customer.name,
            "email": customer.email,
            "company": customer.company,
            "status": customer.status,
            "notes": _truncate(customer.notes),
        },
        "data": data,
    }
    return [
        {
            "role": "system",
            "content": (
                "You produce concise customer relationship insights. "
                "Respond with ONLY a JSON object using exactly these keys: "
                "summary (2-3 sentences), relationship_health "
                "(\"strong\"|\"neutral\"|\"at_risk\"), suggested_next_action "
                "(1 sentence). Do not invent numbers; rely on the provided data."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(context, default=str),
        },
    ]


def _computed_relationship_health(data: dict) -> str:
    risk_terms = ("no contact in 30+ days", "deal stalled", "unpaid invoice")
    if any(f in " ".join(data["flags"]) for f in risk_terms):
        return "at_risk"
    if data["open_deals_value"] > 0 and (
        data.get("last_contact_days_ago") is not None
        and data["last_contact_days_ago"] < 30
    ):
        return "strong"
    return "neutral"


def _computed_summary(name, data: dict) -> str:
    last = (
        f"{data['last_contact_days_ago']} days ago"
        if data.get("last_contact_days_ago") is not None
        else "no recorded contact"
    )
    return (
        f"{name} has {data['open_deal_count']} open deal(s) totalling "
        f"${data['open_deals_value']:.2f}, {data['activity_count']} recorded "
        f"interaction(s) (last contact {last}), and "
        f"{data['unpaid_invoice_count']} unpaid invoice(s)."
    )


def _computed_action(name, data: dict) -> str:
    if data["open_deals_value"] > 0:
        return f"Follow up with {name} on their open deal(s)."
    if data.get("last_contact_days_ago") is not None:
        return f"Reach out to {name} to re-engage."
    return f"Introduce yourself to {name} and qualify their needs."


def _data_only_result(customer, data: dict) -> dict:
    return {
        "summary": _computed_summary(customer.name, data),
        "relationship_health": _computed_relationship_health(data),
        "open_deals_value": data["open_deals_value"],
        "last_contact_days_ago": data.get("last_contact_days_ago"),
        "suggested_next_action": _computed_action(customer.name, data),
        "flags": data["flags"],
        "source": "data",
    }


def _parse_llm_json(raw) -> dict | None:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _merge_result(customer, data: dict, llm: dict | None) -> dict:
    base = _data_only_result(customer, data)
    if llm is None:
        return base
    health = llm.get("relationship_health")
    if health not in ("strong", "neutral", "at_risk"):
        health = base["relationship_health"]
    summary = _truncate(llm.get("summary"), 600) or base["summary"]
    action = _truncate(llm.get("suggested_next_action"), 300) or base["suggested_next_action"]
    return {
        "summary": summary,
        "relationship_health": health,
        "open_deals_value": data["open_deals_value"],
        "last_contact_days_ago": data.get("last_contact_days_ago"),
        "suggested_next_action": action,
        "flags": data["flags"],
        "source": "llm",
    }


def _summarize_customer(db, org_id, user_id, arguments: dict):
    from app.models.customer import Customer

    customer = (
        db.query(Customer)
        .filter(
            Customer.id == _to_uuid(arguments.get("customer_id")),
            Customer.organization_id == org_id,
        )
        .first()
    )
    if customer is None:
        return {"error": "Customer not found"}

    data = _gather_customer_data(db, org_id, customer.id)

    llm = None
    try:
        raw = model_router.complete(_summary_prompt(customer, data), temperature=0.2)
        llm = _parse_llm_json(raw)
    except Exception:  # noqa: BLE001 - rate limit / no key / parse issues -> fallback
        llm = None

    result = _merge_result(customer, data, llm)
    result["customer_id"] = str(customer.id)
    return result


CRM_TOOLS: dict[str, ToolSpec] = {
    "search_crm": ToolSpec(
        name="search_crm",
        description="Search customers and leads by name/email/company.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text search"},
                "entity": {"type": "string", "enum": ["customer", "lead", "all"]},
                "limit": {"type": "integer"},
            },
        },
        handler=_search_crm,
    ),
    "get_customer": ToolSpec(
        name="get_customer",
        description="Fetch a single customer by id.",
        parameters={
            "type": "object",
            "properties": {"id": {"type": "string", "format": "uuid"}},
            "required": ["id"],
        },
        handler=_get_customer,
    ),
    "list_leads": ToolSpec(
        name="list_leads",
        description="List leads, optionally filtered by status.",
        parameters={
            "type": "object",
            "properties": {"status": {"type": "string"}, "limit": {"type": "integer"}},
        },
        handler=_list_leads,
    ),
    "list_deals": ToolSpec(
        name="list_deals",
        description="List deals, optionally filtered by stage.",
        parameters={
            "type": "object",
            "properties": {"stage": {"type": "string"}, "limit": {"type": "integer"}},
        },
        handler=_list_deals,
    ),
    "create_activity": ToolSpec(
        name="create_activity",
        description="Log an activity/note against a target in the CRM.",
        parameters={
            "type": "object",
            "properties": {
                "target_type": {"type": "string"},
                "target_id": {"type": "string"},
                "type": {"type": "string"},
                "description": {"type": "string"},
            },
        },
        handler=_create_activity,
    ),
    "create_customer": ToolSpec(
        name="create_customer",
        description=(
            "Create a new customer record in the CRM. Only `name` is "
            "required; email, phone, company, address and notes are optional. "
            "Returns the new customer's id so follow-up tools (invoices, "
            "quotations, meetings) can reference it."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Customer name (required)"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "company": {"type": "string"},
                "address": {"type": "string"},
                "notes": {"type": "string"},
                "status": {"type": "string", "description": "Defaults to 'active'"},
            },
            "required": ["name"],
        },
        handler=_create_customer,
    ),
    "summarize_customer": ToolSpec(
        name="summarize_customer",
        description=(
            "Synthesize a compact relationship summary and health assessment "
            "for a customer from their real activities, deals, invoices and "
            "quotations."
        ),
        parameters={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "format": "uuid"},
            },
            "required": ["customer_id"],
        },
        handler=_summarize_customer,
    ),
}