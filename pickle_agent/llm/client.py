"""Step 11. Usage meter, offline switch and the lazily created OpenAI client (notebook section 1, cell 3)."""

from ..config import settings


class OfflineModeError(RuntimeError):
    """Raised when a real API call is attempted while PICKLE_OFFLINE=1."""


class LiveCallLimit(RuntimeError):
    """Raised when the call count or the cost cap for this session is reached."""


def _field(obj, name, default=0):
    """Read a field from an SDK object or a dict, treating None as the default."""
    value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
    return default if value is None else value


class UsageMeter:
    """Counts real API calls and tracks tokens and cost so spending stays visible."""

    def __init__(self, prices, max_calls, max_cost=None, offline=False):
        self.prices, self.max_calls, self.max_cost, self.offline = prices, max_calls, max_cost, offline
        self.rows = []

    def check(self):
        if self.offline:
            raise OfflineModeError("PICKLE_OFFLINE=1: refusing to call the API.")
        if len(self.rows) >= self.max_calls:
            raise LiveCallLimit(f"MAX_LIVE_CALLS={self.max_calls} reached.")
        if self.max_cost is not None and self.total_cost() >= self.max_cost:
            raise LiveCallLimit(f"MAX_COST_USD={self.max_cost} reached.")

    def record(self, model, usage, label=""):
        price = self.prices[model]
        tokens_in = _field(usage, "input_tokens")
        cached = _field(_field(usage, "input_tokens_details", {}), "cached_tokens")
        tokens_out = _field(usage, "output_tokens")
        reasoning = _field(_field(usage, "output_tokens_details", {}), "reasoning_tokens")
        cost = ((tokens_in - cached) * price["input"] + cached * price["cached"]
                + tokens_out * price["output"]) / 1_000_000
        self.rows.append({"label": label, "in": tokens_in, "cached": cached,
                          "out": tokens_out, "reasoning": reasoning, "cost": cost})
        print(f"[call {len(self.rows)}/{self.max_calls}] {label}: in={tokens_in} "
              f"(cached {cached}) out={tokens_out} (reasoning {reasoning}) cost=${cost:.5f}")

    def total_cost(self):
        return sum(row["cost"] for row in self.rows)

    def summary(self):
        print(f"{len(self.rows)} API calls, total ${self.total_cost():.5f}")


assert settings.MODEL_ID in settings.PRICES_PER_M, f"add a price row for {settings.MODEL_ID} to PRICES_PER_M so cost can be tracked"
meter = UsageMeter(settings.PRICES_PER_M, settings.MAX_LIVE_CALLS, settings.MAX_COST_USD, offline=settings.OFFLINE)
_client = None


def get_client():
    """Create the OpenAI client on first use, so importing this package never touches the key."""
    global _client
    meter.check()
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()
    return _client
