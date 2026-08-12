"""Master agent + delegate_task tests (model_router mocked, no real LLM)."""
import json
import sys

sys.path.insert(0, ".")

import pytest

from app.ai.agents import MASTER_AGENT, agent_by_key
from app.ai.engine import run_agent
from app.ai.tools import get_tool


class FakeDB:
    def query(self, m):
        return self

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        return self

    def all(self):
        return []


def _delegate():
    spec = get_tool("delegate_task")
    assert spec is not None
    return spec.handler


def test_master_registered():
    assert agent_by_key("master").key == "master"
    assert agent_by_key("master").allowed_tools == [
        "delegate_task",
        "send_email",
        "send_quotation_email",
    ]
    assert "delegate_task" in MASTER_AGENT.allowed_tools


def test_delegate_rejects_master():
    res = _delegate()(None, "org", None, {"agent_key": "master", "instruction": "x"})
    assert res.get("error")
    assert "disallowed" in res["error"]


def test_delegate_rejects_unknown_agent():
    res = _delegate()(
        None, "org", None, {"agent_key": "does-not-exist", "instruction": "x"}
    )
    assert res.get("error")
    assert "disallowed" in res["error"]


def test_delegate_valid_calls_run_agent_with_resolved_agent(monkeypatch):
    import app.ai.engine as engine

    captured = {}

    def fake_run_agent(db, *, organization_id, user_id, agent, user_message, **kwargs):
        captured["key"] = agent.key
        captured["org"] = organization_id
        captured["user"] = user_id
        captured["msg"] = user_message
        return "REPLY-OK"

    monkeypatch.setattr(engine, "run_agent", fake_run_agent)

    res = _delegate()(
        FakeDB(),
        "org-1",
        "user-1",
        {"agent_key": "sales", "instruction": "Follow up on the Acme lead"},
    )
    assert res == {"agent": "sales", "reply": "REPLY-OK"}
    assert captured["key"] == "sales"
    assert captured["msg"] == "Follow up on the Acme lead"


def test_delegate_wraps_subagent_failure(monkeypatch):
    import app.ai.engine as engine

    def boom(db, **kwargs):
        raise RuntimeError("sub-agent exploded")

    monkeypatch.setattr(engine, "run_agent", boom)

    res = _delegate()(
        FakeDB(), "org-1", "user-1", {"agent_key": "sales", "instruction": "go"}
    )
    assert res.get("error")
    assert "delegation to sales failed" in res["error"]


def test_full_master_turn_two_delegates_then_answer(monkeypatch):
    import app.ai.engine as engine

    def fake_native(
        messages,
        tools=None,
        model=None,
        temperature=0.3,
        tool_choice="auto",
        max_tokens=None,
    ):
        names = {t["function"]["name"] for t in (tools or [])}
        if "delegate_task" in names:
            tool_count = sum(1 for m in messages if m["role"] == "tool")
            if tool_count == 0:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "name": "delegate_task",
                            "arguments": {
                                "agent_key": "sales",
                                "instruction": "Find the top lead",
                            },
                        }
                    ],
                }
            if tool_count == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c2",
                            "name": "delegate_task",
                            "arguments": {
                                "agent_key": "accountant",
                                "instruction": "Quote the customer",
                            },
                        }
                    ],
                }
            # Final turn: surface the tool results so we prove the delegates
            # really ran through executor.run (guardrails allowlist) and the
            # recursive run_agent returned a real sub-agent reply.
            tool_replies = [
                json.loads(m["content"])["reply"]
                for m in messages
                if m["role"] == "tool"
            ]
            return {
                "content": "Final combined: " + " | ".join(tool_replies),
                "tool_calls": [],
            }
        # sub-agent (e.g. sales/accountant) -> plain answer, no further tools
        return {"content": "Sub-agent result.", "tool_calls": []}

    monkeypatch.setattr(engine.model_router, "complete_with_tools", fake_native)

    reply = run_agent(
        FakeDB(),
        organization_id="00000000-0000-0000-0000-000000000000",
        user_id=None,
        agent=MASTER_AGENT,
        user_message="Plan a follow-up and quote them.",
    )
    assert "Sub-agent result." in reply
