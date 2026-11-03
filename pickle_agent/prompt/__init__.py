"""Steps 2-5: who the agent is (persona), how it must behave (instructions), what it knows (knowledge), joined by system_prompt."""

from .instructions import INSTRUCTION_LINES, INSTRUCTIONS, ROUTE_INSTRUCTIONS
from .knowledge import BUSINESS_PDF, BUSINESS_SUMMARY
from .persona import PERSONA
from .system_prompt import build_system_prompt, show_prompt
