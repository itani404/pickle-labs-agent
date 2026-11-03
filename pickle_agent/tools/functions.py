"""Step 8. Tool functions: the code that actually runs when the model calls a tool (notebook section 4, cell 15)."""

import re

from .logbook import log_event, read_log

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def record_customer_interest(email, name, message):
    email, name, message = email.strip(), name.strip(), message.strip()
    if len(name) < 2:
        return {"status": "error", "reason": "name is missing or too short"}
    if not EMAIL_RE.match(email):
        return {"status": "error", "reason": f"'{email}' is not a valid email address"}
    if not message:
        return {"status": "error", "reason": "message is empty"}
    for lead in read_log("leads"):
        if lead["email"].lower() == email.lower() and lead["message"] == message:
            return {"status": "duplicate", "reason": "this lead was already recorded"}
    log_event("leads", {"email": email, "name": name, "message": message})
    return {"status": "recorded"}


def record_feedback(question):
    question = question.strip()
    if len(question) < 3:
        return {"status": "error", "reason": "question is empty"}
    log_event("feedback", {"question": question})
    return {"status": "recorded"}


TOOL_IMPL = {"record_customer_interest": record_customer_interest, "record_feedback": record_feedback}
