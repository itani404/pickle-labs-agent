"""Pickle Labs front-desk MCP server (Assignment C5).

Exactly three tools, one per category from Chapter 5:

    find_open_slots       Data tool           reads the team calendar, changes nothing
    send_email            Action tool         writes one message to the outbox (a side effect)
    offer_scoping_slots   Orchestration tool  calls find_open_slots over several days, then send_email

plus one resource, picklelabs://services (the service catalogue). A resource is not a tool: the
host reads it, the model never calls it.

Every failure the caller can predict raises ToolError("CODE: explanation"). FastMCP returns that to
the client as a result with isError=true, so the agent sees the code and the reason instead of a
silent empty answer.

Run it on its own (stdio transport):  python -m mcp_toolkit.server
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from datetime import date, datetime, time, timedelta
from email import message_from_bytes
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from typing import Annotated, NoReturn
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_DIR = PACKAGE_DIR.parent

TZ = ZoneInfo("Asia/Beirut")
MIN_NOTICE = timedelta(hours=2)  # no call can start sooner than this
MAX_DAYS_AHEAD = 60  # the calendar is only planned this far
SEARCH_BUSINESS_DAYS = 10  # how far offer_scoping_slots looks
OFFER_SIZE = 3
MAX_BODY_CHARS = 5000
FRONT_DESK = "Pickle Labs front desk <frontdesk@picklelabs.example>"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


# ---------------------------------------------------------------- configuration and logging

def _calendar_path() -> Path:
    return Path(os.environ.get("PICKLE_CALENDAR", PACKAGE_DIR / "data" / "calendar.json"))


def _outbox_dir() -> Path:
    return Path(os.environ.get("PICKLE_OUTBOX", REPO_DIR / "outbox"))


def _now() -> datetime:
    """Current Beirut time. PICKLE_NOW (ISO, e.g. 2026-11-02T08:00) pins it for tests and demos."""
    pinned = os.environ.get("PICKLE_NOW")
    if pinned:
        return datetime.fromisoformat(pinned).replace(tzinfo=TZ)
    return datetime.now(TZ)


log = logging.getLogger("pickle_mcp")
if not log.handlers:
    # stdout carries the MCP protocol, so the log goes to stderr (and to logs/ for the record).
    _fmt = logging.Formatter("%(asctime)s [mcp-server] %(message)s", datefmt="%H:%M:%S")
    _stderr = logging.StreamHandler(sys.stderr)
    _stderr.setFormatter(_fmt)
    log.addHandler(_stderr)
    try:
        (REPO_DIR / "logs").mkdir(exist_ok=True)
        _file = logging.FileHandler(REPO_DIR / "logs" / "mcp_server.log")
        _file.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        log.addHandler(_file)
    except OSError:
        pass
    log.setLevel(logging.INFO)
    log.propagate = False


def _fail(code: str, message: str) -> NoReturn:
    log.info("  error %s: %s", code, message)
    raise ToolError(f"{code}: {message}")


# ---------------------------------------------------------------- output types

class Slot(BaseModel):
    start: str = Field(description="Start time, HH:MM, Beirut time.")
    end: str = Field(description="End time, HH:MM, Beirut time.")
    consultants: list[str] = Field(description="Team members free for the whole slot.")


class DaySlots(BaseModel):
    date: str = Field(description="The day checked, YYYY-MM-DD.")
    weekday: str
    timezone: str = Field(description="Always Asia/Beirut.")
    slot_minutes: int = Field(description="Length of a scoping call in minutes.")
    slots: list[Slot] = Field(description="Free slots in time order. Empty when the day is fully booked.")


class EmailReceipt(BaseModel):
    message_id: str = Field(description="Stable id of the message, derived from its content.")
    to: str
    subject: str
    sent_at: str = Field(description="ISO timestamp, Beirut time.")
    outbox_file: str = Field(description="Where the delivered message was written.")


class OfferedSlot(BaseModel):
    date: str
    weekday: str
    start: str
    end: str
    consultant: str


class ScopingOffer(BaseModel):
    offered: list[OfferedSlot] = Field(description="The times put in the email, earliest first, one per day.")
    business_days_checked: int
    fully_booked_days: list[str] = Field(description="Working days checked that had no free slot.")
    email: EmailReceipt = Field(description="Receipt of the offer email sent to the client.")


# ---------------------------------------------------------------- helpers

def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        _fail("INVALID_DATE", f"'{value}' is not a date in YYYY-MM-DD format, for example 2026-11-03.")


def _check_email(address: str) -> str:
    address = (address or "").strip()
    if not EMAIL_RE.match(address):
        _fail("INVALID_EMAIL", f"'{address}' is not a valid email address. Ask for it again.")
    return address


def _load_calendar() -> dict:
    path = _calendar_path()
    try:
        cal = json.loads(path.read_text())
        hours = cal["working_hours"]
        cal["_open"] = time.fromisoformat(hours["start"])
        cal["_close"] = time.fromisoformat(hours["end"])
        cal["consultants"] = list(cal["consultants"])
        cal["slot_minutes"] = int(cal["slot_minutes"])
        for block in cal["weekly_busy"]:
            block["_start"] = time.fromisoformat(block["start"])
            block["_end"] = time.fromisoformat(block["end"])
    except FileNotFoundError:
        _fail("CALENDAR_UNAVAILABLE", f"the team calendar ({path.name}) cannot be found. Nothing was looked up; try again later.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _fail("CALENDAR_UNAVAILABLE", f"the team calendar ({path.name}) could not be read ({type(exc).__name__}). Nothing was looked up; try again later.")
    return cal


def _business_days(start: date, count: int):
    day = start
    while count:
        if day.weekday() < 5:
            yield day
            count -= 1
        day += timedelta(days=1)


# ---------------------------------------------------------------- server

mcp = FastMCP(
    "Pickle Labs front desk",
    instructions=(
        "Tools for the Pickle Labs front desk. find_open_slots reads the calendar, send_email sends "
        "one message, offer_scoping_slots emails a client up to three scoping-call times. "
        "Errors start with an upper-case code such as INVALID_EMAIL."
    ),
)


@mcp.tool(
    version="1.0",
    tags={"data"},
    annotations={"title": "Find open scoping-call slots", "readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
)
def find_open_slots(
    date: Annotated[str, Field(description="The working day to check, YYYY-MM-DD, Beirut time.")],
) -> DaySlots:
    """Look up the free 30-minute scoping-call slots with Omar or Ali on one working day.

    Read-only: it never books, holds or sends anything. Working hours are Monday to Friday,
    09:00 to 18:00 Beirut time, and a call must start at least 2 hours from now. A fully booked
    day returns an empty slot list, which is an answer, not an error.

    Errors: INVALID_DATE (not YYYY-MM-DD), DATE_IN_PAST, TOO_FAR_AHEAD (over 60 days),
    NOT_A_WORKING_DAY (Saturday or Sunday), CALENDAR_UNAVAILABLE (calendar missing or unreadable).
    """
    log.info("find_open_slots(date=%r)", date)
    day = _parse_day(date)
    now = _now()
    if day < now.date():
        _fail("DATE_IN_PAST", f"{day.isoformat()} has already passed; today is {now.date().isoformat()}.")
    if day > now.date() + timedelta(days=MAX_DAYS_AHEAD):
        _fail("TOO_FAR_AHEAD", f"the calendar is only planned {MAX_DAYS_AHEAD} days ahead, up to {(now.date() + timedelta(days=MAX_DAYS_AHEAD)).isoformat()}.")
    if day.weekday() >= 5:
        _fail("NOT_A_WORKING_DAY", f"{day.isoformat()} is a {day.strftime('%A')}; the team works Monday to Friday.")

    cal = _load_calendar()
    step = timedelta(minutes=cal["slot_minutes"])
    weekday = day.strftime("%A")
    busy = [b for b in cal["weekly_busy"] if b["weekday"] == weekday]
    earliest = now + MIN_NOTICE
    close = datetime.combine(day, cal["_close"], TZ)

    slots: list[Slot] = []
    start = datetime.combine(day, cal["_open"], TZ)
    while start + step <= close:
        end = start + step
        if start >= earliest:
            free = [
                person for person in cal["consultants"]
                if not any(
                    b["consultant"] == person
                    and datetime.combine(day, b["_start"], TZ) < end
                    and start < datetime.combine(day, b["_end"], TZ)
                    for b in busy
                )
            ]
            if free:
                slots.append(Slot(start=start.strftime("%H:%M"), end=end.strftime("%H:%M"), consultants=free))
        start = end

    log.info("  -> %d free slot(s) on %s %s", len(slots), weekday, day.isoformat())
    return DaySlots(date=day.isoformat(), weekday=weekday, timezone="Asia/Beirut", slot_minutes=cal["slot_minutes"], slots=slots)


@mcp.tool(
    version="1.0",
    tags={"action"},
    annotations={"title": "Send an email", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
def send_email(
    to: Annotated[str, Field(description="Recipient email address.")],
    subject: Annotated[str, Field(description="One-line subject.")],
    body: Annotated[str, Field(description="Plain-text message body, already written.")],
) -> EmailReceipt:
    """Send one plain-text email from the Pickle Labs front desk to one recipient.

    Side effect: the message is delivered to the outbox and cannot be unsent. Use it for a
    message you have already written, such as a follow-up or a note to the team. To offer a
    client scoping-call times, use offer_scoping_slots instead. An identical message (same
    recipient, subject and body) is only ever sent once.

    Errors: INVALID_EMAIL, INVALID_FIELD (empty subject or body, multi-line subject, body over
    5000 characters), DUPLICATE_MESSAGE (already sent; nothing new was sent),
    OUTBOX_UNAVAILABLE (the outbox cannot be written; nothing was sent).
    """
    log.info("send_email(to=%r, subject=%r, body=<%d chars>)", to, subject, len(body or ""))
    to = _check_email(to)
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject or not body:
        _fail("INVALID_FIELD", "subject and body must both be non-empty.")
    if "\n" in subject or "\r" in subject:
        _fail("INVALID_FIELD", "the subject must be a single line.")
    if len(body) > MAX_BODY_CHARS:
        _fail("INVALID_FIELD", f"the body is {len(body)} characters; the limit is {MAX_BODY_CHARS}.")

    # The content hash is the idempotency key: two runs sending the same message collide on the
    # same file name, and the exclusive create ("x") lets only one of them through.
    key = hashlib.sha256(f"{to.lower()}\n{subject}\n{body}".encode()).hexdigest()[:12]
    outbox = _outbox_dir()
    path = outbox / f"{key}.eml"
    sent_at = _now()

    msg = EmailMessage()
    msg["From"] = FRONT_DESK
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = format_datetime(sent_at)
    msg["Message-ID"] = f"<{key}@picklelabs.example>"
    msg.set_content(body, cte="8bit")

    # Two separate try blocks: mkdir also raises FileExistsError (when a file sits where the
    # outbox folder should be), and that must not be mistaken for a duplicate message.
    try:
        outbox.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _fail("OUTBOX_UNAVAILABLE", f"the outbox could not be opened ({type(exc).__name__}). Nothing was sent.")
    try:
        with open(path, "xb") as fh:
            fh.write(bytes(msg))
    except FileExistsError:
        first = message_from_bytes(path.read_bytes())["Date"]
        _fail("DUPLICATE_MESSAGE", f"this exact message to {to} was already sent ({first}, id {key}). It was not sent again.")
    except OSError as exc:
        _fail("OUTBOX_UNAVAILABLE", f"the outbox could not be written ({type(exc).__name__}). Nothing was sent.")

    log.info("  -> sent %s to %s (%s)", key, to, path.name)
    return EmailReceipt(message_id=key, to=to, subject=subject, sent_at=sent_at.isoformat(timespec="seconds"), outbox_file=str(path))


@mcp.tool(
    version="1.0",
    tags={"orchestration"},
    annotations={"title": "Email a client scoping-call options", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
def offer_scoping_slots(
    client_name: Annotated[str, Field(description="The client's name, used to greet them.")],
    client_email: Annotated[str, Field(description="Where to send the offer.")],
    from_date: Annotated[str, Field(description="First day to consider, YYYY-MM-DD. Weekends are skipped.")],
) -> ScopingOffer:
    """Email a prospective client up to three free scoping-call times, each on a different working day.

    Calls find_open_slots for up to 10 working days starting at from_date, keeps the earliest
    free slot of each day until it has three, then sends one offer email with send_email. It
    does not book or hold the times; the client replies to choose one.

    Errors: INVALID_FIELD (empty name), INVALID_EMAIL, INVALID_DATE, DATE_IN_PAST, TOO_FAR_AHEAD,
    NO_AVAILABILITY (no free slot in the 10 working days; nothing was sent),
    CALENDAR_UNAVAILABLE, DUPLICATE_MESSAGE (this exact offer was already sent), OUTBOX_UNAVAILABLE.
    """
    log.info("offer_scoping_slots(client_name=%r, client_email=%r, from_date=%r)", client_name, client_email, from_date)
    client_name = (client_name or "").strip()
    if not client_name:
        _fail("INVALID_FIELD", "client_name must be non-empty.")
    # Check the address before any lookup, so a typo costs nothing.
    client_email = _check_email(client_email)
    first_day = _parse_day(from_date)
    horizon = _now().date() + timedelta(days=MAX_DAYS_AHEAD)

    offered: list[OfferedSlot] = []
    fully_booked: list[str] = []
    checked = 0
    for day in _business_days(first_day, SEARCH_BUSINESS_DAYS):
        if day > horizon and checked:  # the first day goes through, so find_open_slots reports TOO_FAR_AHEAD
            break
        log.info("  offer_scoping_slots -> find_open_slots(%s)", day.isoformat())
        result = find_open_slots(day.isoformat())
        checked += 1
        if not result.slots:
            fully_booked.append(result.date)
            continue
        first = result.slots[0]
        offered.append(OfferedSlot(date=result.date, weekday=result.weekday, start=first.start, end=first.end, consultant=first.consultants[0]))
        if len(offered) == OFFER_SIZE:
            break

    if not offered:
        _fail("NO_AVAILABILITY", f"no free scoping slot in the {checked} working days from {first_day.isoformat()}. Nothing was sent; try a later from_date.")

    lines = [
        f"{i}. {datetime.fromisoformat(s.date).strftime('%A %d %B %Y').replace(' 0', ' ')}, {s.start} to {s.end} with {s.consultant}"
        for i, s in enumerate(offered, 1)
    ]
    body = (
        f"Hi {client_name},\n\n"
        "Thank you for your interest in Pickle Labs. Here are times for your free 30-minute scoping call (Beirut time):\n\n"
        + "\n".join(lines)
        + "\n\nReply with the number that suits you and we will send a calendar invite. These times are not held until you reply.\n\n"
        "Pickle Labs front desk"
    )
    log.info("  offer_scoping_slots -> send_email(%s) with %d option(s)", client_email, len(offered))
    receipt = send_email(client_email, f"Your Pickle Labs scoping call: {len(offered)} times to choose from", body)
    return ScopingOffer(offered=offered, business_days_checked=checked, fully_booked_days=fully_booked, email=receipt)


SERVICES = {
    "company": "Pickle Labs, a three-person AI consultancy in Beirut (remote-first).",
    "scoping_call": "Free, 30 minutes, with Omar or Ali. The first step for every project.",
    "support_hours": "Monday to Friday, 09:00 to 18:00 Beirut time.",
    "services": [
        {"name": "Agent Autopsy", "price": "4,500 USD flat", "duration": "5 business days", "what": "Audit of an AI system that is not working; refunded if nothing actionable is found."},
        {"name": "Build Sprint", "price": "from 18,000 USD, fixed after scoping", "duration": "4 weeks", "what": "One agent or LLM feature with an evaluation suite and a handoff."},
        {"name": "Retainer, Pickle Jar", "price": "3,200 USD per month", "duration": "monthly, 3-month minimum", "what": "20 engineering hours per month; unused hours expire."},
        {"name": "Retainer, Big Jar", "price": "7,000 USD per month", "duration": "monthly, 3-month minimum", "what": "50 engineering hours per month; unused hours expire."},
        {"name": "Prompt Clinic", "price": "600 USD per session", "duration": "2 hours, up to 4 people", "what": "Live remote repair of prompts and tool definitions."},
    ],
}


@mcp.resource("picklelabs://services", name="service_catalogue", mime_type="application/json")
def service_catalogue() -> str:
    """Pickle Labs services, prices, support hours and the scoping-call policy. Static data."""
    return json.dumps(SERVICES, indent=2)


if __name__ == "__main__":
    mcp.run(show_banner=False)
