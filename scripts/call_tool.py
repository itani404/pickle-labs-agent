"""Call one tool on the MCP server by hand, with no model in the loop.

Starts the server over stdio exactly as the agent does, sends one tools/call request and prints the
raw result, including the isError flag. Useful for checking a tool, or a failure case, directly.

    python scripts/call_tool.py                       list tools and resources
    python scripts/call_tool.py find_open_slots '{"date": "2026-11-03"}'
    python scripts/call_tool.py find_open_slots '{"date": "2026-11-07"}'      (failure: a Saturday)
    python scripts/call_tool.py send_email '{"to": "omar@picklelabs.example", "subject": "Hi", "body": "Test"}'
    python scripts/call_tool.py offer_scoping_slots '{"client_name": "Lina", "client_email": "lina@example.com", "from_date": "2026-11-05"}'
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

SERVER = Path(__file__).resolve().parent.parent / "mcp_toolkit" / "server.py"
PASSTHROUGH = ("PATH", "HOME", "PICKLE_NOW", "PICKLE_OUTBOX", "PICKLE_CALENDAR")


async def main() -> None:
    async with Client(PythonStdioTransport(SERVER, cwd=str(SERVER.parent.parent), env={k: os.environ[k] for k in PASSTHROUGH if k in os.environ})) as client:
        if len(sys.argv) < 2:
            for tool in await client.list_tools():
                print(f"{tool.name}\n  {tool.description.splitlines()[0]}\n  input: {json.dumps(tool.input_schema['properties'])}\n")
            for res in await client.list_resources():
                print(f"resource {res.uri}")
            return
        name = sys.argv[1]
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        print(f"-> tools/call {name} {json.dumps(args)}")
        result = await client.call_tool(name, args, raise_on_error=False)
        print(f"<- isError={result.is_error}")
        if result.structured_content and not result.is_error:
            print(json.dumps(result.structured_content, indent=2))
        else:
            print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
