# Pickle Labs Agent

An agent-powered business assistant for **Pickle Labs**, a fictional three-person AI consultancy run out of a garage in Beirut. The assistant is **Dr. Rick**, a sarcastic, brilliant front-desk AI. It answers questions about the business from a PDF profile and a summary, routes every message to the right kind of handling, collects leads, logs feedback and unanswered questions through tool calls, and double-checks its own replies before sending them. It runs on the OpenAI API (`gpt-6-luna`) and is demoed through a Gradio chat interface.

Course: EECE 503P/798S Agentic Systems, Assignment C3 (Introduction to Agents).

## How a message flows

```
customer message
      |
      v
  ROUTER  (one LLM call, JSON out)  ->  general_question | lead_collection | feedback_or_unanswered
      |
      v
  AGENT LOOP for that route  (system prompt = persona + instructions + route instructions + business knowledge)
      |        model asks for a tool?  -- yes --> run tool, give the result back, call the model again
      |        no                                                       (capped at 4 tool rounds)
      v
  draft reply
      |
      v
  REFLECTION  (second LLM call: checks the draft against the instructions, revises if needed)
      |
      v
  reply shown in Gradio, with a collapsible "Router and tools" trace above it
```

In the terms of Chapter 3, the router is the **routing workflow pattern** (a fixed path picked by a classifier), the tool loop inside each route is the **agent** (the model decides whether and when to call a tool), and the reflection step is the **reflection and self-criticism** planning technique.

## Project structure

```
pickle-labs-agent/
├── me/
│   ├── about_business.pdf       Business profile: services, pricing, team, policies, FAQ
│   └── business_summary.txt     Short summary
├── business_agent.ipynb         The whole system, with tests and recorded outputs
├── requirements.txt             Pinned libraries
├── .env.example                 Copy to .env and add your key (the real .env is never committed)
└── README.md
```

At run time the notebook also creates `logs/` (`leads.jsonl`, `feedback.jsonl`, `reflection.jsonl`). It is in `.gitignore` because it can hold personal data.

## Setup and run

1. Python 3.12. Create a virtual environment and install the pinned libraries:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and put your key in it: `OPENAI_API_KEY=...`
3. Open `business_agent.ipynb` (VS Code, Jupyter or Colab with the files uploaded) and run all cells from the top. The last cells build the Gradio interface and launch it; open the local URL it prints.

A full run of the notebook (offline tests, a 15-message router test, a seeded reflection test and seven demo conversations) makes about 68 real calls and costs under one US cent on `gpt-6-luna`. Set the environment variable `PICKLE_OFFLINE=1` before starting to run only the offline tests: every real API call then raises an error instead of spending money.

## The pieces

### Persona and instructions (kept separate on purpose)

- **Persona** (cell 3.1): who Dr. Rick is. Tone and style only, no rules.
- **Instructions** (cell 3.2): ten numbered guardrails, for example "never invent prices", "log what you cannot answer with `record_feedback`", "collect name and email before the conversation ends", "never claim you recorded something unless a tool result confirmed it", "keep replies to two to five sentences and avoid em dashes", and "you are the AI front desk, so speak about Omar, Ali and Youssef in the third person". Each route adds its own short instruction block on top.

When the two conflict (a sarcastic character is tempted to guess), the instructions win, and instruction 3 says so.

### The system prompt

`build_system_prompt(route)` assembles tagged sections: `<persona>`, `<instructions>`, `<route_instructions>`, `<business_summary>` and `<business_profile_pdf>`. The knowledge is about 1,700 tokens (the whole system prompt is about 2,300), so it goes straight into the prompt (no retrieval). The PDF contains facts the summary does not (prices, refund and payment terms, team backgrounds), which proves the agent really reads it. It says nothing about some topics (certifications, on-premise fine-tuning), which is what makes the unanswered-question tool fire.

### The router

One LLM call with reasoning effort `none` and `temperature=0`, returning `{"intent": ..., "reason": ...}`. It also sees the last few messages, so a bare reply such as an email address after the assistant asked for contact details stays in the lead path. Unparseable output falls back to `general_question`.

| Intent | Handling | Tool exposed to the model |
| --- | --- | --- |
| `general_question` | Answer from the knowledge; log what it cannot answer | `record_feedback`, plus `record_customer_interest` as a safety net |
| `lead_collection` | Collect name, email and what they want, then record | `record_customer_interest`, plus `record_feedback` as a safety net |
| `feedback_or_unanswered` | Acknowledge, then log the message | `record_feedback` only |

Gating the tools by route is the chapter's "tool gating" idea at small scale. The two open-ended routes also keep the other tool as a safety net, so a misrouted message still has the right tool available. Availability is not a guarantee, because the model has to choose to call it: for a test message holding both a question the profile cannot answer and contact details, the model recorded both in one live run and only the question in another. In that second run its draft implied the contact details were saved, and the reflection step caught it and rewrote the reply.

The intent names come from the brief, but the third one is really about **feedback**: whether the knowledge can answer a question is only known after the model has read it, so unanswered questions are logged inside the general route, not by the router.

Measured on 25 messages. The first 15 were written while the router prompt was being built (a development set, including two ambiguous messages and a follow-up that needs the history): **15 of 15 correct**. The last 10 were written afterwards, share no wording with the examples in the prompt and were not used to change anything: **9 of 10 correct**. The miss, "Can you build a voice assistant for us?", went to the lead route; it is a borderline message, and nothing is lost because that route can also log the question. All 25 outputs parsed. The full table is in the notebook output.

### Tools

Both tools are defined once as MCP-style dictionaries (`name`, `description`, `inputSchema`, `outputSchema`, JSON Schema). The same dictionary is printed as documentation, sent to the model and used to validate arguments.

| Tool | Parameters (all required strings) | Output | Logs to |
| --- | --- | --- | --- |
| `record_customer_interest` | `email`, `name`, `message` | `{"status": "recorded"}`, `{"status": "duplicate", ...}` or `{"status": "error", "reason": ...}` | `logs/leads.jsonl` |
| `record_feedback` | `question` | `{"status": "recorded"}` or `{"status": "error", "reason": ...}` | `logs/feedback.jsonl` |

Both print a line in the notebook and append one JSON line to their file. Errors (invalid email, empty fields, unknown tool, wrong arguments, a tool not allowed on that route) are returned to the model as data, never raised, so it can recover by asking the customer again.

### The agent loop

`agent_turn` sends the system prompt, the last 20 messages of chat history (short-term memory) and the new message to the model with the route's tools. If the model asks for a tool, the loop runs it, appends the result and calls the model again; if it answers in text, that text is returned. The loop stops after 4 tool rounds, and on the last round the tools are withheld so the model has to answer in text.

### Reflection (bonus)

A second, lightweight call reviews the draft against the instructions and the business knowledge (including the earlier conversation): invented facts or promises, claims that something was recorded without a tool result, broken character, and an interested customer who was not asked for contact details. If the draft is fine it is sent unchanged. Otherwise the reviewer lists the issues and writes a revised reply. Every review is written to `logs/reflection.jsonl` with the original draft and the final reply, and the chat trace shows the original draft when a revision happened. A checkbox in the interface turns it off.

A seeded test shows it working. The draft "An Agent Autopsy is only 499 dollars and comes with a lifetime warranty" is flagged for the wrong price and the invented warranty, and revised to the real $4,500 flat price and five business days. The reviewer is a model too, so it is not perfectly consistent: it sometimes rewrites a fine reply, for example to add a request for contact details, and if its own answer cannot be parsed the draft is sent unchanged and the chat trace says so. In test conversations it also caught a draft that promised a follow-up without confirmation, one that never asked an interested customer for their name and email, and one that described a service the customer had not mentioned.

## What was tested

- **Offline** (no API, no cost): usage meter, knowledge loading, prompt assembly, both tools and the dispatcher (valid calls, duplicates, bad email, empty fields, unknown tool, missing, extra and wrongly typed arguments, bad JSON, tool not allowed on a route), the agent loop with a scripted fake model (plain text, tool call, tool error recovery, disallowed tool, round cap, history cleaning), router parsing, reflection parsing and the full chat turn.
- **Live** (`gpt-6-luna`): the 25-message router table, the seeded reflection test, and eight conversations: an answer from the summary and one only the PDF has, a SOC 2 question the knowledge cannot answer (logged), a lead over two messages (recorded once), a lead with a malformed email followed by the corrected one, a lead who never said what they want (the assistant asks instead of guessing), a bug report (logged), an attempt to talk it into a 90% discount (no discount invented, stays in role, not logged as a question), and one message that holds both an unanswerable question and contact details (the model recorded both in one run and only the question in another, where reflection caught the unconfirmed claim).
- **Interface:** the Gradio app was driven through its HTTP API with both a fake and the real model. It also installs and runs from scratch in a clean virtual environment with the pinned requirements.

## Notes and decisions

- **Responses API, not `openai.ChatCompletion`.** The brief names the older interface. Current OpenAI models do tool calling through the Responses API (`client.responses.create`), so that is what `llm_call` uses.
- **Pinned libraries.** `pydantic==2.10.3` and `huggingface_hub==0.36.2` are pinned because Gradio 5.14.0 breaks with the newest versions of both. A clean install of unpinned dependencies failed during testing.
- **No retrieval.** The business knowledge is small enough to live in the system prompt. A larger knowledge base would need chunking and retrieval.
- **Memory is per conversation.** History lives in the Gradio session; nothing is stored across sessions except the log files.
- **Cost control.** `MAX_LIVE_CALLS` and `MAX_COST_USD` stop a notebook session that runs away, and the usage meter prints tokens and cost after every call.
- **Fictional data.** The business, people, prices and the demo leads in the recorded outputs are invented.
