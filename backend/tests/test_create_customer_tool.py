"""Tests for the `create_customer` agent tool.

Covers the three places a new tool must be wired (registry, guardrails
allowlist, Sales Agent's allowed_tools) and the handler itself against the
live Postgres, following the pattern in test_quotation_reminder_tools.py.
"""
import sys
import uuid

sys.path.insert(0, ".")

import pytest


def test_create_customer_registered_and_allowlisted():
    """The tool must exist in the registry AND the guardrails allowlist."""
    from app.ai.guardrails import _SAFE_TOOL_NAMES, validate_tool_call
    from app.ai.tools import ALL_TOOLS, get_tool

    assert "create_customer" in ALL_TOOLS
    assert get_tool("create_customer") is not None
    assert "create_customer" in _SAFE_TOOL_NAMES
    assert validate_tool_call("create_customer", {"name": "Acme"})


def test_sales_agent_can_create_customer():
    """The Sales Agent is the agent granted the create_customer tool."""
    from app.ai.agents import agent_by_key

    sales = agent_by_key("sales")
    assert sales is not None
    assert "create_customer" in sales.allowed_tools


def _org(db):
    from app.models.organization import Organization

    org = Organization(
        name="Create Customer Test Org",
        slug=f"cc-{uuid.uuid4().hex[:10]}",
        settings={},
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _teardown(db, org):
    from sqlalchemy import text

    deletes = [
        "DELETE FROM customers WHERE organization_id = :id",
        "DELETE FROM users WHERE organization_id = :id",
        "DELETE FROM ai_employees WHERE organization_id = :id",
        "DELETE FROM organizations WHERE id = :id",
    ]
    for statement in deletes:
        db.execute(text(statement), {"id": org.id})
    db.commit()


@pytest.mark.db
def test_create_customer_handler(db):
    from app.ai.tools.crm_tools import CRM_TOOLS
    from app.models.customer import Customer

    org = _org(db)
    try:
        # Missing name -> structured error
        missing = CRM_TOOLS["create_customer"].handler(db, org.id, None, {})
        assert missing.get("error")

        # Happy path: creates a customer scoped to the org
        res = CRM_TOOLS["create_customer"].handler(
            db,
            org.id,
            None,
            {
                "name": "Acme Corp",
                "email": "john@acme.io",
                "phone": "+1-555-0100",
                "company": "Acme",
                "notes": "Enterprise prospect",
            },
        )
        assert res.get("id")
        assert res["name"] == "Acme Corp"
        assert res["email"] == "john@acme.io"
        assert res["status"] == "active"

        row = (
            db.query(Customer)
            .filter(Customer.id == uuid.UUID(res["id"]))
            .first()
        )
        assert row is not None
        assert str(row.organization_id) == str(org.id)
        assert row.name == "Acme Corp"

        # Default status is 'active' when omitted
        res2 = CRM_TOOLS["create_customer"].handler(
            db, org.id, None, {"name": "GlobalTech"}
        )
        assert res2["status"] == "active"
    finally:
        _teardown(db, org)


@pytest.mark.db
def test_executor_runs_create_customer_through_guardrails(db):
    """End-to-end via executor.run: guardrails + per-agent allowlist pass."""
    from app.ai.executor import run as execute

    org = _org(db)
    try:
        res = execute(
            db,
            "create_customer",
            org.id,
            None,
            {"name": "Nova Retail", "company": "Nova"},
            allowed_tools=["create_customer"],
        )
        assert res.get("id"), f"expected success, got error: {res!r}"
        assert "not allowed" not in res  # guardrails must NOT reject it
        assert res["name"] == "Nova Retail"
    finally:
        _teardown(db, org)
