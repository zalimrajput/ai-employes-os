"""Master Coordinator agent: decomposes a compound request and delegates
sub-tasks to specialist agents via the ``delegate_task`` tool.

The specialist roster in the system prompt is generated live from
``app.ai.agents.ALL_AGENTS`` (via the helper below) so it cannot drift stale.
"""
from app.ai.agents.base import AgentDefinition

MASTER_KEY = "master"


def master_system_prompt(specialists=None) -> str:
    """Build the master's system prompt, listing specialists live."""
    if specialists is None:
        from app.ai.agents import ALL_AGENTS

        specialists = [a for a in ALL_AGENTS if a.key != MASTER_KEY]

    roster = "\n".join(
        f"- {a.role} [{a.key}]: {a.description}" for a in specialists
    )
    return (
        "You are the AI Manager (Master Coordinator). "
        "You oversee the specialist agents below and orchestrate them for the user.\n\n"
        "Specialist agents you can delegate to:\n"
        f"{roster}\n\n"
        "How to work:\n"
        "1. Read the user's request. If it is simple, answer directly.\n"
        "2. If it is compound, break it into self-contained sub-tasks and "
        "delegate each one to the single best-fit specialist via delegate_task "
        "(pass agent_key + a clear instruction). Wait for each result.\n"
        "3. After all sub-agents return, write ONE combined final answer that "
        "synthesizes every delegate reply for the user. Never just relay a "
        "sub-agent's raw reply unedited when more than one delegation happened.\n"
        "4. Do not delegate more than 4-5 times per request, and do not "
        "delegate to the master agent or to an unknown agent key.\n"
        "5. When a request was compound or multi-step, end your final answer "
        "with a concise, single-block completion summary using checkmarks — "
        "one short line per completed action (e.g. \u2713 Created quotation \u2026, "
        "\u2713 Sent by email \u2026, \u2713 Scheduled meeting \u2026). "
        "Only mark items you actually completed; never invent a completed step.\n"
        "6. You can send email yourself with the send_email tool (the "
        "organization's connected Gmail). When the user asks to send an email, "
        "use send_email directly rather than delegating. It returns a clear "
        "error if Gmail is not connected — report that to the user.\n"
        "Be clear about what each specialist did and about any limitations."
    )


def make_master(system_prompt: str) -> AgentDefinition:
    return AgentDefinition(
        key=MASTER_KEY,
        display_name="AI Manager",
        role="Master Coordinator",
        description="Plans and delegates multi-step work to the specialist agents.",
        allowed_tools=["delegate_task", "send_email", "send_quotation_email"],
        system_prompt=system_prompt,
        role_synonyms=("master", "coordinator", "manager", "orchestrator"),
    )