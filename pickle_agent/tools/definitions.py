"""Step 6. Tool definitions: what the model is told it can call (notebook section 4, cell 14).

Each tool is defined once, as a dictionary in the style of an MCP tool definition (name, description,
inputSchema, outputSchema). That single definition is printed as documentation, sent to the model, and
used to check arguments.
"""

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


def to_openai_tool(tool):
    """MCP-style definition -> the function-tool format the OpenAI Responses API expects."""
    return {"type": "function", "name": tool["name"], "description": tool["description"],
            "parameters": tool["inputSchema"], "strict": True}
