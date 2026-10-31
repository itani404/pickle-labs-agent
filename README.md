# Pickle Labs Agent

A fictional three-person AI consultancy in Beirut, built for EECE 503P/798S Agentic Systems, one assignment per branch. This branch (`assignment-5`) holds **Assignment C5**, an MCP toolkit built with FastMCP and connected to an agent through the OpenAI Agents SDK. The **Assignment C3** business assistant is kept below exactly as submitted, and its notebook (`business_agent.ipynb`) is untouched on this branch.

| Assignment                                 | Branch                                                                            | What it is                                                                                                              |
| ------------------------------------------ | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| C3: Introduction to Agents                 | [`assignment-3`](https://github.com/itani404/pickle-labs-agent/tree/assignment-3) | A business assistant with a router, two tools, a reflection step and a Gradio demo                                      |
| C4: Agent Personas and Thinking Mechanisms | [`assignment-4`](https://github.com/itani404/pickle-labs-agent/tree/assignment-4) | A hand-written ReAct agent with configurable personas                                                                   |
| **C5: Agent Tools**                        | [`assignment-5`](https://github.com/itani404/pickle-labs-agent/tree/assignment-5) | **This branch.** An MCP server with one Data, one Action and one Orchestration tool, used by an OpenAI Agents SDK agent |

## Assignment C5: an MCP toolkit for the Pickle Labs front desk

Every Pickle Labs project starts with a free 30-minute scoping call with Omar or Ali, Monday to Friday, 09:00 to 18:00 Beirut time. The front desk needs to answer "when are you free?", send messages, and email a prospective client a few times to choose from. Those three jobs became three MCP tools on one FastMCP server, and the front-desk agent (Dr. Rick, from C3) reaches them only through MCP.

Deliverables in this branch:

| Deliverable                                                               | Where                                            |
| ------------------------------------------------------------------------- | ------------------------------------------------ |
| FastMCP server with the three tools                                       | [`mcp_toolkit/server.py`](mcp_toolkit/server.py) |
| OpenAI Agents SDK host and client                                         | [`mcp_toolkit/agent.py`](mcp_toolkit/agent.py)   |
| Tests, including every failure case                                       | [`tests/`](tests/) (21 tests, no API key needed) |
| Example script that calls one tool by hand                                | [`scripts/call_tool.py`](scripts/call_tool.py)   |
| Setup and run instructions                                                | [Setup and run](#setup-and-run) below            |
| Written summary (Part 1)                                                  | [`docs/part1-summary.md`](docs/part1-summary.md) |
| Reflection: where the tool lines are, whether three was right, next steps | [`docs/reflection.md`](docs/reflection.md)       |
| Screencast                                                                | _link to be added_                               |

### The three tools

| Category          | Tool                  | What it does                                                                                                                                                                                                        | Arguments                                  | Returns                                                                                   | Predictable failures (error code)                                                                                                         |
| ----------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **Data**          | `find_open_slots`     | Lists the free 30-minute slots on one working day and who is free for each. Read-only.                                                                                                                              | `date` (YYYY-MM-DD)                        | `DaySlots`: date, weekday, timezone, slot length, list of `{start, end, consultants}`     | `INVALID_DATE`, `DATE_IN_PAST`, `TOO_FAR_AHEAD`, `NOT_A_WORKING_DAY`, `CALENDAR_UNAVAILABLE`                                              |
| **Action**        | `send_email`          | Sends one plain-text email that has already been written. The side effect: one `.eml` file is delivered to `outbox/`.                                                                                               | `to`, `subject`, `body`                    | `EmailReceipt`: message id, recipient, subject, time sent, outbox file                    | `INVALID_EMAIL`, `INVALID_FIELD`, `DUPLICATE_MESSAGE`, `OUTBOX_UNAVAILABLE`                                                               |
| **Orchestration** | `offer_scoping_slots` | Calls `find_open_slots` day by day (up to 10 working days, skipping weekends and fully booked days), keeps the earliest free slot of each day until it has three, writes the offer, and sends it with `send_email`. | `client_name`, `client_email`, `from_date` | `ScopingOffer`: the slots offered, days checked, fully booked days, and the email receipt | `INVALID_FIELD`, `INVALID_EMAIL`, `INVALID_DATE`, `DATE_IN_PAST`, `TOO_FAR_AHEAD`, `NO_AVAILABILITY`, plus any error passed on from the two tools it calls |

The server also exposes one **resource**, `picklelabs://services` (services, prices, support hours). A resource is not a tool: the host reads it once at start-up and puts it in the agent's instructions, and the model never calls it. The toolkit therefore has exactly three tools.

Each tool has a docstring that the model reads as its description (what it does, its side effects, and every error code), typed arguments with a description for each, and a Pydantic return type, which FastMCP publishes as an output schema. Each tool also carries a category tag (`data`, `action`, `orchestration`), a version (`1.0`), and MCP annotations: `readOnlyHint` is true only for the Data tool.

### How a request travels

```
user ──> agent.py (HOST)
           Agent + Runner (OpenAI Agents SDK, model gpt-6-luna)
           │  the model picks a tool and its arguments
           v
         MCPServerStdio (MCP CLIENT, one per server)
           │  JSON-RPC tools/call over stdin/stdout
           v
         python -m mcp_toolkit.server (MCP SERVER, FastMCP)
           │  find_open_slots ──> mcp_toolkit/data/calendar.json
           │  send_email ──────> outbox/<message-id>.eml
           │  offer_scoping_slots ──> find_open_slots (x N) ──> send_email
           v
         result (or isError + "CODE: reason") goes back up the same chain to the model,
         which writes the reply
```

At start-up the host lists the server's tools (discovery) and reads the resource. During a turn, `agent.py` shows a status line while the model works, then prints each tool call as it leaves (`1. agent → MCP client → server`) and each result as it returns (`✓ server → MCP client → agent`, or `✗` with the error code). The server logs its own side on stderr; the host pipes that stream into its console and prints it indented under the call (`server │ ...`), with the calls the Orchestration tool makes marked `↳`. One terminal therefore shows the whole round trip, and the reply comes last in its own box. The server also writes its log to `logs/mcp_server.log`.

### Design decisions

- **One job per tool, and no overlap.** The first design had a `book_earliest_scoping_call` Orchestration tool. It took the same inputs as the booking Action tool and ended in the same effect, so for "book me a call" the model could not tell the two apart. In the final design the Action tool is a general messenger that needs a body someone has already written. The Orchestration tool needs no body: its value is the multi-day search and composing the offer from what it finds.
- **Errors are explicit and coded.** Every predictable failure raises `ToolError("CODE: reason")`. FastMCP returns it as a result with `isError: true`, and the Agents SDK passes the text to the model, which can then explain it to the user. An empty day is not an error: a fully booked Friday returns `slots: []`, because "nobody is free" is a valid answer.
- **Fail before acting.** `send_email` validates everything before writing. `offer_scoping_slots` checks the email address before any calendar lookup, and sends nothing when it finds no slot. No failure path leaves a half-sent message.
- **Duplicates are stopped by the tool, not by the prompt.** The message id is a hash of recipient, subject and body, and the `.eml` file is created in exclusive mode. Two runs sending the same message collide on the same file name, and only one succeeds, even if they run at the same moment. A prompt rule cannot guarantee this.
- **The Orchestration tool calls the other two as functions.** In FastMCP 4 the `@mcp.tool` decorator returns the original function, so `offer_scoping_slots` calls `find_open_slots` and `send_email` directly, with the same validation and logging, and without a second MCP round trip.
- **Email is simulated.** `send_email` writes a standard RFC 5322 `.eml` file instead of talking to an SMTP server, so the demo sends nothing real. Swapping the file write for `smtplib` would not change the tool's interface.
- **The calendar is a weekly pattern** (`mcp_toolkit/data/calendar.json`), so the demo works in any week. Fridays are fully booked on purpose, which shows the Orchestration tool skipping a day.

### Project structure (C5 additions)

```
mcp_toolkit/
├── server.py            FastMCP server: 3 tools, 1 resource, error codes, logging
├── agent.py             OpenAI Agents SDK host: MCPServerStdio client, instructions, round-trip printing
└── data/calendar.json   Weekly busy blocks for Omar and Ali
scripts/call_tool.py     Call one tool over stdio with no model (handy for failure cases)
tests/
├── conftest.py          Pinned clock (Mon 2 Nov 2026, 08:00), a temporary outbox per test, and the
│                        "what was tested" summary printed at the end of a run
├── test_server.py       17 tests of the three tools through an in-memory MCP client
└── test_agent_offline.py  4 tests of the full host round trip over stdio, with a scripted model
requirements-c5.txt      Pinned libraries for C5
```

At run time the server creates `outbox/` (delivered emails) and `logs/`. Both are in `.gitignore`.

### Setup and run

1. Python 3.12. Create a virtual environment and install the pinned libraries:
   ```
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-c5.txt
   ```
2. Copy `.env.example` to `.env` and add an OpenAI API key. Only the live agent needs it; the tests and `scripts/call_tool.py` do not.
3. Run it:
   ```
   python -m mcp_toolkit.agent --list                      # connect, list tools and resource, no model calls
   python -m mcp_toolkit.agent                             # interactive chat
   python -m mcp_toolkit.agent --ask "Is anyone free next Tuesday?"
   python scripts/call_tool.py find_open_slots '{"date": "2026-11-07"}'   # a failure case, no model
   pytest tests                                            # 21 offline tests
   ```

Optional environment variables: `PICKLE_MODEL` (default `gpt-6-luna`), `PICKLE_NOW` (pin the clock, e.g. `2026-11-02T08:00`; the host and the server both read it), `PICKLE_OUTBOX` (where emails go), and `PICKLE_CALENDAR` (another calendar file).

### What was tested

- **Offline, 21 tests, no API key.** The 17 tool tests cover:
  - discovery: exactly three tools, one per category tag, each with a description, documented arguments and an output schema, and the Data tool marked read-only;
  - the resource;
  - every success path and every error code in the table above, including a missing calendar, a corrupt calendar, a header-injection subject and a blocked outbox;
  - "nothing was sent" after each failure;
  - duplicate blocking;
  - the Orchestration tool skipping a weekend and a fully booked Friday.

  The 4 host tests run the real Agents SDK `Runner`, the real `MCPServerStdio` client and the real server subprocess, with a scripted model in place of the LLM. They check tool discovery, the resource reaching the instructions, a Data round trip, an Orchestration round trip, and an error reaching the model as text.

- **Live** (`gpt-6-luna`, 30 Oct 2026): one five-turn conversation.
  1. "Is anyone free next Tuesday?" → Data tool.
  2. "And this Saturday?" → `NOT_A_WORKING_DAY`, explained to the user.
  3. A client asks to be emailed some options → Orchestration tool; the server log shows three `find_open_slots` calls, then `send_email`.
  4. "Email Omar that she prefers French" → Action tool, with a body the model wrote.
  5. "Send me the same options again" → `DUPLICATE_MESSAGE`; the agent said so and repeated the times in the chat.

  Each turn went to the right tool on the first try.

- **A bug the tests caught.** `outbox.mkdir()` raises `FileExistsError` when a file sits where the outbox folder should be. The duplicate-message handler caught it by mistake and then crashed, and the client saw only a generic "Error calling tool". Creating the folder and creating the file now have separate error handling, and that case returns `OUTBOX_UNAVAILABLE`.

### Limits

- An offer does not hold the slots it proposes. Two clients can be offered the same time, and the client's reply still has to be handled by a person.
- The duplicate guard also blocks a legitimate "please resend". The live run hit exactly this; a time window or an explicit resend flag would fix it.
- The Agents SDK does not show MCP resources to the model, so the catalogue reaches the model only through the instructions the host writes.
- Conversation memory lasts for one chat session only.

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
- **Instructions** (cell 3.2): ten numbered guardrails, for example "never invent prices", "log what you cannot answer with `record_feedback`", "collect name and email before the conversation ends", "never claim you recorded something unless a tool result confirmed it", "keep replies to two to five sentences and avoid em dashes", and "you are the AI front desk, so speak about Omar, Ali and Youssef in the third person". Each route adds its own short instruction block on top.

When the two conflict (a sarcastic character is tempted to guess), the instructions win, and instruction 3 says so.

#### The system prompt

`build_system_prompt(route)` assembles tagged sections: `<persona>`, `<instructions>`, `<route_instructions>`, `<business_summary>` and `<business_profile_pdf>`. The knowledge is about 1,700 tokens (the whole system prompt is about 2,300), so it goes straight into the prompt (no retrieval). The PDF contains facts the summary does not (prices, refund and payment terms, team backgrounds), which proves the agent really reads it. It says nothing about some topics (certifications, on-premise fine-tuning), which is what makes the unanswered-question tool fire.

#### The router

One LLM call with reasoning effort `none` and `temperature=0`, returning `{"intent": ..., "reason": ...}`. It also sees the last few messages, so a bare reply such as an email address after the assistant asked for contact details stays in the lead path. Unparseable output falls back to `general_question`.

| Intent                   | Handling                                             | Tool exposed to the model                                          |
| ------------------------ | ---------------------------------------------------- | ------------------------------------------------------------------ |
| `general_question`       | Answer from the knowledge; log what it cannot answer | `record_feedback`, plus `record_customer_interest` as a safety net |
| `lead_collection`        | Collect name, email and what they want, then record  | `record_customer_interest`, plus `record_feedback` as a safety net |
| `feedback_or_unanswered` | Acknowledge, then log the message                    | `record_feedback` only                                             |

Gating the tools by route is the chapter's "tool gating" idea at small scale. The two open-ended routes also keep the other tool as a safety net, so a misrouted message still has the right tool available. Availability is not a guarantee, because the model has to choose to call it: for a test message holding both a question the profile cannot answer and contact details, the model recorded both in one live run and only the question in another. In that second run its draft implied the contact details were saved, and the reflection step caught it and rewrote the reply.

The intent names come from the brief, but the third one is really about **feedback**: whether the knowledge can answer a question is only known after the model has read it, so unanswered questions are logged inside the general route, not by the router.

Measured on 25 messages. The first 15 were written while the router prompt was being built (a development set, including two ambiguous messages and a follow-up that needs the history): **15 of 15 correct**. The last 10 were written afterwards, share no wording with the examples in the prompt and were not used to change anything: **9 of 10 correct**. The miss, "Can you build a voice assistant for us?", went to the lead route; it is a borderline message, and nothing is lost because that route can also log the question. All 25 outputs parsed. The full table is in the notebook output.

#### Tools

Both tools are defined once as MCP-style dictionaries (`name`, `description`, `inputSchema`, `outputSchema`, JSON Schema). The same dictionary is printed as documentation, sent to the model and used to validate arguments.

| Tool                       | Parameters (all required strings) | Output                                                                                           | Logs to               |
| -------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------- |
| `record_customer_interest` | `email`, `name`, `message`        | `{"status": "recorded"}`, `{"status": "duplicate", ...}` or `{"status": "error", "reason": ...}` | `logs/leads.jsonl`    |
| `record_feedback`          | `question`                        | `{"status": "recorded"}` or `{"status": "error", "reason": ...}`                                 | `logs/feedback.jsonl` |

Both print a line in the notebook and append one JSON line to their file. Errors (invalid email, empty fields, unknown tool, wrong arguments, a tool not allowed on that route) are returned to the model as data, never raised, so it can recover by asking the customer again.

#### The agent loop

`agent_turn` sends the system prompt, the last 20 messages of chat history (short-term memory) and the new message to the model with the route's tools. If the model asks for a tool, the loop runs it, appends the result and calls the model again; if it answers in text, that text is returned. The loop stops after 4 tool rounds, and on the last round the tools are withheld so the model has to answer in text.

#### Reflection (bonus)

A second, lightweight call reviews the draft against the instructions and the business knowledge (including the earlier conversation): invented facts or promises, claims that something was recorded without a tool result, broken character, and an interested customer who was not asked for contact details. If the draft is fine it is sent unchanged. Otherwise the reviewer lists the issues and writes a revised reply. Every review is written to `logs/reflection.jsonl` with the original draft and the final reply, and the chat trace shows the original draft when a revision happened. A checkbox in the interface turns it off.

A seeded test shows it working. The draft "An Agent Autopsy is only 499 dollars and comes with a lifetime warranty" is flagged for the wrong price and the invented warranty, and revised to the real $4,500 flat price and five business days. The reviewer is a model too, so it is not perfectly consistent: it sometimes rewrites a fine reply, for example to add a request for contact details, and if its own answer cannot be parsed the draft is sent unchanged and the chat trace says so. In test conversations it also caught a draft that promised a follow-up without confirmation, one that never asked an interested customer for their name and email, and one that described a service the customer had not mentioned.

### What was tested

- **Offline** (no API, no cost): usage meter, knowledge loading, prompt assembly, both tools and the dispatcher (valid calls, duplicates, bad email, empty fields, unknown tool, missing, extra and wrongly typed arguments, bad JSON, tool not allowed on a route), the agent loop with a scripted fake model (plain text, tool call, tool error recovery, disallowed tool, round cap, history cleaning), router parsing, reflection parsing and the full chat turn.
- **Live** (`gpt-6-luna`): the 25-message router table, the seeded reflection test, and eight conversations: an answer from the summary and one only the PDF has, a SOC 2 question the knowledge cannot answer (logged), a lead over two messages (recorded once), a lead with a malformed email followed by the corrected one, a lead who never said what they want (the assistant asks instead of guessing), a bug report (logged), an attempt to talk it into a 90% discount (no discount invented, stays in role, not logged as a question), and one message that holds both an unanswerable question and contact details (the model recorded both in one run and only the question in another, where reflection caught the unconfirmed claim).
- **Interface:** the Gradio app was driven through its HTTP API with both a fake and the real model. It also installs and runs from scratch in a clean virtual environment with the pinned requirements.

### Notes and decisions

- **Responses API, not `openai.ChatCompletion`.** The brief names the older interface. Current OpenAI models do tool calling through the Responses API (`client.responses.create`), so that is what `llm_call` uses.
- **Pinned libraries.** `pydantic==2.10.3` and `huggingface_hub==0.36.2` are pinned because Gradio 5.14.0 breaks with the newest versions of both. A clean install of unpinned dependencies failed during testing.
- **No retrieval.** The business knowledge is small enough to live in the system prompt. A larger knowledge base would need chunking and retrieval.
- **Memory is per conversation.** History lives in the Gradio session; nothing is stored across sessions except the log files.
- **Cost control.** `MAX_LIVE_CALLS` and `MAX_COST_USD` stop a notebook session that runs away, and the usage meter prints tokens and cost after every call.
- **Fictional data.** The business, people, prices and the demo leads in the recorded outputs are invented.
