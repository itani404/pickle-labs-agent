"""The two tools, their MCP-style definitions, route gating and the dispatcher (notebook section 4, cells 14 and 15).

Each tool is defined once, as a dictionary in the style of an MCP tool definition (name, description,
inputSchema, outputSchema). That single definition is printed as documentation, sent to the model, and
used to check arguments. Errors are returned to the model as data, never raised.
"""

import json
import re

from .logbook import log_event, read_log

TOOL_DEFS = [
    {
        "name": "record_customer_interest",
        "description": "Save a customer's contact details and what they want. Call it once you have their name and email.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "The customer's email address"},
                "name": {"type": "string", "description": "The customer's name"},
                "message": {"type": "string", "description": "What the customer wants, in one or two sentences"},
            },
            "required": ["email", "name", "message"],
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["recorded", "duplicate", "error"]},
                "reason": {"type": "string", "description": "Present when status is error"},
            },
            "required": ["status"],
        },
    },
    {
        "name": "record_feedback",
        "description": "Log a question you cannot answer from the business knowledge, or feedback from the customer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The customer's exact question or feedback"},
            },
            "required": ["question"],
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["recorded", "error"]},
                "reason": {"type": "string", "description": "Present when status is error"},
            },
            "required": ["status"],
        },
    },
]
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOL_DEFS}

# Tool gating: each intent gets the tools that fit it. The two open-ended routes also keep the other tool as a
# safety net, so a misrouted message can still be logged (a lead inside a question, an unknown question inside a lead).
ROUTE_TOOLS = {
    "general_question": ["record_feedback", "record_customer_interest"],
    "lead_collection": ["record_customer_interest", "record_feedback"],
    "feedback_or_unanswered": ["record_feedback"],
}


def to_openai_tool(tool):
    """MCP-style definition -> the function-tool format the OpenAI Responses API expects."""
    return {"type": "function", "name": tool["name"], "description": tool["description"],
            "parameters": tool["inputSchema"], "strict": True}


def tools_for_route(route):
    return [to_openai_tool(TOOL_BY_NAME[name]) for name in ROUTE_TOOLS[route]]


def print_tool_docs():
    """Documentation printed from the same definitions the model receives."""
    for tool in TOOL_DEFS:
        schema = tool["inputSchema"]
        print(f"{tool['name']}  ({tool['description']})")
        for field, spec in schema["properties"].items():
            required = "required" if field in schema["required"] else "optional"
            print(f"    in : {field}: {spec['type']}, {required}. {spec['description']}")
        print(f"    out: {json.dumps(tool['outputSchema']['properties']['status']['enum'])} (status)\n")
    for route, names in ROUTE_TOOLS.items():
        print(f"route {route:<24} exposes {names}")


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def record_customer_interest(email, name, message):
    email, name, message = email.strip(), name.strip(), message.strip()
    if len(name) < 2:
        return {"status": "error", "reason": "name is missing or too short"}
    if not EMAIL_RE.match(email):
        return {"status": "error", "reason": f"'{email}' is not a valid email address"}
    if not message:
        return {"status": "error", "reason": "message is empty"}
    for lead in read_log("leads"):
        if lead["email"].lower() == email.lower() and lead["message"] == message:
            return {"status": "duplicate", "reason": "this lead was already recorded"}
    log_event("leads", {"email": email, "name": name, "message": message})
    return {"status": "recorded"}


def record_feedback(question):
    question = question.strip()
    if len(question) < 3:
        return {"status": "error", "reason": "question is empty"}
    log_event("feedback", {"question": question})
    return {"status": "recorded"}


TOOL_IMPL = {"record_customer_interest": record_customer_interest, "record_feedback": record_feedback}


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
