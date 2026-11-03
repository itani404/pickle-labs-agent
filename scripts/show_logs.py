"""What the tools recorded: every line of logs/leads, feedback and reflection (notebook section 10, cell 38).

    python scripts/show_logs.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pickle_agent.tools.logbook import read_log  # noqa: E402

for kind in ("leads", "feedback", "reflection"):
    entries = read_log(kind)
    print(f"--- logs/{kind}.jsonl: {len(entries)} entries ---")
    for entry in entries:
        print(json.dumps(entry, ensure_ascii=False))
    print()
