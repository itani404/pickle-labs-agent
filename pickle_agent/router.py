"""The router: one lightweight LLM call that picks one of three intents (notebook section 6, cell 22).

In Chapter 3 terms this is the routing workflow pattern (a fixed path chosen by a classifier), while the
tool loop inside each route (agent_loop.py) is the agent part. Unparseable output falls back to
general_question and says so.
"""

from . import config
from .agent_loop import clean_history
from .llm import extract_json, llm_call

ROUTER_PROMPT = """You classify one customer message sent to the chat assistant of Pickle Labs, an AI consultancy.
Choose exactly one intent:

general_question: the customer asks about the business (services, prices, team, process, policies) or wants information.
lead_collection: the customer wants to buy, book, get a quote, start a project or be contacted, or is giving their name or email for that purpose.
feedback_or_unanswered: the customer gives feedback, a complaint, a bug report, a suggestion or praise.

Use the recent conversation only to understand short replies. A bare name or email sent after the assistant asked for contact details is lead_collection.

Examples:
"Which models and frameworks do you work with?" -> general_question
"Please put me on the list for a scoping call." -> lead_collection
"I'm Maya, maya@studio.io, I'd like to start something with you." -> lead_collection
"Your onboarding document was confusing." -> feedback_or_unanswered
"The demo video has no sound." -> feedback_or_unanswered

Reply with JSON only: {"intent": "<one of the three>", "reason": "<five words or fewer>"}"""


def parse_router_output(text):
    """Return (intent, reason, parsed_ok). Anything unparseable falls back to general_question."""
    data = extract_json(text)
    if data and data.get("intent") in config.INTENTS:
        return data["intent"], str(data.get("reason", "")).strip(), True
    return "general_question", "router output could not be parsed, defaulted", False


def classify_intent(message, history, llm=None):
    llm = llm or llm_call
    recent = clean_history(history)[-4:]
    transcript = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in recent) or "(no earlier messages)"
    payload = f"Recent conversation:\n{transcript}\n\nNew message: {message}"
    out = llm(ROUTER_PROMPT, [{"role": "user", "content": payload}], None, effort=config.ROUTER_EFFORT,
              max_output=config.ROUTER_MAX_OUTPUT, temperature=0, label="router")
    intent, reason, parsed_ok = parse_router_output(out["text"])
    return {"intent": intent, "reason": reason, "parsed_ok": parsed_ok}
