"""Orchestrator: resolves the right agent, injects memory/RAG context and runs
the engine for a given AI employee and conversation.

This is the single entry point the chat route calls — it keeps the FastAPI
layer thin while the actual work (prompt assembly + tool loop) lives in the
engine.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.ai.engine import run_agent
from app.ai.memory import recall
from app.ai.retriever import retrieve_context
from app.models.ai_conversation import AIConversation
from app.models.ai_employee import AIEmployee

logger = logging.getLogger("app.ai.orchestrator")


def agent_for_employee(employee: AIEmployee | None):
    """Pick the agent definition for an employee's role (or the default)."""
    from app.ai.agents import DEFAULT_AGENT, resolve_agent

    if employee is None:
        return DEFAULT_AGENT
    return resolve_agent(employee.role)


def build_context_turns(history_messages) -> list[dict]:
    """Convert stored AIMessage rows into OpenAI chat turns."""
    turns = []
    for m in history_messages or []:
        role = m.role if m.role in ("user", "assistant", "system") else "user"
        turns.append({"role": role, "content": m.message})
    return turns


def execute_turn(
    db: Session,
    organization_id,
    user_id,
    conversation: AIConversation,
    user_message: str,
    employee: AIEmployee | None = None,
    history_messages=None,
    model: Optional[str] = None,
    temperature: float = 0.3,
    images: Optional[list[dict]] = None,
) -> tuple[str, str]:
    """Run one full agent turn with memory + RAG context injected.

    Returns (reply_text, agent_key).
    """
    agent = agent_for_employee(employee)

    employee_id = str(employee.id) if employee else (
        str(conversation.ai_employee_id) if conversation.ai_employee_id else None
    )

    memory_chunks = recall(db, organization_id, employee_id, user_message, limit=4)
    rag_chunks = retrieve_context(db, organization_id, user_message, limit=4)
    system_context = [f"{c['title']}\n{c['content']}" for c in rag_chunks]

    employee_name = employee.name if employee else "AI Employee"

    reply = run_agent(
        db,
        organization_id=organization_id,
        user_id=user_id,
        agent=agent,
        user_message=user_message,
        memory=memory_chunks + system_context,
        context=build_context_turns(history_messages),
        model=model or (employee.model if employee else None),
        temperature=temperature,
        images=images,
    )
    return reply, agent.key