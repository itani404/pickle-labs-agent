import asyncio
import sys
from pathlib import Path

import pytest
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_toolkit.server import mcp  # noqa: E402

# Monday 2 November 2026, 08:00 Beirut time. Every test sees the same "now".
NOW = "2026-11-02T08:00"


@pytest.fixture(autouse=True)
def pinned_env(tmp_path, monkeypatch):
    """Fixed clock and a throwaway outbox for every test; the real calendar unless a test swaps it."""
    monkeypatch.setenv("PICKLE_NOW", NOW)
    monkeypatch.setenv("PICKLE_OUTBOX", str(tmp_path / "outbox"))
    return tmp_path


def call(tool: str, args: dict):
    """Call one tool through a real MCP client session (in memory, no subprocess, no model)."""
    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(tool, args, raise_on_error=False)
    return asyncio.run(go())


def error_code(result) -> str:
    assert result.is_error, f"expected an error, got {result.structured_content}"
    return result.content[0].text.split(":", 1)[0]


# ---------------------------------------------------------------- readable summary at the end of a run
# Each test's docstring is its one-line description; the summary groups them by tool.

GROUPS = [  # (test module, test name prefix, title), matched top to bottom, printed in this order
    ("test_server", "test_find_open_slots", "Data tool: find_open_slots"),
    ("test_server", "test_send_email", "Action tool: send_email"),
    ("test_server", "test_offer", "Orchestration tool: offer_scoping_slots"),
    ("test_agent_offline", "", "Full round trip: agent → MCP client → MCP server → back (scripted model, no API)"),
]
WHOLE = "The toolkit as a whole"
ORDER = [WHOLE] + [title for _, _, title in GROUPS]
_described: dict[str, tuple[str, str]] = {}  # nodeid -> (group, description), in collection order
_outcomes: dict[str, str] = {}


def pytest_collection_modifyitems(items):
    for item in items:
        module, name = item.module.__name__, item.name
        group = next((title for mod, prefix, title in GROUPS if module == mod and name.startswith(prefix)), WHOLE)
        doc = (item.function.__doc__ or name).strip().splitlines()[0]
        _described[item.nodeid] = (group, doc)


def pytest_runtest_logreport(report):
    if report.failed:  # a failure in setup, the test itself or teardown
        _outcomes[report.nodeid] = "failed"
    elif report.when == "call":
        _outcomes.setdefault(report.nodeid, report.outcome)


def pytest_terminal_summary(terminalreporter):
    by_group: dict[str, list[tuple[str, str]]] = {}
    for nodeid, (group, doc) in _described.items():
        if nodeid in _outcomes:
            by_group.setdefault(group, []).append((doc, _outcomes[nodeid]))
    if not by_group:
        return
    terminalreporter.write_sep("=", "what was tested")
    for group in sorted(by_group, key=ORDER.index):
        terminalreporter.write_line("")
        terminalreporter.write_line(group, bold=True)
        for doc, outcome in by_group[group]:
            ok = outcome == "passed"
            terminalreporter.write_line(f"  {'✓' if ok else '✗'} {doc}", green=ok, red=not ok)
