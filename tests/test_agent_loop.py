"""The tool loop with a scripted fake model (notebook cell 20). No API calls."""

import json

from conftest import FakeLLM, text_answer, tool_answer
from pickle_agent.config import settings
from pickle_agent.loop.agent_loop import FALLBACK_REPLY, agent_turn
from pickle_agent.memory.history import clean_history
from pickle_agent.tools.logbook import read_log


def test_plain_text_turn_carries_history_and_gates_tools(tmp_logs):
    fake = FakeLLM(text_answer("Four services. Try to keep up."))
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "What do you want?"}]
    reply, trace = agent_turn("What do you sell?", history, "general_question", llm=fake)
    assert reply == "Four services. Try to keep up." and trace == []
    sent = fake.calls[0]
    assert [m["content"] for m in sent["items"]] == ["hi", "What do you want?", "What do you sell?"]
    assert [t["name"] for t in sent["tools"]] == ["record_feedback", "record_customer_interest"]   # general route: both tools
    assert 'intent="general_question"' in sent["system"]


def test_tool_turn_returns_result_to_model(tmp_logs):
    fake = FakeLLM(tool_answer("record_customer_interest",
                               {"email": "dana@acme.io", "name": "Dana Cole", "message": "Agent Autopsy"}),
                   text_answer("Done, Dana. Omar will email you."))
    reply, trace = agent_turn("I'm Dana, dana@acme.io, I want an Agent Autopsy", [], "lead_collection", llm=fake)
    assert trace[0]["tool"] == "record_customer_interest" and trace[0]["result"] == {"status": "recorded"}
    assert reply.startswith("Done, Dana")
    returned = fake.calls[1]["items"][-1]
    assert returned["type"] == "function_call_output" and returned["call_id"] == "call_1"
    assert json.loads(returned["output"]) == {"status": "recorded"}


def test_tool_error_is_handed_back(tmp_logs):
    fake = FakeLLM(tool_answer("record_customer_interest", {"email": "dana", "name": "Dana", "message": "hi"}),
                   text_answer("That email looks broken. Try again?"))
    reply, trace = agent_turn("dana", [], "lead_collection", llm=fake)
    assert trace[0]["result"]["status"] == "error"
    assert "not a valid email" in fake.calls[1]["items"][-1]["output"]


def test_disallowed_tool_is_refused_and_safety_net_works(tmp_logs):
    # seed one lead so the "nothing new was recorded" check matches the notebook's sequence
    agent_turn("seed", [], "lead_collection", llm=FakeLLM(
        tool_answer("record_customer_interest", {"email": "dana@acme.io", "name": "Dana Cole", "message": "Agent Autopsy"}),
        text_answer("ok")))

    fake = FakeLLM(tool_answer("record_customer_interest", {"email": "a@b.co", "name": "Al", "message": "x"}),
                   text_answer("Sorry."))
    _, trace = agent_turn("hello", [], "feedback_or_unanswered", llm=fake)
    assert [t["name"] for t in fake.calls[0]["tools"]] == ["record_feedback"]
    assert trace[0]["result"]["status"] == "error" and len(read_log("leads")) == 1   # nothing new was recorded

    fake = FakeLLM(tool_answer("record_customer_interest", {"email": "eve@x.io", "name": "Eve Hart", "message": "quote"}),
                   text_answer("Noted."))
    _, trace = agent_turn("I'm Eve Hart, eve@x.io, quote please", [], "general_question", llm=fake)
    assert trace[0]["result"] == {"status": "recorded"}
    fake = FakeLLM(tool_answer("record_feedback", {"question": "Do you have SOC 2?"}), text_answer("Logged."))
    _, trace = agent_turn("Do you have SOC 2? Also I'm Dana", [], "lead_collection", llm=fake)
    assert trace[0]["result"] == {"status": "recorded"}


def test_round_cap_withholds_tools_on_last_round(tmp_logs):
    endless = [tool_answer("record_feedback", {"question": f"q{n}"}, f"c{n}") for n in range(settings.MAX_TOOL_ROUNDS)]
    fake = FakeLLM(*endless, tool_answer("record_feedback", {"question": "last"}, "c_last"))
    reply, trace = agent_turn("loop", [], "general_question", llm=fake)
    assert reply == FALLBACK_REPLY and fake.calls[-1]["tools"] is None and len(fake.calls) == settings.MAX_TOOL_ROUNDS + 1


def test_history_cleaning():
    messy = ([{"role": "assistant", "content": "orphan"}, {"role": "user", "content": "q"},
              {"role": "assistant", "content": "trace", "metadata": {"title": "Router and tools"}},
              {"role": "assistant", "content": [{"text": "a", "type": "text"}]},
              {"role": "assistant", "content": "**Router:** `general_question` (metadata lost)"}]
             + [{"role": "user", "content": f"u{n}"} for n in range(30)])
    cleaned = clean_history(messy)
    assert len(cleaned) <= settings.HISTORY_LIMIT and cleaned[0]["role"] == "user"
    assert [m["content"] for m in clean_history(messy[:5])] == ["q", "a"]       # trace messages are gone, even without metadata
