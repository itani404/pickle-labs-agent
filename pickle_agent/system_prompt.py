"""The system prompt: persona + instructions + route instructions + business knowledge (notebook section 3.3, cell 12)."""

from .instructions import INSTRUCTIONS, ROUTE_INSTRUCTIONS
from .knowledge import BUSINESS_PDF, BUSINESS_SUMMARY
from .persona import PERSONA


def build_system_prompt(route=None):
    """Persona + instructions + (optional) route instructions + business knowledge, in tagged sections."""
    parts = [
        f"<persona>\n{PERSONA}\n</persona>",
        f"<instructions>\n{INSTRUCTIONS}\n</instructions>",
    ]
    if route:
        parts.append(f'<route_instructions intent="{route}">\n{ROUTE_INSTRUCTIONS[route]}\n</route_instructions>')
    parts.append(f"<business_summary>\n{BUSINESS_SUMMARY}\n</business_summary>")
    parts.append(f"<business_profile_pdf>\n{BUSINESS_PDF}\n</business_profile_pdf>")
    return "\n\n".join(parts)


def show_prompt(route, knowledge_preview=160):
    """Print the prompt with the long knowledge blocks shortened, for reading."""
    prompt = build_system_prompt(route)
    for tag in ("business_summary", "business_profile_pdf"):
        start = prompt.index(f"<{tag}>\n") + len(tag) + 3
        end = prompt.index(f"\n</{tag}>")
        body = prompt[start:end]
        prompt = prompt[:start] + body[:knowledge_preview] + f" [... {len(body) - knowledge_preview} more characters ...]" + prompt[end:]
    print(prompt)
