# Pickle Labs Agent

A fictional three-person AI consultancy in Beirut, built twice for EECE 503P/798S Agentic Systems. This branch (`assignment-4`) holds **Assignment C4**, a ReAct agent with configurable personas, on top of the **Assignment C3** business assistant, which is kept below exactly as submitted. The C3 notebook (`business_agent.ipynb`) is untouched on this branch.

## Assignment C4: a ReAct agent with configurable personas

The deliverable is `Itani_ReAct_Personas_Assignment.ipynb` (the file name is a placeholder: the brief names none). It contains the use case, the hand-written ReAct loop, three personas, the instructions block, the evaluation harness, every experiment result, and the reflection.

### What it is

Three personas of the same agent, each with its own task, prompt traits, tools and LLM configuration:

| Persona | Task | Temperature | Top-p | Max tokens | Tools |
| --- | --- | --- | --- | --- | --- |
| **Dr. Rick**, sales concierge | Answer questions, check call availability, collect leads | 0.6 | 0.85 | 400 | `get_service`, `get_policy`, `list_team`, `check_availability`, `record_customer_interest`, `record_feedback` |
| **Ada**, project scoper | Turn a request into a price, with assumptions | 0.2 | 0.7 | 600 | `get_service`, `get_policy`, `list_team`, `estimate_project`, `record_customer_interest`, `record_feedback` |
| **Pip**, ideation partner | Show what an agent could do for the customer's business | 0.9 | 0.95 | 600 (+ presence penalty 0.6 where the route accepts it) | `get_service`, `get_policy`, `list_team`, `record_customer_interest`, `record_feedback` |

The AI personas have their own names because Layla and Sami are human team members in the business profile.

### How a message flows

The loop is a **LangGraph** state machine written by hand. There is no `AgentExecutor`, no `create_react_agent` and no prebuilt tool node (a test checks the compiled graph for them).

```
START -> prepare -> think --+--(answer)--> finish -> END
                      ^     |
                      |     +--(action)--> act ------+--(budget left)--> think
                      |     |                        +--(step cap)-----> stop -> END
                      |     +--(unparseable reply, under the limit)--> repair --> think
                      |     +--(format-error limit, or the model call failed)--> stop -> END
```

- `think` asks the model for the next step and runs my own parser on its text. The model writes `Thought:`, `Action:`, `Action Input:` (a JSON object) or `Answer:`.
- `act` runs the detected tool and appends `Observation: {...}`; `repair` feeds a parse error back to the model; guards stop a run after 6 model calls or 2 unreadable replies.
- The parser is where the brief's "detect when the model suggests an action" lives. It handles labels glued onto one line, markdown decoration, code-fenced JSON, invented `Observation:` lines, answers written ahead of the observation, and truncated replies (21 test cases and graph tests in the notebook).

### Tools

Seven tools, defined once as MCP-style dictionaries (`name`, `description`, `inputSchema`, `outputSchema`) that are at the same time the documentation, the tool descriptions rendered into the system prompt and the validation schema. Five are read tools (the business knowledge now lives behind them): `get_service`, `get_policy`, `list_team`, `check_availability`, `estimate_project`. Two are the C3 write tools. Errors come back as data, so the agent can adjust (for example `estimate_project` rejects a 2-month retainer, and the agent retries with 3 months).

### Instructions

A dedicated block written to the Chapter 4 guidelines: goal, action and transition for each workflow step, one purpose per rule, explicit input and output format, a worked example inside the block, positive framing, a length cap, and no persona wording. The first draft (v1) is kept as an experiment arm against the revised block (v2).

### Experiments

19 arms and 3,204 logged runs in `experiments/*.jsonl` (28 tasks across the personas, 5 repeats, 6 tasks held out, a model judge for persona fit). Every table in the notebook is generated from those logs. Headline results (success = correct answer **and** the intended tool use; intervals are 95 percent Wilson intervals on runs that are not independent, so they are optimistic):

| Question | Result |
| --- | --- |
| Baseline (text ReAct, Thought on, one example, instructions in the system prompt, persona configurations) | 96 percent (91 to 98); 97 percent on development tasks, 90 percent on held-out |
| With versus without chain-of-thought | **76 percent without the Thought line**, against 96 with it (the largest effect) |
| Zero-shot, one-shot, few-shot | 92, 96 and 92 percent (overlapping intervals) |
| Instructions in the system prompt or in the first user message | Same success (95 and 96), but Dr. Rick's persona-fit score falls from 3.78 to 2.87 |
| Temperature 0 to 1.5, top-p, max tokens | Success flat (93 to 96 percent); temperature and top-p change wording variety; a 120-token limit truncates Pip's replies |
| Penalties and top-k | Not accepted by `gpt-6-luna` (see below); studied on `gpt-4.1-nano` and a local model: frequency penalty and a larger top-k increase variety slightly |
| Model type | `gpt-4.1-nano` 71 percent; `gpt-6-luna` with hidden reasoning 94; `gpt-6.1-sol` 94 at about 18 times the cost |
| Text loop against native function calling | 96 against 98 percent (a tie at this size) |
| Instructions v1 against v2 | 91 against 96 percent; held-out 67 against 90 |

### Limits and honest notes

- `gpt-6-luna` accepts `temperature` and `top_p` only at reasoning effort `none`, rejects `top_k`, and returns a server error on any non-zero frequency or presence penalty (28 probe calls, recorded in the notebook). The main agent therefore runs at effort `none`, and penalties and top-k are studied separately.
- The sample is small (28 tasks, 5 repeats), the judge is a model of the same family as the agent, and the held-out tasks were seen once in a first run. The notebook's section 11 lists every limit.
- An independent code review of the first version found ten issues (a parser that ate a leading asterisk, scoring regexes without number boundaries, a metric confounded by length and others). They were fixed and **all experiments were rerun on the fixed code**; the first, superseded logs are not part of the results.
- Cost: the whole of C4, including the superseded first run and all tests, cost about 0.88 US dollars against a 5 dollar maximum. A full notebook run offline costs nothing.

### Project structure (C4 additions)

```
pickle-labs-agent/
├── Itani_ReAct_Personas_Assignment.ipynb   The C4 deliverable (59 cells, with stored outputs)
├── experiments/                            One JSONL file per arm (3,204 runs with full traces) and sampling_study.jsonl
├── requirements.txt                        Pinned libraries (adds langgraph 1.2.16 and langchain-core 1.6.10)
├── business_agent.ipynb                    The C3 notebook, unchanged
└── me/                                     The C3 business profile (PDF and summary)
```

### Setup and run

1. Python 3.12, a **dedicated virtual environment**, and the pinned libraries:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Offline (no key, no cost, deterministic): set `PICKLE_OFFLINE=1` and run the notebook from the top. It executes every test with a scripted fake model and prints all results from `experiments/`. Verified in a brand-new virtual environment built from `requirements.txt` alone.
3. Live: copy `.env.example` to `.env`, add `OPENAI_API_KEY`, and run the notebook without `PICKLE_OFFLINE`. Set `PICKLE_LIVE_DEMO=1` to make the demo cell run three fresh conversations (about 0.001 dollars). The last cell launches the Gradio interface (persona dropdown and a collapsible ReAct trace).
4. To regenerate the experiments (about 0.6 dollars; runs already logged are skipped): start the notebook with `PICKLE_RUN_EXPERIMENTS=1` and without `PICKLE_OFFLINE`. The `top_k` study needs a local Ollama with the `phi3` model.

---

## Assignment C3: the Pickle Labs business assistant (unchanged, branch `assignment-3`)

An agent-powered business assistant for **Pickle Labs**, a fictional three-person AI consultancy run out of a garage in Beirut. The assistant is **Dr. Rick**, a sarcastic, brilliant front-desk AI. It answers questions about the business from a PDF profile and a summary, routes every message to the right kind of handling, collects leads, logs feedback and unanswered questions through tool calls, and double-checks its own replies before sending them. It runs on the OpenAI API (`gpt-6-luna`) and is demoed through a Gradio chat interface.

Course: EECE 503P/798S Agentic Systems, Assignment C3 (Introduction to Agents).

### How a message flows

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

### Project structure

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

### Setup and run

1. Python 3.12. Create a virtual environment and install the pinned libraries:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and put your key in it: `OPENAI_API_KEY=...`
3. Open `business_agent.ipynb` (VS Code, Jupyter or Colab with the files uploaded) and run all cells from the top. The last cells build the Gradio interface and launch it; open the local URL it prints.

A full run of the notebook (offline tests, a 15-message router test, a seeded reflection test and seven demo conversations) makes about 68 real calls and costs under one US cent on `gpt-6-luna`. Set the environment variable `PICKLE_OFFLINE=1` before starting to run only the offline tests: every real API call then raises an error instead of spending money.

### The pieces

#### Persona and instructions (kept separate on purpose)

- **Persona** (cell 3.1): who Dr. Rick is. Tone and style only, no rules.
- **Instructions** (cell 3.2): ten numbered guardrails, for example "never invent prices", "log what you cannot answer with `record_feedback`", "collect name and email before the conversation ends", "never claim you recorded something unless a tool result confirmed it", "keep replies to two to five sentences and avoid em dashes", and "you are the AI front desk, so speak about Dr. Haddad, Layla and Sami in the third person". Each route adds its own short instruction block on top.

When the two conflict (a sarcastic character is tempted to guess), the instructions win, and instruction 3 says so.

#### The system prompt

`build_system_prompt(route)` assembles tagged sections: `<persona>`, `<instructions>`, `<route_instructions>`, `<business_summary>` and `<business_profile_pdf>`. The knowledge is about 1,700 tokens (the whole system prompt is about 2,300), so it goes straight into the prompt (no retrieval). The PDF contains facts the summary does not (prices, refund and payment terms, team backgrounds), which proves the agent really reads it. It says nothing about some topics (certifications, on-premise fine-tuning), which is what makes the unanswered-question tool fire.

#### The router

One LLM call with reasoning effort `none` and `temperature=0`, returning `{"intent": ..., "reason": ...}`. It also sees the last few messages, so a bare reply such as an email address after the assistant asked for contact details stays in the lead path. Unparseable output falls back to `general_question`.

| Intent | Handling | Tool exposed to the model |
| --- | --- | --- |
| `general_question` | Answer from the knowledge; log what it cannot answer | `record_feedback`, plus `record_customer_interest` as a safety net |
| `lead_collection` | Collect name, email and what they want, then record | `record_customer_interest`, plus `record_feedback` as a safety net |
| `feedback_or_unanswered` | Acknowledge, then log the message | `record_feedback` only |

Gating the tools by route is the chapter's "tool gating" idea at small scale. The two open-ended routes also keep the other tool as a safety net, so one misrouted message cannot lose a lead or an unanswered question (a test message with both a question the profile cannot answer and contact details makes the model call both tools).

The intent names come from the brief, but the third one is really about **feedback**: whether the knowledge can answer a question is only known after the model has read it, so unanswered questions are logged inside the general route, not by the router.

Measured on 25 messages. The first 15 were written while the router prompt was being built (a development set, including two ambiguous messages and a follow-up that needs the history): **15 of 15 correct**. The last 10 were written afterwards, share no wording with the examples in the prompt and were not used to change anything: **9 of 10 correct**. The miss, "Can you build a voice assistant for us?", went to the lead route; it is a borderline message, and nothing is lost because that route can also log the question. All 25 outputs parsed. The full table is in the notebook output.

#### Tools

Both tools are defined once as MCP-style dictionaries (`name`, `description`, `inputSchema`, `outputSchema`, JSON Schema). The same dictionary is printed as documentation, sent to the model and used to validate arguments.

| Tool | Parameters (all required strings) | Output | Logs to |
| --- | --- | --- | --- |
| `record_customer_interest` | `email`, `name`, `message` | `{"status": "recorded"}`, `{"status": "duplicate", ...}` or `{"status": "error", "reason": ...}` | `logs/leads.jsonl` |
| `record_feedback` | `question` | `{"status": "recorded"}` or `{"status": "error", "reason": ...}` | `logs/feedback.jsonl` |

Both print a line in the notebook and append one JSON line to their file. Errors (invalid email, empty fields, unknown tool, wrong arguments, a tool not allowed on that route) are returned to the model as data, never raised, so it can recover by asking the customer again.

#### The agent loop

`agent_turn` sends the system prompt, the last 20 messages of chat history (short-term memory) and the new message to the model with the route's tools. If the model asks for a tool, the loop runs it, appends the result and calls the model again; if it answers in text, that text is returned. The loop stops after 4 tool rounds, and on the last round the tools are withheld so the model has to answer in text.

#### Reflection (bonus)

A second, lightweight call reviews the draft against the instructions and the business knowledge (including the earlier conversation): invented facts or promises, claims that something was recorded without a tool result, broken character, and an interested customer who was not asked for contact details. If the draft is fine it is sent unchanged. Otherwise the reviewer lists the issues and writes a revised reply. Every review is written to `logs/reflection.jsonl` with the original draft and the final reply, and the chat trace shows the original draft when a revision happened. A checkbox in the interface turns it off.

A seeded test shows it working. The draft "An Agent Autopsy is only 499 dollars and comes with a lifetime warranty" is flagged for the wrong price and the invented warranty, and revised to the real $4,500 flat price and five business days. The reviewer is a model too, so it is not perfectly consistent: it sometimes rewrites a fine reply, for example to add a request for contact details, and if its own answer cannot be parsed the draft is sent unchanged and the chat trace says so. In test conversations it also caught a draft that promised a follow-up without confirmation, one that never asked an interested customer for their name and email, and one that described a service the customer had not mentioned.

### What was tested

- **Offline** (no API, no cost): usage meter, knowledge loading, prompt assembly, both tools and the dispatcher (valid calls, duplicates, bad email, empty fields, unknown tool, missing, extra and wrongly typed arguments, bad JSON, tool not allowed on a route), the agent loop with a scripted fake model (plain text, tool call, tool error recovery, disallowed tool, round cap, history cleaning), router parsing, reflection parsing and the full chat turn.
- **Live** (`gpt-6-luna`): the 25-message router table, the seeded reflection test, and eight conversations: an answer from the summary and one only the PDF has, a SOC 2 question the knowledge cannot answer (logged), a lead over two messages (recorded once), a lead with a malformed email followed by the corrected one, a lead who never said what they want (the assistant asks instead of guessing), a bug report (logged), an attempt to talk it into a 90% discount (no discount invented, stays in role, not logged as a question), and one message that holds both an unanswerable question and contact details (both tools fire).
- **Interface:** the Gradio app was driven through its HTTP API with both a fake and the real model. It also installs and runs from scratch in a clean virtual environment with the pinned requirements.

### Notes and decisions

- **Responses API, not `openai.ChatCompletion`.** The brief names the older interface. Current OpenAI models do tool calling through the Responses API (`client.responses.create`), so that is what `llm_call` uses.
- **Pinned libraries.** `pydantic==2.10.3` and `huggingface_hub==0.36.2` are pinned because Gradio 5.14.0 breaks with the newest versions of both. A clean install of unpinned dependencies failed during testing.
- **No retrieval.** The business knowledge is small enough to live in the system prompt. A larger knowledge base would need chunking and retrieval.
- **Memory is per conversation.** History lives in the Gradio session; nothing is stored across sessions except the log files.
- **Cost control.** `MAX_LIVE_CALLS` and `MAX_COST_USD` stop a notebook session that runs away, and the usage meter prints tokens and cost after every call.
- **Fictional data.** The business, people, prices and the demo leads in the recorded outputs are invented.
