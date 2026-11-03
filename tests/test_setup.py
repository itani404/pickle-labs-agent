"""Usage meter (cell 4), knowledge loading (cell 6) and the system prompt (cell 12). No API calls."""

from types import SimpleNamespace as NS

import pytest

from pickle_agent.config import settings
from pickle_agent.prompt.instructions import INSTRUCTION_LINES
from pickle_agent.prompt.knowledge import BUSINESS_PDF, BUSINESS_SUMMARY
from pickle_agent.prompt.system_prompt import build_system_prompt
from pickle_agent.llm.client import LiveCallLimit, OfflineModeError, UsageMeter

MODEL_ID, PRICES_PER_M = settings.MODEL_ID, settings.PRICES_PER_M


def test_usage_meter():
    test_meter = UsageMeter(PRICES_PER_M, max_calls=2)
    fake_usage = NS(input_tokens=3300, input_tokens_details=NS(cached_tokens=0),
                    output_tokens=150, output_tokens_details=NS(reasoning_tokens=40))
    test_meter.record(MODEL_ID, fake_usage, "fake agent call")
    assert abs(test_meter.rows[0]["cost"] - (3300 * 0.10 + 150 * 0.50) / 1e6) < 1e-12

    cached_usage = {"input_tokens": 3300, "input_tokens_details": {"cached_tokens": 3000}, "output_tokens": 100}
    test_meter.record(MODEL_ID, cached_usage, "fake cached call (dict usage)")
    assert abs(test_meter.rows[1]["cost"] - (300 * 0.10 + 3000 * 0.01 + 100 * 0.50) / 1e6) < 1e-12

    with pytest.raises(LiveCallLimit):
        test_meter.check()
    with pytest.raises(OfflineModeError):
        UsageMeter(PRICES_PER_M, 5, offline=True).check()

    capped = UsageMeter(PRICES_PER_M, 100, max_cost=0.0003)
    capped.record(MODEL_ID, fake_usage, "fake")
    with pytest.raises(LiveCallLimit):
        capped.check()


def test_knowledge_has_pdf_only_facts_and_clean_text():
    assert "4,500" in BUSINESS_PDF and "net-15" in BUSINESS_PDF and "Omar Al Itani" in BUSINESS_PDF and "Youssef" in BUSINESS_PDF
    assert "net-15" not in BUSINESS_SUMMARY and "4,500" not in BUSINESS_SUMMARY
    assert not any(ch in BUSINESS_PDF for ch in "ﬁﬂﬀ")
    assert "SOC" not in BUSINESS_PDF and "fine-tun" not in BUSINESS_PDF   # the deliberate gaps


def test_system_prompt_covers_required_behaviours():
    full = build_system_prompt("lead_collection")
    assert "Dr. Rick" in full                                            # stays in character
    assert "<business_summary>" in full and "<business_profile_pdf>" in full and "4,500" in full   # summary and PDF
    assert "record_feedback" in INSTRUCTION_LINES[1]                     # logs unknown questions via a tool
    assert "name and email" in INSTRUCTION_LINES[3]                      # encourages leads to leave contact info
    assert all(f'intent="{route}"' in build_system_prompt(route) for route in settings.INTENTS)
    assert "intent=" not in build_system_prompt()                        # no route block without a route
