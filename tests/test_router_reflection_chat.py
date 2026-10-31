"""Router parsing (cell 23), reflection parsing (cell 28) and the full chat turn (cell 32). No API calls."""

from conftest import FakeLLM, text_answer, tool_answer
from pickle_agent import config
from pickle_agent.chat import chat_turn, format_trace
from pickle_agent.logbook import read_log
from pickle_agent.reflection import reflect
from pickle_agent.router import classify_intent, parse_router_output


def test_router_parsing_and_prompt():
    assert parse_router_output('{"intent": "lead_collection", "reason": "wants a quote"}') == ("lead_collection", "wants a quote", True)
    assert parse_router_output('```json\n{"intent": "feedback_or_unanswered"}\n```')[0] == "feedback_or_unanswered"
    assert parse_router_output('Sure! {"intent": "general_question", "reason": "asks price"} Hope that helps')[2] is True
    assert parse_router_output('{"intent": "refund_request"}') == ("general_question", "router output could not be parsed, defaulted", False)
    assert parse_router_output("I think it is a lead")[2] is False
    assert parse_router_output("")[2] is False and parse_router_output(None)[2] is False

    fake = FakeLLM(text_answer('{"intent": "lead_collection", "reason": "gives email"}'))
    history = [{"role": "user", "content": "I'd like to start a Build Sprint"},
               {"role": "assistant", "content": "Great. What are your name and email?"}]
    result = classify_intent("sam@reed.dev", history, llm=fake)
    call = fake.calls[0]
    assert result == {"intent": "lead_collection", "reason": "gives email", "parsed_ok": True}
    assert "What are your name and email?" in call["items"][0]["content"] and "New message: sam@reed.dev" in call["items"][0]["content"]
    assert call["temperature"] == 0 and call["effort"] == config.ROUTER_EFFORT and call["tools"] is None


def test_reflection_parsing(tmp_logs):
    bad = '{"ok": false, "issues": ["invented a price"], "revised": "An Agent Autopsy is 4,500 USD flat."}'
    result = reflect("How much is an autopsy?", "It's 499 dollars.", [], llm=FakeLLM(text_answer(bad)))
    assert result["ok"] is False and result["final"] == "An Agent Autopsy is 4,500 USD flat." and result["parsed_ok"]

    good = '{"ok": true, "issues": [], "revised": ""}'
    result = reflect("hi", "Hello. State your business.", [], llm=FakeLLM(text_answer(good)))
    assert result["ok"] is True and result["final"] == "Hello. State your business."

    result = reflect("hi", "Hello.", [], llm=FakeLLM(text_answer("no json here")))        # broken reviewer
    assert result["parsed_ok"] is False and result["final"] == "Hello."

    result = reflect("hi", "Hello.", [], llm=FakeLLM(text_answer('{"ok": false, "issues": [], "revised": ""}')))
    assert result["final"] == "Hello."                                                    # flagged but nothing to revise to

    fake = FakeLLM(text_answer(good))
    reflect("and the price?", "4,500 USD.", [], llm=fake,
            history=[{"role": "user", "content": "Tell me about autopsies"}, {"role": "assistant", "content": "It is an audit."}])
    assert "user: Tell me about autopsies" in fake.calls[0]["items"][0]["content"]      # the reviewer sees the earlier turns

    entries = read_log("reflection")
    assert len(entries) == 5 and entries[0]["draft"] == "It's 499 dollars." and entries[0]["final"].startswith("An Agent Autopsy")


def test_full_chat_turn(tmp_logs):
    fake = FakeLLM(
        text_answer('{"intent": "lead_collection", "reason": "gives contact details"}'),                  # router
        tool_answer("record_customer_interest", {"email": "dana@acme.io", "name": "Dana Cole", "message": "autopsy"}),
        text_answer("Recorded. Expect an email from Omar."),                                         # agent draft
        text_answer('{"ok": true, "issues": [], "revised": ""}'),                                          # reflection
    )
    result = chat_turn("Dana Cole, dana@acme.io, autopsy please", [], reflection=True, llm=fake)
    assert result["route"] == "lead_collection" and result["tool_calls"][0]["result"] == {"status": "recorded"}
    assert result["reply"] == result["draft"] and result["reflection"]["ok"] is True and len(fake.calls) == 4
    trace = format_trace(result)
    assert "lead_collection" in trace and "record_customer_interest" in trace and "approved" in trace

    fake = FakeLLM(text_answer('{"intent": "general_question", "reason": "asks price"}'),
                   text_answer("It's 499."),
                   text_answer('{"ok": false, "issues": ["invented price"], "revised": "4,500 USD flat."}'))
    result = chat_turn("price?", [], reflection=True, llm=fake)
    assert result["reply"] == "4,500 USD flat." and result["draft"] == "It's 499."
    assert "Original draft" in format_trace(result)

    fake = FakeLLM(text_answer('{"intent": "general_question", "reason": "hello"}'), text_answer("Hello there."),
                   text_answer("this is not json"))                    # a broken reviewer must not look like an approval
    result = chat_turn("hi", [], reflection=True, llm=fake)
    assert result["reflection"]["parsed_ok"] is False and "could not be read" in format_trace(result)
    assert "approved" not in format_trace(result)

    fake = FakeLLM(text_answer('{"intent": "general_question", "reason": "hello"}'), text_answer("State your business."))
    result = chat_turn("hi", [], reflection=False, llm=fake)
    assert result["reflection"] is None and len(fake.calls) == 2           # reflection off means no third call


def test_gradio_app_builds():
    from pickle_agent.app import build_demo
    assert build_demo() is not None
