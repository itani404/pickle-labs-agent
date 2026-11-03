"""Step 7. Tool gating: which tools each route gets, and the tool documentation (notebook section 4, cell 14)."""

import json

from .definitions import TOOL_BY_NAME, TOOL_DEFS, to_openai_tool

# Tool gating: each intent gets the tools that fit it. The two open-ended routes also keep the other tool as a
# safety net, so a misrouted message can still be logged (a lead inside a question, an unknown question inside a lead).
ROUTE_TOOLS = {
    "general_question": ["record_feedback", "record_customer_interest"],
    "lead_collection": ["record_customer_interest", "record_feedback"],
    "feedback_or_unanswered": ["record_feedback"],
}


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
