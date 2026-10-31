"""Unit tests for the three MCP tools, called through an in-memory MCP client. No API calls."""

import asyncio
import json
from email import message_from_bytes, policy
from pathlib import Path

from fastmcp import Client

from conftest import call, error_code
from mcp_toolkit.server import mcp


def outbox(tmp_path) -> list[Path]:
    return sorted((tmp_path / "outbox").glob("*.eml"))


# ---------------------------------------------------------------- the server as a whole

def test_exactly_three_tools_one_per_category():
    """Exactly 3 tools, tagged data, action, orchestration; each documents its errors; the Data tool is read-only."""
    async def go():
        async with Client(mcp) as client:
            return await client.list_tools(), await client.list_resources()
    tools, resources = asyncio.run(go())
    by_name = {t.name: t for t in tools}
    assert set(by_name) == {"find_open_slots", "send_email", "offer_scoping_slots"}
    tags = {name: t.meta["fastmcp"]["tags"] for name, t in by_name.items()}
    assert tags == {"find_open_slots": ["data"], "send_email": ["action"], "offer_scoping_slots": ["orchestration"]}
    for tool in tools:
        assert tool.description and "Errors:" in tool.description
        assert tool.output_schema is not None
        assert all("description" in p for p in tool.input_schema["properties"].values())
    assert by_name["find_open_slots"].annotations.read_only_hint is True
    assert by_name["send_email"].annotations.read_only_hint is False
    assert [str(r.uri) for r in resources] == ["picklelabs://services"]


def test_service_catalogue_resource():
    """The service catalogue is a resource (read by the host), not a fourth tool."""
    async def go():
        async with Client(mcp) as client:
            return await client.read_resource("picklelabs://services")
    data = json.loads(asyncio.run(go())[0].text)
    assert {s["name"] for s in data["services"]} >= {"Agent Autopsy", "Prompt Clinic"}


# ---------------------------------------------------------------- Data tool: find_open_slots

def test_find_open_slots_monday():
    """Monday returns the right free slots for Omar and Ali from the calendar."""
    result = call("find_open_slots", {"date": "2026-11-02"})
    assert not result.is_error
    day = result.structured_content
    assert day["weekday"] == "Monday" and day["timezone"] == "Asia/Beirut"
    assert [(s["start"], s["consultants"]) for s in day["slots"]] == [
        ("12:00", ["Omar"]), ("12:30", ["Omar"]), ("16:30", ["Ali"]), ("17:00", ["Ali"]), ("17:30", ["Ali"]),
    ]


def test_find_open_slots_fully_booked_day_is_empty_not_an_error():
    """A fully booked Friday returns an empty list, not an error."""
    result = call("find_open_slots", {"date": "2026-11-06"})  # Friday: both consultants busy all day
    assert not result.is_error
    assert result.structured_content["slots"] == []


def test_find_open_slots_respects_two_hours_notice(monkeypatch):
    """Slots less than 2 hours from now are not offered."""
    monkeypatch.setenv("PICKLE_NOW", "2026-11-02T11:00")
    starts = [s["start"] for s in call("find_open_slots", {"date": "2026-11-02"}).structured_content["slots"]]
    assert starts[0] == "16:30"  # earliest start is 13:00, so Omar's 12:00 and 12:30 drop out
    monkeypatch.setenv("PICKLE_NOW", "2026-11-02T09:59")
    starts = [s["start"] for s in call("find_open_slots", {"date": "2026-11-02"}).structured_content["slots"]]
    assert starts[0] == "12:00"


def test_find_open_slots_changes_nothing(pinned_env):
    """Looking up slots sends nothing and books nothing."""
    call("find_open_slots", {"date": "2026-11-03"})
    assert outbox(pinned_env) == []


def test_find_open_slots_input_failures():
    """Bad dates fail with their own codes: INVALID_DATE, DATE_IN_PAST, NOT_A_WORKING_DAY, TOO_FAR_AHEAD."""
    assert error_code(call("find_open_slots", {"date": "next tuesday"})) == "INVALID_DATE"
    assert error_code(call("find_open_slots", {"date": "2026-02-30"})) == "INVALID_DATE"
    assert error_code(call("find_open_slots", {"date": "2026-10-30"})) == "DATE_IN_PAST"
    assert error_code(call("find_open_slots", {"date": "2026-11-07"})) == "NOT_A_WORKING_DAY"
    assert error_code(call("find_open_slots", {"date": "2027-06-01"})) == "TOO_FAR_AHEAD"


def test_find_open_slots_calendar_unavailable(monkeypatch, tmp_path):
    """A missing or broken calendar returns CALENDAR_UNAVAILABLE."""
    monkeypatch.setenv("PICKLE_CALENDAR", str(tmp_path / "missing.json"))
    result = call("find_open_slots", {"date": "2026-11-03"})
    assert error_code(result) == "CALENDAR_UNAVAILABLE"
    (tmp_path / "broken.json").write_text("{not json")
    monkeypatch.setenv("PICKLE_CALENDAR", str(tmp_path / "broken.json"))
    assert error_code(call("find_open_slots", {"date": "2026-11-03"})) == "CALENDAR_UNAVAILABLE"


# ---------------------------------------------------------------- Action tool: send_email

def test_send_email_delivers_one_message(pinned_env):
    """One email lands in the outbox with the right To, Subject and body."""
    result = call("send_email", {"to": "omar@picklelabs.example", "subject": "Client prefers French", "body": "Lina would like the scoping call in French."})
    assert not result.is_error
    receipt = result.structured_content
    files = outbox(pinned_env)
    assert len(files) == 1 and files[0].name == f"{receipt['message_id']}.eml"
    msg = message_from_bytes(files[0].read_bytes(), policy=policy.default)
    assert msg["To"] == "omar@picklelabs.example"
    assert msg["Subject"] == "Client prefers French"
    assert "in French" in msg.get_content()


def test_send_email_never_sends_the_same_message_twice(pinned_env):
    """The exact same email twice: the second is refused with DUPLICATE_MESSAGE."""
    args = {"to": "lina@example.com", "subject": "Hello", "body": "Same body."}
    assert not call("send_email", args).is_error
    assert error_code(call("send_email", args)) == "DUPLICATE_MESSAGE"
    assert len(outbox(pinned_env)) == 1
    assert not call("send_email", {**args, "body": "A different body."}).is_error
    assert len(outbox(pinned_env)) == 2


def test_send_email_input_failures_send_nothing(pinned_env):
    """Bad address, empty fields, a hidden Bcc injection, an oversized body: all refused, nothing sent."""
    assert error_code(call("send_email", {"to": "lina at example", "subject": "s", "body": "b"})) == "INVALID_EMAIL"
    assert error_code(call("send_email", {"to": "lina@example.com", "subject": "  ", "body": "b"})) == "INVALID_FIELD"
    assert error_code(call("send_email", {"to": "lina@example.com", "subject": "s", "body": ""})) == "INVALID_FIELD"
    assert error_code(call("send_email", {"to": "lina@example.com", "subject": "a\nBcc: x@evil.example", "body": "b"})) == "INVALID_FIELD"
    assert error_code(call("send_email", {"to": "lina@example.com", "subject": "s", "body": "x" * 5001})) == "INVALID_FIELD"
    assert outbox(pinned_env) == []


def test_send_email_outbox_unavailable(monkeypatch, tmp_path):
    """A broken outbox returns OUTBOX_UNAVAILABLE, not a fake duplicate (the bug the tests caught)."""
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("a file where the outbox folder should be")
    monkeypatch.setenv("PICKLE_OUTBOX", str(blocker))
    assert error_code(call("send_email", {"to": "lina@example.com", "subject": "s", "body": "b"})) == "OUTBOX_UNAVAILABLE"


# ---------------------------------------------------------------- Orchestration tool: offer_scoping_slots

def test_offer_picks_earliest_slot_on_three_different_days(pinned_env):
    """Picks the earliest slot on 3 different days and sends exactly one email."""
    result = call("offer_scoping_slots", {"client_name": "Lina", "client_email": "lina@example.com", "from_date": "2026-11-02"})
    assert not result.is_error
    offer = result.structured_content
    assert [(o["date"], o["start"], o["consultant"]) for o in offer["offered"]] == [
        ("2026-11-02", "12:00", "Omar"), ("2026-11-03", "11:00", "Omar"), ("2026-11-04", "09:00", "Ali"),
    ]
    assert offer["business_days_checked"] == 3
    files = outbox(pinned_env)
    assert len(files) == 1
    body = message_from_bytes(files[0].read_bytes(), policy=policy.default).get_content()
    assert "Hi Lina" in body and "Tuesday 3 November 2026, 11:00 to 11:30 with Omar" in body


def test_offer_skips_weekend_and_fully_booked_days():
    """Starting Thursday: skips the full Friday and the weekend, offers Thu, Mon, Tue."""
    # Thursday start: Friday is fully booked, the weekend is skipped, Monday and Tuesday follow.
    offer = call("offer_scoping_slots", {"client_name": "Lina", "client_email": "lina@example.com", "from_date": "2026-11-05"}).structured_content
    assert [o["date"] for o in offer["offered"]] == ["2026-11-05", "2026-11-09", "2026-11-10"]
    assert offer["fully_booked_days"] == ["2026-11-06"]
    assert offer["business_days_checked"] == 4


def test_offer_bad_email_fails_before_any_lookup(monkeypatch, pinned_env):
    """A bad client email fails first, before any calendar lookup."""
    monkeypatch.setenv("PICKLE_CALENDAR", str(pinned_env / "missing.json"))  # a lookup would fail differently
    result = call("offer_scoping_slots", {"client_name": "Lina", "client_email": "lina@", "from_date": "2026-11-02"})
    assert error_code(result) == "INVALID_EMAIL"
    assert outbox(pinned_env) == []


def test_offer_no_availability_sends_nothing(monkeypatch, pinned_env):
    """When nobody is free for weeks, NO_AVAILABILITY and no email."""
    calendar = json.loads((Path(__file__).resolve().parent.parent / "mcp_toolkit" / "data" / "calendar.json").read_text())
    calendar["weekly_busy"] = [
        {"consultant": c, "weekday": d, "start": "09:00", "end": "18:00", "title": "busy"}
        for c in calendar["consultants"] for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    ]
    (pinned_env / "full.json").write_text(json.dumps(calendar))
    monkeypatch.setenv("PICKLE_CALENDAR", str(pinned_env / "full.json"))
    result = call("offer_scoping_slots", {"client_name": "Lina", "client_email": "lina@example.com", "from_date": "2026-11-02"})
    assert error_code(result) == "NO_AVAILABILITY"
    assert outbox(pinned_env) == []


def test_offer_passes_on_errors_from_the_tools_it_calls(pinned_env):
    """Errors from the tools it calls come through unchanged, including DUPLICATE_MESSAGE."""
    args = {"client_name": "Lina", "client_email": "lina@example.com", "from_date": "2026-11-02"}
    assert error_code(call("offer_scoping_slots", {**args, "from_date": "2026-10-01"})) == "DATE_IN_PAST"
    assert error_code(call("offer_scoping_slots", {**args, "from_date": "2027-03-01"})) == "TOO_FAR_AHEAD"
    assert error_code(call("offer_scoping_slots", {**args, "from_date": "soon"})) == "INVALID_DATE"
    assert error_code(call("offer_scoping_slots", {**args, "client_name": " "})) == "INVALID_FIELD"
    assert not call("offer_scoping_slots", args).is_error
    assert error_code(call("offer_scoping_slots", args)) == "DUPLICATE_MESSAGE"
    assert len(outbox(pinned_env)) == 1
