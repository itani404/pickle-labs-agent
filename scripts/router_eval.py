"""The router at work: 25 labelled messages, development and held-out sets (notebook section 6.1, cell 25).

LIVE: makes 25 small real API calls.

    python scripts/router_eval.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pickle_agent import config  # noqa: E402
from pickle_agent.router import classify_intent  # noqa: E402
from pickle_agent.usage import meter  # noqa: E402

LEAD_HISTORY = [{"role": "user", "content": "I'd like to start a Build Sprint."},
                {"role": "assistant", "content": "Fine. I need your name and your email."}]

DEV_TESTS = [
    # (message, history, expected intent)
    ("What does an Agent Autopsy include?", [], "general_question"),
    ("Who is on the team?", [], "general_question"),
    ("What is your refund policy?", [], "general_question"),
    ("Do you have a SOC 2 certification?", [], "general_question"),
    ("Can you fine-tune a 70B model on our own servers?", [], "general_question"),
    ("I'd like to know what a retainer costs.", [], "general_question"),                     # ambiguous: sounds like a lead
    ("I want to book an Agent Autopsy. I'm Dana Cole, dana@acme.io", [], "lead_collection"),
    ("Can you send me a quote for a customer-support bot?", [], "lead_collection"),
    ("Sam Reed, sam@reed.dev", LEAD_HISTORY, "lead_collection"),                             # needs the history
    ("Please have someone call me about a retainer.", [], "lead_collection"),
    ("We want to hire you. How do we start?", [], "lead_collection"),                        # ambiguous: question or lead
    ("Your last report was too vague, honestly.", [], "feedback_or_unanswered"),
    ("The contact form on your website crashes on my phone.", [], "feedback_or_unanswered"),
    ("It would be great if you offered a Slack integration.", [], "feedback_or_unanswered"),
    ("Great session with Youssef last week, thank you!", [], "feedback_or_unanswered"),
]

HELD_OUT_TESTS = [
    ("How long does it take to start a project?", [], "general_question"),
    ("Do you work in Arabic?", [], "general_question"),
    ("Is there a minimum contract length for retainers?", [], "general_question"),
    ("Can you build a voice assistant for us?", [], "general_question"),
    ("We're a 30-person fintech and want an audit of our chatbot. Who do I talk to?", [], "lead_collection"),
    ("Book me a Prompt Clinic for next week, my email is lina@brightpath.org", [], "lead_collection"),
    ("Yes, my name is Omar Saad and it's omar@saad.dev", LEAD_HISTORY, "lead_collection"),   # needs the history
    ("Your pricing page is confusing, I could not find the retainer tiers.", [], "feedback_or_unanswered"),
    ("Thanks, that answer was really helpful.", [], "feedback_or_unanswered"),
    ("Honestly the chatbot on your site is slow.", [], "feedback_or_unanswered"),
]
ROUTER_TESTS = [(*t, "development") for t in DEV_TESTS] + [(*t, "held-out") for t in HELD_OUT_TESTS]

if __name__ == "__main__":
    ROUTER_RESULTS = []
    if config.OFFLINE:
        print("offline mode: router table skipped (it needs real calls)")
        sys.exit(0)
    print(f"{'set':<12} {'expected':<24} {'actual':<24} {'ok':<3} message")
    for message, history, expected, test_set in ROUTER_TESTS:
        result = classify_intent(message, history)
        ROUTER_RESULTS.append({**result, "expected": expected, "message": message, "set": test_set})
        mark = "yes" if result["intent"] == expected else "NO"
        print(f"{test_set:<12} {expected:<24} {result['intent']:<24} {mark:<3} {message[:58]}  ({result['reason']})")
    for test_set in ("development", "held-out"):
        rows = [r for r in ROUTER_RESULTS if r["set"] == test_set]
        print(f"\n{test_set}: {sum(r['intent'] == r['expected'] for r in rows)}/{len(rows)} correct, "
              f"{sum(r['parsed_ok'] for r in rows)}/{len(rows)} parsed")
    meter.summary()
