"""The full host round trip with no API calls.

A scripted model stands in for the LLM: it asks for one tool, then answers with the tool result
it was given. Everything else is real: the Agents SDK Runner, the MCP client (MCPServerStdio),
the server subprocess over stdio and the tool code.
"""

import asyncio
import json

from agents import Runner
from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from mcp_toolkit.agent import RoundTripPrinter, build_agent, open_server, read_catalogue


def _text(output) -> str:
    """Tool output reaches the model as a string or as a list of content parts."""
    if isinstance(output, str):
        return output
    return "".join(part.get("text", "") for part in output if isinstance(part, dict))


class ScriptedModel(Model):
    """Turn 1: call `tool` with `arguments`. Turn 2: reply with the last tool output it received."""

    def __init__(self, tool: str, arguments: dict):
        self.tool, self.arguments = tool, arguments
        self.seen_tools: list[str] = []
        self.seen_instructions = ""

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kwargs):
        self.seen_tools = [t.name for t in tools]
        self.seen_instructions = system_instructions or ""
        outputs = [item for item in input if isinstance(item, dict) and item.get("type") == "function_call_output"]
        if not outputs:
            item = ResponseFunctionToolCall(type="function_call", id="fc_1", call_id="call_1", name=self.tool, arguments=json.dumps(self.arguments), status="completed")
        else:
            text = _text(outputs[-1]["output"])
            item = ResponseOutputMessage(type="message", id="msg_1", role="assistant", status="completed", content=[ResponseOutputText(type="output_text", text=text, annotations=[])])
        return ModelResponse(output=[item], usage=Usage(), response_id=None)

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError


def run(tool: str, arguments: dict):
    async def go():
        async with open_server() as server:
            model = ScriptedModel(tool, arguments)
            agent = build_agent(server, await read_catalogue(server), model=model)
            hooks = RoundTripPrinter()
            result = await Runner.run(agent, "scripted turn", hooks=hooks)
            return model, hooks, result.final_output
    return asyncio.run(go())


def test_host_discovers_tools_and_reads_the_resource():
    """The host finds all 3 tools on its own and puts the service catalogue into the instructions."""
    model, _, _ = run("find_open_slots", {"date": "2026-11-03"})
    assert sorted(model.seen_tools) == ["find_open_slots", "offer_scoping_slots", "send_email"]
    assert "Agent Autopsy" in model.seen_instructions  # the catalogue resource reached the instructions
    assert "Monday 2026-11-02" in model.seen_instructions  # host and server agree on "today"


def test_round_trip_data_tool():
    """Model picks find_open_slots; the call goes through the MCP client to the server and the slots come back."""
    _, hooks, reply = run("find_open_slots", {"date": "2026-11-03"})
    assert hooks.calls == [("find_open_slots", '{"date": "2026-11-03"}')]
    assert '"weekday":"Tuesday"' in reply.replace(" ", "")


def test_round_trip_orchestration_tool(pinned_env):
    """Model picks offer_scoping_slots; one call through the client, one email lands in the outbox."""
    _, hooks, reply = run("offer_scoping_slots", {"client_name": "Lina", "client_email": "lina@example.com", "from_date": "2026-11-02"})
    assert [name for name, _ in hooks.calls] == ["offer_scoping_slots"]
    assert len(list((pinned_env / "outbox").glob("*.eml"))) == 1
    assert "message_id" in reply


def test_round_trip_failure_reaches_the_model_as_a_clear_error():
    """A Saturday reaches the model as a clear NOT_A_WORKING_DAY error, not a crash."""
    _, _, reply = run("find_open_slots", {"date": "2026-11-07"})
    assert reply.startswith("NOT_A_WORKING_DAY")
