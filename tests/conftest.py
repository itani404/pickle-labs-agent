"""Shared test setup: offline mode, temporary logs, and the scripted fake model (notebook cell 20, top)."""

import json
import os
import sys
from pathlib import Path

os.environ["PICKLE_OFFLINE"] = "1"      # any real API call raises; set before the package is imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from pickle_agent.config import settings  # noqa: E402
from pickle_agent.tools import logbook  # noqa: E402


@pytest.fixture
def tmp_logs(tmp_path, monkeypatch):
    """The notebook swapped LOG_DIR and QUIET_LOGS inside try/finally; this does the same per test."""
    monkeypatch.setattr(settings, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logbook, "QUIET_LOGS", True)
    return tmp_path


class FakeLLM:
    """Replays scripted answers and records what the loop sent."""

    def __init__(self, *script):
        self.script, self.calls = list(script), []

    def __call__(self, system, items, tools=None, **kwargs):
        self.calls.append({"system": system, "items": list(items), "tools": tools, **kwargs})
        return self.script.pop(0)


def text_answer(text):
    return {"text": text, "tool_calls": [], "output_items": [], "status": "completed"}


def tool_answer(name, arguments, call_id="call_1"):
    call = {"name": name, "arguments": json.dumps(arguments), "call_id": call_id}
    return {"text": "", "tool_calls": [call], "status": "completed",
            "output_items": [{"type": "function_call", **call}]}
