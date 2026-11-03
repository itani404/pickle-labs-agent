"""Step 15. One full chat turn: router, then the tool loop for that route, then reflection (notebook section 8, cell 31)."""

import json

from ..config import settings
from ..loop.agent_loop import FALLBACK_REPLY, agent_turn
from ..memory.history import TRACE_MARKER
from .reflection import reflect
from .router import classify_intent


def chat_turn(user_message, history, reflection=None, llm=None):
    """Router, then the agent loop for that route, then (optionally) reflection."""
    use_reflection = settings.REFLECTION if reflection is None else reflection
    routing = classify_intent(user_message, history, llm)
    draft, tool_trace = agent_turn(user_message, history, routing["intent"], llm)
    review = None
    final = draft
    if use_reflection and draft != FALLBACK_REPLY:
        review = reflect(user_message, draft, tool_trace, llm, history)
        final = review["final"]
    return {"reply": final, "draft": draft, "route": routing["intent"], "route_reason": routing["reason"],
            "router_parsed_ok": routing["parsed_ok"], "tool_calls": tool_trace, "reflection": review}


def format_trace(result):
    """A short, human-readable account of what the system did for this message."""
    lines = [f"{TRACE_MARKER} `{result['route']}` ({result['route_reason']})"]
    for call in result["tool_calls"]:
        lines.append(f"**Tool:** `{call['tool']}({call['arguments']})` returned `{json.dumps(call['result'])}`")
    if not result["tool_calls"]:
        lines.append("**Tool:** none called")
    review = result["reflection"]
    if review is not None:
        if not review["parsed_ok"]:
            lines.append("**Reflection:** the reviewer's answer could not be read, so the draft was sent unchanged")
        elif review["ok"]:
            lines.append("**Reflection:** draft approved unchanged")
        else:
            lines.append(f"**Reflection:** draft revised. Issues: {'; '.join(review['issues']) or 'none listed'}")
            lines.append(f"**Original draft:** {result['draft']}")
    return "\n\n".join(lines)


def run_conversation(title, user_messages, reflection=None):
    """Play a conversation turn by turn against the real model and print what happened."""
    print(f"\n=== {title} ===")
    history = []
    for user_message in user_messages:
        result = chat_turn(user_message, history, reflection=reflection)
        print(f"USER      : {user_message}")
        print(f"  router  : {result['route']} ({result['route_reason']})")
        for call in result["tool_calls"]:
            print(f"  tool    : {call['tool']} {call['arguments']} -> {call['result']}")
        if result["reflection"] is not None:
            review = result["reflection"]
            print(f"  reflect : {'ok' if review['ok'] else 'REVISED, issues=' + str(review['issues'])}")
            if not review["ok"]:
                print(f"  draft   : {result['draft']}")
        print(f"DR. RICK  : {result['reply']}")
        history += [{"role": "user", "content": user_message}, {"role": "assistant", "content": result["reply"]}]
    return history
