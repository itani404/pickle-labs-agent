"""Print what the notebook printed while it was being built: settings, knowledge, prompt, tools.
No API calls (notebook cells 2, 6, 8, 10, 12 and 14, the print parts).

    python scripts/inspect_agent.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pickle_agent import config  # noqa: E402
from pickle_agent.instructions import INSTRUCTIONS, ROUTE_INSTRUCTIONS  # noqa: E402
from pickle_agent.knowledge import BUSINESS_PDF, BUSINESS_SUMMARY  # noqa: E402
from pickle_agent.persona import PERSONA  # noqa: E402
from pickle_agent.system_prompt import build_system_prompt, show_prompt  # noqa: E402
from pickle_agent.tools import print_tool_docs  # noqa: E402

config.describe()

print(f"\nsummary: {len(BUSINESS_SUMMARY)} characters, about {len(BUSINESS_SUMMARY) // 4} tokens")
print(f"pdf:     {len(BUSINESS_PDF)} characters, about {len(BUSINESS_PDF) // 4} tokens")
print("\n--- summary, first lines ---")
print(BUSINESS_SUMMARY[:260] + " ...")
print("\n--- pdf, first lines ---")
print(BUSINESS_PDF[:260] + " ...")

print("\n=== PERSONA ===")
print(PERSONA)

print("\n=== INSTRUCTIONS ===")
print(INSTRUCTIONS)
print()
for route, text in ROUTE_INSTRUCTIONS.items():
    print(f"[{route}] {text}\n")

print("=== SYSTEM PROMPT (lead_collection route, knowledge shortened) ===")
show_prompt("lead_collection")
full = build_system_prompt("lead_collection")
print(f"\nfull prompt is {len(full)} characters, about {len(full) // 4} tokens")

print("\n=== TOOLS ===")
print_tool_docs()
