"""Central registry of all tools agents can call."""
from typing import Any

from app.ai.tools.base import ToolSpec
from app.ai.tools.crm_tools import CRM_TOOLS
from app.ai.tools.delegate_tools import DELEGATE_TOOLS
from app.ai.tools.email_tools import EMAIL_TOOLS
from app.ai.tools.hr_tools import HR_TOOLS
from app.ai.tools.integration_tools import INTEGRATION_TOOLS
from app.ai.tools.invoice_tools import INVOICE_TOOLS
from app.ai.tools.inventory_tools import INVENTORY_TOOLS
from app.ai.tools.knowledge_tools import KNOWLEDGE_TOOLS
from app.ai.tools.marketing_tools import MARKETING_TOOLS
from app.ai.tools.reminder_tools import REMINDER_TOOLS
from app.ai.tools.reporting_tools import REPORTING_TOOLS
from app.ai.tools.task_tools import TASK_TOOLS

ALL_TOOLS: dict[str, ToolSpec] = {}
for _group in [
    CRM_TOOLS,
    HR_TOOLS,
    INVOICE_TOOLS,
    INTEGRATION_TOOLS,
    INVENTORY_TOOLS,
    KNOWLEDGE_TOOLS,
    MARKETING_TOOLS,
    TASK_TOOLS,
    REMINDER_TOOLS,
    DELEGATE_TOOLS,
    EMAIL_TOOLS,
    REPORTING_TOOLS,
]:
    ALL_TOOLS.update(_group)


def get_tool(name: str) -> ToolSpec | None:
    return ALL_TOOLS.get(name)


def execute_tool(db, tool_name, org_id, user_id, arguments: dict):
    """Execute a named tool safely inside its tenant context.

    Returns a JSON-serializable result dict. Unknown or failed tools return
    an ``{"error": ...}`` dict instead of raising, so the agent loop can keep
    going.
    """
    spec = get_tool(tool_name)
    if spec is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return spec.handler(db, org_id, user_id, arguments or {})
    except Exception as exc:  # noqa: BLE001 - agent-facing, must not crash turn
        # A failed handler may have aborted the session's transaction (e.g. a
        # bad flush); roll back so the rest of the turn can keep using it.
        try:
            db.rollback()
        except Exception:  # noqa: BLE001 - best effort
            pass
        return {"error": f"{exc.__class__.__name__}: {exc}"}


def tool_definitions(enabled_names: list[str]) -> list[dict[str, Any]]:
    """Expose only a subset of tools (by name) as OpenAI-style definitions."""
    return [
        spec.to_definition()
        for name, spec in ALL_TOOLS.items()
        if name in enabled_names
    ]


__all__ = [
    "ALL_TOOLS",
    "get_tool",
    "execute_tool",
    "tool_definitions",
    "ToolSpec",
]