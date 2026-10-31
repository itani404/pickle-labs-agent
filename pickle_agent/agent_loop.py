"""The model-tool-model loop for one message, and short-term memory (notebook section 5, cell 19).

1. Build the input: the system prompt for the chosen route, the cleaned chat history and the new message.
2. Call the model with only the tools that route allows.
3. If the model asks for a tool, run it with dispatch, append the result, and call the model again.
4. If the model answers in plain text, return that text.

Capped at MAX_TOOL_ROUNDS tool cycles; on the last round the tools are withheld so the model must answer.
"""

import json

from . import config
from .llm import llm_call
from .system_prompt import build_system_prompt
from .tools import ROUTE_TOOLS, dispatch, tools_for_route

FALLBACK_REPLY = ("Something glitched on my side, which is rare and I resent it. "
                  "Leave your email and a human at Pickle Labs will pick this up.")


TRACE_MARKER = "**Router:**"       # every trace message starts with this, so it is dropped even if metadata is lost


def clean_history(history):
    """Short-term memory: keep plain user/assistant text only (drop trace messages), last HISTORY_LIMIT, user first."""
    cleaned = []
    for message in history or []:
        role, content = message.get("role"), message.get("content")
        if role not in ("user", "assistant") or message.get("metadata"):
            continue
        if isinstance(content, dict):
            content = content.get("text", "")
        elif isinstance(content, list):
            content = " ".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        if isinstance(content, str) and content.strip() and not content.startswith(TRACE_MARKER):
            cleaned.append({"role": role, "content": content})
    cleaned = cleaned[-config.HISTORY_LIMIT:]
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    return cleaned


def agent_turn(user_message, history, route, llm=None):
    """Model-tool-model loop for one user message. Returns (reply_text, tool_trace)."""
    llm = llm or llm_call
    system = build_system_prompt(route)
    tools = tools_for_route(route)
    allowed = ROUTE_TOOLS[route]
    items = clean_history(history) + [{"role": "user", "content": user_message}]
    tool_trace = []
    for round_number in range(config.MAX_TOOL_ROUNDS + 1):
        withhold_tools = round_number == config.MAX_TOOL_ROUNDS          # last round: force a text answer
        out = llm(system, items, None if withhold_tools else tools, effort=config.AGENT_EFFORT,
                  max_output=config.AGENT_MAX_OUTPUT, label=f"agent:{route}")
        if not out["tool_calls"]:
            return (out["text"] or "").strip() or FALLBACK_REPLY, tool_trace
        items += out["output_items"]
        for call in out["tool_calls"]:
            result = dispatch(call["name"], call["arguments"], allowed)
            tool_trace.append({"tool": call["name"], "arguments": call["arguments"], "result": result})
            items.append({"type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(result)})
    return FALLBACK_REPLY, tool_trace
