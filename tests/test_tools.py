"""Both tools and the dispatcher (notebook cell 16). Logs go to a temporary folder."""

from pickle_agent.tools.logbook import read_log
from pickle_agent.tools.dispatcher import dispatch


def test_tools_and_dispatcher(tmp_logs):
    ok = dispatch("record_customer_interest",
                  '{"email": "dana@acme.io", "name": "Dana Cole", "message": "Wants an Agent Autopsy"}')
    assert ok == {"status": "recorded"}

    dup = dispatch("record_customer_interest",
                   {"email": "DANA@acme.io", "name": "Dana Cole", "message": "Wants an Agent Autopsy"})
    assert dup["status"] == "duplicate"

    assert dispatch("record_customer_interest", {"email": "not-an-email", "name": "Dana", "message": "hi"})["status"] == "error"
    assert dispatch("record_customer_interest", {"email": "a@b.co", "name": " ", "message": "hi"})["status"] == "error"
    assert dispatch("record_customer_interest", {"email": "a@b.co", "name": "Al", "message": ""})["status"] == "error"

    assert dispatch("record_feedback", {"question": "Do you have SOC 2?"}) == {"status": "recorded"}
    assert dispatch("record_feedback", {"question": "  "})["status"] == "error"

    assert dispatch("no_such_tool", {})["status"] == "error"
    assert dispatch("record_feedback", {})["status"] == "error"                                  # missing argument
    assert dispatch("record_feedback", {"question": "x y z", "extra": "1"})["status"] == "error"  # unexpected argument
    assert dispatch("record_feedback", {"question": 42})["status"] == "error"                    # wrong type
    assert dispatch("record_feedback", "{not json")["status"] == "error"
    assert dispatch("record_feedback", {"question": "x y z"}, allowed=["record_customer_interest"])["status"] == "error"

    leads, feedback = read_log("leads"), read_log("feedback")
    assert len(leads) == 1 and leads[0]["name"] == "Dana Cole" and "time" in leads[0]
    assert len(feedback) == 1 and feedback[0]["question"] == "Do you have SOC 2?"
