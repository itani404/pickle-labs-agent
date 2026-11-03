"""Step 10. Short-term memory: the conversation that is re-sent on every call (notebook section 5, cell 19)."""

from ..config import settings

TRACE_MARKER = "**Router:**"       # every trace message starts with this, so it is dropped even if metadata is lost


def clean_history(history):
    """Short-term memory: keep plain user/assistant text only (drop trace messages), last HISTORY_LIMIT, user first."""
    cleaned = []
    for message in history or []:
        role, content = message.get("role"), message.get("content")
        if role not in ("user", "assistant") or message.get("metadata"):
            continue
        if isinstance(content, dict):
            content = content.get("text", "")
        elif isinstance(content, list):
            content = " ".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        if isinstance(content, str) and content.strip() and not content.startswith(TRACE_MARKER):
            cleaned.append({"role": role, "content": content})
    cleaned = cleaned[-settings.HISTORY_LIMIT:]
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    return cleaned
