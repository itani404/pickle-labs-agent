"""Steps 6-9: what the agent can do. Definitions (what the model sees), gating (which route gets which tool),
functions (what runs, writing through logbook) and the dispatcher (the guard in front of them)."""

from .definitions import TOOL_BY_NAME, TOOL_DEFS, to_openai_tool
from .dispatcher import dispatch
from .functions import TOOL_IMPL, record_customer_interest, record_feedback
from .gating import ROUTE_TOOLS, print_tool_docs, tools_for_route
from .logbook import log_event, read_log
