"""Lightweight input/output guardrails for the AI engine.

These run inline (no model calls) so they are cheap and deterministic:
- refuse obvious prompt-injection / tool-abuse requests on input
- refuse outputs trying to exfiltrate system secrets
- reject unknown tool names before they reach the executor
"""
import re
from typing import Any

_REFUSE_PATTERNS = [
    # Prompt injection
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?(your\s+)?(system|prior)\s+(prompt|instruction)",
    # Secret exfil
    r"reveal\s+(\w*\s*)*(api[_-]?key|secret|password|token)",
    r"print\s+(the\s+)?(api[_-]?key|secret)",
    r"dump\s+(the\s+)?database",
]

_REFUSED_REPLY = (
    "I can't help with that request — it looks like it's trying to bypass "
    "my security or access controls. Please rephrase your request."
)

_SAFE_TOOL_NAMES = {
    "search_crm",
    "get_customer",
    "list_leads",
    "list_deals",
    "create_activity",
    "summarize_customer",
    "list_employees",
    "list_leave_requests",
    "list_candidates",
    "create_invoice",
    "get_invoice",
    "list_invoices",
    "create_expense",
    "list_expenses",
    "create_quotation",
    "list_quotations",
    "generate_quotation_pdf_tool",
    "generate_invoice_pdf_tool",
    "mark_invoice_paid",
    "generate_invoice_payment_link",
    "submit_quotation_for_approval",
    "approve_quotation",
    "reject_quotation",
    "create_reminder",
    "list_reminders",
    "delegate_task",
    "send_email",
    "send_quotation_email",
    "list_tasks",
    "create_task",
    "list_meetings",
    "create_meeting",
    "summarize_meeting",
    "transcribe_meeting_audio",
    "search_knowledge",
    "get_document",
    "analyze_document",
    "list_campaigns",
    "create_email_draft",
    "classify_email_thread",
    "summarize_email_thread",
    "list_inventory",
    "list_suppliers",
    "list_purchase_orders",
    "zoho_create_lead",
    "zoho_list_leads",
    "xero_create_invoice",
    "xero_list_invoices",
    "sheets_append_row",
    "drive_upload_file",
    "onedrive_upload_file",
    "onedrive_append_excel",
    "slack_post_message",
    "generate_revenue_report",
    "generate_expense_report",
    "generate_sales_pipeline_report",
    "generate_productivity_report",
    "generate_forecast_report",
    "generate_customer_cohort_report",
}


def sanitize_input(text: str | None) -> str | None:
    """Return the message if within length bounds, else None."""
    if text is None:
        return None
    text = text.strip()
    if not text or len(text) > 16_000:
        return None
    return text


def is_flagged(message: str) -> bool:
    lower = message.lower()
    return any(
        re.search(pattern, lower) is not None
        for pattern in _REFUSE_PATTERNS
    )


def refuse_reply() -> str:
    return _REFUSED_REPLY


def validate_tool_call(name: str, arguments: dict) -> bool:
    if name not in _SAFE_TOOL_NAMES:
        return False
    if not isinstance(arguments, dict):
        return False
    return True