"""External integration tools (Zoho CRM, Xero, Drive/Sheets, OneDrive/Excel).

Each tool only succeeds when the organization has connected the matching
integration. When not connected, they return a clear message so the agent can
tell the user what to connect — the internal CRM/invoice rows are still
created so work is never lost.
"""
from app.ai.tools.base import ToolSpec


def _to_optional_uuid(value):
    from uuid import UUID

    try:
        return UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _customer_name(db, org_id, customer_id) -> str | None:
    if not customer_id:
        return None
    from app.models.customer import Customer

    row = (
        db.query(Customer)
        .filter(
            Customer.id == _to_optional_uuid(customer_id),
            Customer.organization_id == org_id,
        )
        .first()
    )
    if row is None:
        return None
    return row.name or row.company or row.email or None


# ── Zoho CRM --------------------------------------------------------------

def _zoho_create_lead(db, org_id, user_id, arguments: dict):
    """Create a lead in the internal CRM and mirror it to Zoho when connected."""
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.integrations.zoho.service import get_client as zoho_get_client
    from app.models.lead import Lead

    last_name = str(arguments.get("last_name") or arguments.get("name") or "").strip()
    if not last_name:
        return {"error": "last_name is required to create a lead"}
    first_name = arguments.get("first_name")
    company = arguments.get("company")
    email = arguments.get("email")
    phone = arguments.get("phone")
    description = arguments.get("description")

    lead = Lead(
        organization_id=org_id,
        name=" ".join(filter(None, [first_name, last_name])).strip(),
        company=company,
        email=email,
        phone=phone,
        source="zoho",
        status="new",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    result = {"lead_id": str(lead.id), "synced_to": "internal"}
    try:
        client = zoho_get_client(db, org_id)
    except IntegrationNotConnectedError as exc:
        result["zoho"] = {"error": str(exc)}
        return result
    try:
        zoho = client.create_lead(
            last_name=last_name,
            first_name=first_name,
            company=company,
            email=email,
            phone=phone,
            description=description,
        )
        result["zoho"] = zoho
        result["synced_to"] = "internal+zoho"
    except Exception as exc:  # noqa: BLE001 - report, never crash the turn
        result["zoho"] = {"error": f"{exc.__class__.__name__}: {exc}"}
    return result


def _zoho_list_leads(db, org_id, user_id, arguments: dict):
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.integrations.zoho.service import get_client as zoho_get_client

    try:
        client = zoho_get_client(db, org_id)
    except IntegrationNotConnectedError as exc:
        return {"error": str(exc)}
    try:
        return {"leads": client.list_leads(limit=arguments.get("limit", 25))}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


# ── Xero ----------------------------------------------------------------

def _xero_create_invoice(db, org_id, user_id, arguments: dict):
    """Create the invoice internally, then push it to Xero when connected."""
    from app.ai.tools.invoice_tools import INVOICE_TOOLS
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.integrations.xero.service import get_client as xero_get_client

    result = INVOICE_TOOLS["create_invoice"].handler(db, org_id, user_id, arguments)
    if "error" in result:
        return result

    try:
        client = xero_get_client(db, org_id)
    except IntegrationNotConnectedError as exc:
        result["xero"] = {"error": str(exc)}
        return result
    try:
        contact_name = _customer_name(db, org_id, arguments.get("customer_id")) or "Unknown"
        xero = client.create_invoice(
            invoice_number=result.get("invoice_number") or f"INV-{result['id'][:8]}",
            contact_name=contact_name,
            amount=result.get("amount", 0),
            currency=arguments.get("currency", "USD"),
            due_date=arguments.get("due_date"),
            description=arguments.get("description"),
        )
        result["xero"] = xero
    except Exception as exc:  # noqa: BLE001
        result["xero"] = {"error": f"{exc.__class__.__name__}: {exc}"}
    return result


def _xero_list_invoices(db, org_id, user_id, arguments: dict):
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.integrations.xero.service import get_client as xero_get_client

    try:
        client = xero_get_client(db, org_id)
    except IntegrationNotConnectedError as exc:
        return {"error": str(exc)}
    try:
        return {"invoices": client.list_invoices(limit=arguments.get("limit", 20))}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


# ── Google Sheets ----------------------------------------------------------

def _sheets_append_row(db, org_id, user_id, arguments: dict):
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.integrations.google_sheets.service import get_client as sheets_get_client

    values = arguments.get("values")
    if not isinstance(values, list) or not values:
        return {"error": "values (array of cell values) is required"}
    try:
        client = sheets_get_client(db, org_id)
    except IntegrationNotConnectedError as exc:
        return {"error": str(exc)}
    try:
        spreadsheet_id = arguments.get("spreadsheet_id")
        created = None
        if not spreadsheet_id:
            created = client.create_spreadsheet(arguments.get("title") or "AI Employee OS export")
            spreadsheet_id = created["spreadsheet_id"]
        result = client.append_row(
            spreadsheet_id=str(spreadsheet_id),
            values=[str(v) for v in values],
            range_name=arguments.get("range", "A1"),
        )
        result["spreadsheet_id"] = spreadsheet_id
        if created:
            result["spreadsheet_url"] = created.get("url")
        return result
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


# ── Google Drive -----------------------------------------------------------

def _drive_upload_file(db, org_id, user_id, arguments: dict):
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.integrations.google_drive.service import get_client as drive_get_client

    content = arguments.get("content")
    if content is None:
        return {"error": "content (text to save) is required"}
    filename = str(arguments.get("filename") or "ai-export.txt").strip()
    if not filename:
        return {"error": "filename is required"}
    try:
        client = drive_get_client(db, org_id)
    except IntegrationNotConnectedError as exc:
        return {"error": str(exc)}
    try:
        return client.upload_file(
            filename=filename,
            content_bytes=str(content).encode("utf-8"),
            mime_type=arguments.get("mime_type", "text/plain"),
            description=arguments.get("description"),
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


# ── Slack ------------------------------------------------------------------

def _slack_post_message(db, org_id, user_id, arguments: dict):
    from app.core.config import settings
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.integrations.slack.client import SlackClient
    from app.integrations.slack.service import get_client as slack_get_client

    text = str(arguments.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}
    try:
        client = slack_get_client(db, org_id, channel=arguments.get("channel"))
    except IntegrationNotConnectedError as exc:
        # Fall back to the global bot token so Slack works before OAuth.
        if settings.SLACK_BOT_TOKEN:
            client = SlackClient(
                access_token=settings.SLACK_BOT_TOKEN,
                channel=arguments.get("channel"),
            )
        else:
            return {"error": str(exc)}
    try:
        result = client.post_message(text=text, channel=arguments.get("channel"))
        result["posted"] = True
        return result
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


# ── OneDrive / Excel -------------------------------------------------------

def _onedrive_upload_file(db, org_id, user_id, arguments: dict):
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.integrations.onedrive.service import get_client as onedrive_get_client

    content = arguments.get("content")
    if content is None:
        return {"error": "content (text to save) is required"}
    path = str(arguments.get("path") or "").strip()
    if not path:
        return {"error": "path (OneDrive file path, e.g. 'Reports/export.txt') is required"}
    try:
        client = onedrive_get_client(db, org_id)
    except IntegrationNotConnectedError as exc:
        return {"error": str(exc)}
    try:
        return client.upload_file(
            path=path,
            content_bytes=str(content).encode("utf-8"),
            mime_type=arguments.get("mime_type", "text/plain"),
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


def _onedrive_append_excel(db, org_id, user_id, arguments: dict):
    from app.integrations.gmail.client import IntegrationNotConnectedError
    from app.integrations.onedrive.service import get_client as onedrive_get_client

    values = arguments.get("values")
    if not isinstance(values, list) or not values:
        return {"error": "values (array of cell values) is required"}
    path = str(arguments.get("path") or "").strip()
    if not path:
        return {"error": "path (Excel workbook path) is required"}
    try:
        client = onedrive_get_client(db, org_id)
    except IntegrationNotConnectedError as exc:
        return {"error": str(exc)}
    try:
        return client.append_excel_rows(
            path=path,
            values=[str(v) for v in values],
            table=arguments.get("table", "Table1"),
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


INTEGRATION_TOOLS: dict[str, ToolSpec] = {
    "slack_post_message": ToolSpec(
        name="slack_post_message",
        description=(
            "Post a message to the connected Slack workspace. `channel` may be "
            "a #channel name, a channel id, or a user id (defaults to whatever "
            "was set at connect time)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "channel": {"type": "string"},
            },
            "required": ["text"],
        },
        handler=_slack_post_message,
    ),
    "zoho_create_lead": ToolSpec(
        name="zoho_create_lead",
        description=(
            "Create a lead in the CRM. The lead is always stored internally, "
            "and when Zoho is connected it is also created in Zoho CRM "
            "(the 'Add John as a lead' flow)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "last_name": {"type": "string"},
                "first_name": {"type": "string"},
                "company": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["last_name"],
        },
        handler=_zoho_create_lead,
    ),
    "zoho_list_leads": ToolSpec(
        name="zoho_list_leads",
        description="List recent leads from the connected Zoho CRM.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
        handler=_zoho_list_leads,
    ),
    "xero_create_invoice": ToolSpec(
        name="xero_create_invoice",
        description=(
            "Create an invoice. The invoice is always stored internally, and "
            "when Xero is connected it is also pushed to Xero accounting."
        ),
        parameters={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "invoice_number": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "due_date": {"type": "string", "format": "date"},
                "description": {"type": "string"},
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
            },
        },
        handler=_xero_create_invoice,
    ),
    "xero_list_invoices": ToolSpec(
        name="xero_list_invoices",
        description="List recent invoices from the connected Xero accounting.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
        handler=_xero_list_invoices,
    ),
    "sheets_append_row": ToolSpec(
        name="sheets_append_row",
        description=(
            "Append a row to a Google Sheet (by spreadsheet_id), or create a "
            "new spreadsheet when none is given."
        ),
        parameters={
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string"},
                "title": {"type": "string"},
                "range": {"type": "string"},
                "values": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["values"],
        },
        handler=_sheets_append_row,
    ),
    "drive_upload_file": ToolSpec(
        name="drive_upload_file",
        description="Upload a text file to the connected Google Drive.",
        parameters={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content": {"type": "string"},
                "mime_type": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["filename", "content"],
        },
        handler=_drive_upload_file,
    ),
    "onedrive_upload_file": ToolSpec(
        name="onedrive_upload_file",
        description="Upload a text file to the connected OneDrive at a given path.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "mime_type": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        handler=_onedrive_upload_file,
    ),
    "onedrive_append_excel": ToolSpec(
        name="onedrive_append_excel",
        description=(
            "Append a row to a table in an Excel workbook stored on OneDrive "
            "(e.g. path='Reports/leads.xlsx')."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "table": {"type": "string"},
                "values": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["path", "values"],
        },
        handler=_onedrive_append_excel,
    ),
}
