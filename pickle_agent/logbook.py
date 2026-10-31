"""JSON-lines logs under logs/: leads, feedback and reflection reviews (notebook section 4, cell 15, first half)."""

import json
from datetime import datetime, timezone

from . import config

QUIET_LOGS = False          # the offline tests switch the printing off so their fake data does not clutter the output


def log_event(kind, record):
    """Print one line and append one JSON line to logs/<kind>.jsonl (LOG_DIR is read at call time)."""
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
    with open(config.LOG_DIR / f"{kind}.jsonl", "a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
    if not QUIET_LOGS:
        print(f"[{kind.upper()}] {json.dumps(record, ensure_ascii=False)}")


def read_log(kind):
    path = config.LOG_DIR / f"{kind}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
