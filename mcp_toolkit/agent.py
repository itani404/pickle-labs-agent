"""Pickle Labs front-desk agent: the OpenAI Agents SDK as MCP host and client (Assignment C5).

The host starts the MCP server (mcp_toolkit/server.py) as a subprocess and talks to it over stdio
through one MCP client (MCPServerStdio). At start-up it discovers the server's tools and reads the
service catalogue resource; the catalogue goes into the instructions, the tools go to the model.

Every tool call is printed on its way out and on its way back. The server logs its side of the
same call on stderr; the host pipes that stderr into its own console and prints it indented under
the call, so one terminal shows the whole round trip without the two sides writing over each other:

    agent (model picks a tool) -> MCP client -> MCP server -> tool code -> server -> client -> agent

Usage:
    python -m mcp_toolkit.agent                      interactive chat
    python -m mcp_toolkit.agent --ask "question"     one question, then exit
    python -m mcp_toolkit.agent --list               list the server's tools and resources, no model calls
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from agents import Agent, RunHooks, Runner, trace
from agents.mcp import MCPServerStdio
from dotenv import find_dotenv, load_dotenv
from mcp import stdio_client
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

REPO_DIR = Path(__file__).resolve().parent.parent
TZ = ZoneInfo("Asia/Beirut")
DEFAULT_MODEL = "gpt-6-luna"
CATALOGUE_URI = "picklelabs://services"

INSTRUCTIONS = """You are Dr. Rick, the AI front desk of Pickle Labs, a three-person AI consultancy in Beirut. Dry humour is allowed; accuracy comes first. Keep replies to two to five sentences.

Today is {today} (Beirut time). Turn relative dates such as "next Tuesday" into YYYY-MM-DD yourself before calling a tool.

Rules:
1. Use the Pickle Labs tools for availability and email. Never invent free times.
2. Never say an email was sent unless a tool returned a receipt for it in this conversation.
3. If a tool returns an error, explain the reason in plain words and say what the user can do next. Do not repeat the same call with the same arguments.
4. Ask for missing details (a name, an email address) instead of guessing them.
5. Answer questions about services, prices and hours only from the catalogue below. If it is not there, say so.
6. Do not use em dashes or en dashes; write "09:00 to 18:00" and use commas or full stops instead.

<service_catalogue>
{catalogue}
</service_catalogue>"""


def _today() -> datetime:
    pinned = os.environ.get("PICKLE_NOW")  # same override the server honours, so both agree on "today"
    return datetime.fromisoformat(pinned).replace(tzinfo=TZ) if pinned else datetime.now(TZ)


def _short(value: object, limit: int = 300) -> str:
    if isinstance(value, dict) and "text" in value:  # MCP results arrive as a text content part
        value = value["text"]
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _summary(result: object) -> tuple[bool, str]:
    """(ok, one readable line) for a tool result, instead of the raw JSON the model receives."""
    text = _short(result, 10_000)
    try:
        data = json.loads(text)
    except ValueError:
        return False, _short(text, 200)  # tool errors arrive as "CODE: reason"
    if "offered" in data:
        times = ", ".join(f"{o['weekday'][:3]} {o['date'][5:]} {o['start']} ({o['consultant']})" for o in data["offered"])
        return True, f"emailed {len(data['offered'])} option(s) to {data['email']['to']}: {times}"
    if "slots" in data:
        starts = ", ".join(s["start"] for s in data["slots"]) or "none"
        return True, f"{len(data['slots'])} free slot(s) on {data['weekday']} {data['date']}: {starts}"
    if "message_id" in data:
        return True, f"sent to {data['to']} ({data['outbox_file'].rsplit('/', 1)[-1]})"
    return True, _short(text, 200)


SERVER_LINE = re.compile(r"^\d\d:\d\d:\d\d \[mcp-server\] (.*)$")
FASTMCP_NOISE = re.compile(r"^\[[^\]]*\]\s*|\s+\S+\.py:\d+$")
THINKING = ["Pickling", "Brining", "Fermenting", "Marinating", "Jarring", "Dill-iberating",
            "Crunching", "Vinegaring", "Rick-ing", "Checking the calendar", "Consulting the jar"]


class Display:
    """Everything the host prints: start-up panel, thinking status, tool calls, server log, replies."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console(highlight=False)
        self.nested = False  # inside offer_scoping_slots, the server is calling the other two tools

    def _row(self, prefix: Text, body: Text) -> None:
        """prefix + body, with wrapped lines of body indented under its first line."""
        grid = Table.grid()
        grid.add_column(no_wrap=True)
        grid.add_column()
        grid.add_row(prefix, body)
        self.console.print(grid)

    def server_line(self, line: str) -> None:
        """One stderr line from the server process (called from the pipe reader thread)."""
        if not line.strip():
            return
        match = SERVER_LINE.match(line.rstrip())
        if not match:  # FastMCP's own log lines: keep them, but quiet (no timestamp, no source file)
            text = FASTMCP_NOISE.sub("", " ".join(line.split()))
            self._row(Text("      server │ ", "grey42"), Text(text, "grey42"))
            return
        msg = match.group(1)
        if msg.lstrip().startswith("offer_scoping_slots -> "):
            self.nested = True  # the next call line shows it, indented
            return
        if self.nested:
            msg = ("    " if msg.startswith(" ") else "  ↳ ") + msg
        style = "red" if msg.strip().startswith("error") else "magenta"
        self._row(Text("      server │ ", "magenta"), Text(msg, style))

    def startup(self, server_name: str, tools, resources) -> None:
        table = Table(box=None, pad_edge=False, show_header=True, header_style="bold")
        table.add_column("Tool", style="cyan", no_wrap=True)
        table.add_column("Category", style="yellow", no_wrap=True)
        table.add_column("What it does")
        for tool in tools:
            tags = (tool.meta or {}).get("fastmcp", {}).get("tags", [])
            table.add_row(tool.name, ", ".join(tags), tool.description.splitlines()[0])
        for res in resources:
            table.add_row(str(res.uri), "resource", f"read by the host at start-up ({res.mime_type})")
        title = f"[bold]Pickle Labs front desk[/]  ·  MCP server '{server_name}' connected over stdio, {len(tools)} tools"
        self.console.print(Panel(table, title=title, title_align="left", border_style="green"))

    def question(self, text: str) -> None:
        self.console.print(Text.assemble(("\nyou › ", "bold green"), text))

    def tool_start(self, n: int, name: str, args: str) -> None:
        self.nested = False
        self.console.print()
        self._row(Text(f"  {n}. agent → MCP client → server  ", "bold cyan"), Text.assemble((name, "bold cyan"), (f" {args}", "cyan")))

    def tool_end(self, ok: bool, line: str) -> None:
        self.nested = False
        mark, style = ("✓", "green") if ok else ("✗", "red")
        self._row(Text(f"     {mark} server → MCP client → agent  ", f"bold {style}"), Text(line, style))

    def reply(self, text: str) -> None:
        self.console.print()
        self.console.print(Panel(Markdown(text), title="[bold]Dr. Rick[/]", title_align="left", border_style="blue"))

    async def thinking(self, task):
        """Run `task` behind a rotating status line; the round-trip lines print above it."""
        started = time.monotonic()
        verb = random.choice(THINKING)
        with self.console.status(f"[yellow]{verb}...[/]", spinner="dots") as status:
            job = asyncio.ensure_future(task)
            while not job.done():
                await asyncio.wait({job}, timeout=1.5)
                verb = random.choice([v for v in THINKING if v != verb])
                status.update(f"[yellow]{verb}...[/] [grey50]{time.monotonic() - started:.0f}s[/]")
            return job.result()


class RoundTripPrinter(RunHooks):
    """Prints the agent's side of each tool call: the request leaving and the result coming back."""

    def __init__(self, display: Display | None = None):
        self.display = display or Display()
        self.calls: list[tuple[str, str]] = []

    async def on_tool_start(self, context, agent, tool):
        args = getattr(context, "tool_arguments", "")
        self.calls.append((tool.name, args))
        self.display.tool_start(len(self.calls), tool.name, args)

    async def on_tool_end(self, context, agent, tool, result):
        await asyncio.sleep(0.05)  # let the server's log lines for this call print first
        self.display.tool_end(*_summary(result))


class PickleServerStdio(MCPServerStdio):
    """MCPServerStdio that sends the server's stderr to `errlog` instead of straight to the terminal."""

    def __init__(self, *args, errlog=sys.stderr, **kwargs):
        super().__init__(*args, **kwargs)
        self.errlog = errlog

    def create_streams(self):
        return stdio_client(self.params, errlog=self.errlog)


def _pipe_to(on_line: Callable[[str], None]):
    """A writable file whose lines are handed to `on_line` by a background thread."""
    read_fd, write_fd = os.pipe()

    def pump():
        with os.fdopen(read_fd, encoding="utf-8", errors="replace") as lines:
            for line in lines:
                on_line(line)

    threading.Thread(target=pump, daemon=True).start()
    return os.fdopen(write_fd, "w")


def open_server(on_log: Callable[[str], None] | None = None) -> MCPServerStdio:
    """The MCP client for our server. The server runs as `python -m mcp_toolkit.server`.

    With `on_log`, each line the server logs on stderr goes to that callback instead of the terminal.
    """
    passthrough = ("PATH", "HOME", "PICKLE_NOW", "PICKLE_OUTBOX", "PICKLE_CALENDAR")
    env = {key: os.environ[key] for key in passthrough if key in os.environ}
    if on_log:
        env["COLUMNS"] = "500"  # FastMCP's own log is rich-formatted; one line each, the host wraps it
    return PickleServerStdio(
        name="pickle-labs",
        params={"command": sys.executable, "args": ["-m", "mcp_toolkit.server"], "cwd": str(REPO_DIR), "env": env},
        cache_tools_list=True,
        client_session_timeout_seconds=30,
        errlog=_pipe_to(on_log) if on_log else sys.stderr,
    )


async def read_catalogue(server: MCPServerStdio) -> str:
    result = await server.read_resource(CATALOGUE_URI)
    return result.contents[0].text


def build_agent(server: MCPServerStdio, catalogue: str, model=None) -> Agent:
    return Agent(
        name="Pickle Labs front desk",
        instructions=INSTRUCTIONS.format(today=_today().strftime("%A %Y-%m-%d"), catalogue=catalogue),
        mcp_servers=[server],
        model=model or os.environ.get("PICKLE_MODEL", DEFAULT_MODEL),
    )


async def describe(server: MCPServerStdio, display: Display) -> None:
    tools = await server.list_tools()
    resources = await server.list_resources()
    display.startup(server.name, tools, resources.resources)


async def ask(agent: Agent, history: list, question: str, hooks: RoundTripPrinter) -> list:
    hooks.calls.clear()  # number the tool calls per question
    with trace("pickle-labs front desk"):
        run = Runner.run(agent, history + [{"role": "user", "content": question}], hooks=hooks)
        result = await hooks.display.thinking(run)
    hooks.display.reply(str(result.final_output))
    return result.to_input_list()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ask", help="ask one question and exit")
    parser.add_argument("--list", action="store_true", help="list tools and resources, then exit (no model calls)")
    args = parser.parse_args()

    display = Display()
    async with open_server(on_log=display.server_line) as server:
        await describe(server, display)
        if args.list:
            return
        load_dotenv(find_dotenv(usecwd=True))  # OPENAI_API_KEY
        agent = build_agent(server, await read_catalogue(server))
        hooks = RoundTripPrinter(display)
        history: list = []
        if args.ask:
            display.question(args.ask)
            await ask(agent, history, args.ask, hooks)
            return
        display.console.print("Type a message, or 'quit' to leave.", style="grey50")
        while True:
            try:
                question = display.console.input("\n[bold green]you ›[/] ").strip()
            except EOFError:
                break
            if question.lower() in {"quit", "exit"}:
                break
            if question:
                try:
                    history = await ask(agent, history, question, hooks)
                except Exception as exc:  # e.g. a network or API error: report it and keep the session
                    display.console.print(Text(f"The model call failed ({type(exc).__name__}: {exc}). Try again.", "red"))


if __name__ == "__main__":
    asyncio.run(main())
