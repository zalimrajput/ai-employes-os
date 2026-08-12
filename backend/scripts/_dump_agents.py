"""Dump every AI agent definition (for documentation)."""
import glob
import importlib
import os
import sys

sys.path.insert(0, ".")

from app.ai.agents.base import AgentDefinition

for f in sorted(glob.glob("app/ai/agents/*_agent.py")):
    mod = os.path.basename(f)[:-3]
    m = importlib.import_module("app.ai.agents." + mod)
    if not hasattr(m, "AGENT"):
        continue
    a = m.AGENT
    if not isinstance(a, AgentDefinition):
        continue
    tools = getattr(a, "allowed_tools", []) or []
    print("## " + mod)
    print("  key=%s display=%s role=%s" % (a.key, a.display_name, a.role))
    print("  synonyms=%s" % (", ".join(a.role_synonyms) or "-"))
    print("  tools(%d): %s" % (len(tools), ", ".join(tools)))
    print("  prompt: %s" % str(a.system_prompt)[:200].replace("\n", " "))
    print()

# default agent
from app.ai.agents import DEFAULT_AGENT
print("## default (fallback)")
print("  key=%s display=%s role=%s" % (DEFAULT_AGENT.key, DEFAULT_AGENT.display_name, DEFAULT_AGENT.role))
print("  tools: %s" % ", ".join(getattr(DEFAULT_AGENT, "allowed_tools", []) or []))
