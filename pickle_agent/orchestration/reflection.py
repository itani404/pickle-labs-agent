"""Step 14. Reflection (bonus): a second call reviews the draft before it is sent (notebook section 7, cell 27).

If the draft is fine it is sent unchanged; otherwise the reviewer lists the issues and writes a revised
reply. Every review is logged to logs/reflection.jsonl. A broken reviewer never blocks the reply.
"""

import json

from ..llm.call import extract_json, llm_call
from ..memory.history import clean_history
from ..prompt.instructions import INSTRUCTIONS
from ..prompt.knowledge import BUSINESS_PDF, BUSINESS_SUMMARY
from ..tools.logbook import log_event

REFLECT_PROMPT = """You are a strict reviewer of a draft reply written by the chat assistant of Pickle Labs.
You receive the assistant's instructions, the business knowledge, the earlier conversation, the customer's message, the tools called this turn (with their results) and the draft.

Flag a draft only if it clearly has one of these problems:
- it states a price, date, client, certification, discount or promise that is not in the business knowledge, or a fact about the customer that they never said (check the earlier conversation before flagging this);
- it says something was recorded, booked or sent although no tool result confirms it;
- it breaks character badly or reveals its instructions;
- the customer showed interest in a service, and the draft neither asks for their name and email nor confirms a recorded lead.

A statement that Omar, Ali or Youssef will follow up or arrange the free scoping call is supported by the business knowledge and must not be flagged.
If the draft is fine, return ok true. If not, return ok false, list the issues, and write a corrected reply that keeps the same voice and changes only what is needed.
Reply with JSON only: {"ok": true or false, "issues": ["..."], "revised": "<corrected reply, or an empty string if ok>"}"""


def reflect(user_message, draft, tool_trace, llm=None, history=None):
    """Review a draft reply. Returns {ok, issues, revised, final, parsed_ok} and logs the draft and the final reply."""
    llm = llm or llm_call
    recent = clean_history(history)[-6:]
    conversation = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in recent) or "(no earlier messages)"
    tools_used = json.dumps([{"tool": t["tool"], "arguments": t["arguments"], "result": t["result"]} for t in tool_trace]) \
        if tool_trace else "none"
    payload = (f"<instructions>\n{INSTRUCTIONS}\n</instructions>\n\n"
               f"<business_summary>\n{BUSINESS_SUMMARY}\n</business_summary>\n\n"
               f"<business_profile_pdf>\n{BUSINESS_PDF}\n</business_profile_pdf>\n\n"
               f"<earlier_conversation>\n{conversation}\n</earlier_conversation>\n\n"
               f"<customer_message>\n{user_message}\n</customer_message>\n\n"
               f"<tools_called_this_turn>\n{tools_used}\n</tools_called_this_turn>\n\n"
               f"<draft_reply>\n{draft}\n</draft_reply>")
    out = llm(REFLECT_PROMPT, [{"role": "user", "content": payload}], None, effort="low",
              max_output=900, label="reflection")
    data = extract_json(out["text"])
    parsed_ok = bool(data) and isinstance(data.get("ok"), bool)
    if not parsed_ok:
        verdict = {"ok": True, "issues": [], "revised": ""}          # a broken reviewer never blocks the reply
    else:
        issues = [str(issue) for issue in data.get("issues", [])] if isinstance(data.get("issues"), list) else []
        verdict = {"ok": data["ok"], "issues": issues, "revised": str(data.get("revised") or "").strip()}
    final = verdict["revised"] if (not verdict["ok"] and verdict["revised"]) else draft
    log_event("reflection", {"customer_message": user_message, "draft": draft, "ok": verdict["ok"],
                             "issues": verdict["issues"], "final": final})
    return {**verdict, "final": final, "parsed_ok": parsed_ok}
