"""All settings in one place (notebook section 1, cell 2)."""

import os
from pathlib import Path

# Safety switch: with PICKLE_OFFLINE=1 any real API call raises instead of spending money.
OFFLINE = os.getenv("PICKLE_OFFLINE") == "1"

# Model and generation settings (reasoning effort and token caps keep cost predictable)
MODEL_ID = "gpt-6-luna"
ROUTER_EFFORT = "none"      # the router must be fast and deterministic
AGENT_EFFORT = "low"
ROUTER_MAX_OUTPUT = 200
AGENT_MAX_OUTPUT = 1500

# Agent behaviour
MAX_TOOL_ROUNDS = 4         # cap on model-tool-model cycles per message
HISTORY_LIMIT = 20          # short-term memory: last N messages are sent each call
REFLECTION = True           # bonus: the model checks its own draft before replying

# The three intents the router can choose from
INTENTS = ("general_question", "lead_collection", "feedback_or_unanswered")

# Cost guard
MAX_LIVE_CALLS = 300
MAX_COST_USD = 1.00         # hard stop for one notebook session
PRICES_PER_M = {            # USD per 1M tokens (OpenAI pricing page, 17 Oct 2026)
    "gpt-6-luna": {"input": 0.10, "cached": 0.01, "output": 0.50},
}

# Paths. The notebook used Path.cwd(); a package uses its own location so it runs from any folder.
BASE_DIR = Path(__file__).resolve().parent.parent
ME_DIR = BASE_DIR / "me"
LOG_DIR = BASE_DIR / "logs"     # read at call time by logbook.log_event, so tests can point it elsewhere

# Load the key from .env (skipped offline). Only whether it exists is ever printed.
if not OFFLINE:
    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv(usecwd=True))


def describe():
    print(f"model={MODEL_ID}  offline={OFFLINE}  api_key_present={bool(os.getenv('OPENAI_API_KEY'))}")
