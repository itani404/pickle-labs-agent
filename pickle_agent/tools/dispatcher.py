"""Step 9. Dispatch: the guard between the model's tool request and the code (notebook section 4, cell 15).

Errors are returned to the model as data, never raised.
"""

import json

from .definitions import TOOL_BY_NAME
from .functions import TOOL_IMPL


def dispatch(name, arguments, allowed=None):
    """Run a tool call from the model. Always returns a dict, never raises, so the loop can hand errors back."""
    if name not in TOOL_IMPL:
        return {"status": "error", "reason": f"unknown tool '{name}'"}
    if allowed is not None and name not in allowed:
        return {"status": "error", "reason": f"tool '{name}' is not available for this request"}
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
    except (ValueError, TypeError):
        return {"status": "error", "reason": "arguments were not valid JSON"}
    if not isinstance(args, dict):
        return {"status": "error", "reason": "arguments must be a JSON object"}
    schema = TOOL_BY_NAME[name]["inputSchema"]
    missing = [field for field in schema["required"] if field not in args]
    extra = [field for field in args if field not in schema["properties"]]
    if missing or extra:
        return {"status": "error", "reason": f"missing arguments {missing}, unexpected arguments {extra}"}
    if not all(isinstance(value, str) for value in args.values()):
        return {"status": "error", "reason": "all arguments must be strings"}
    try:
        return TOOL_IMPL[name](**args)
    except Exception as error:                      # a tool bug must not crash the chat
        return {"status": "error", "reason": f"tool failed: {error}"}
