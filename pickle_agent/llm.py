"""The only code that talks to the model, plus a JSON extractor (notebook section 5, cell 18).

It uses the OpenAI Responses API, which is how current OpenAI models do tool calling, and returns a
small normalized dictionary: the text, any tool calls and the raw output items.
"""

import json
import re

from . import config
from .usage import get_client, meter


def llm_call(system, items, tools=None, effort=None, max_output=None, temperature=None, label="agent"):
    """One Responses API call. Returns {text, tool_calls, output_items, status}."""
    kwargs = {"model": config.MODEL_ID, "instructions": system, "input": items,
              "reasoning": {"effort": effort or config.AGENT_EFFORT}, "max_output_tokens": max_output or config.AGENT_MAX_OUTPUT}
    if tools:
        kwargs["tools"] = tools
    if temperature is not None:
        kwargs["temperature"] = temperature
    response = get_client().responses.create(**kwargs)
    meter.record(config.MODEL_ID, response.usage, label)
    calls = [{"name": item.name, "arguments": item.arguments, "call_id": item.call_id}
             for item in response.output if item.type == "function_call"]
    return {"text": response.output_text, "tool_calls": calls,
            "output_items": list(response.output), "status": response.status}


def extract_json(text):
    """Pull the first JSON object out of a model reply (tolerates code fences and extra words)."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None
