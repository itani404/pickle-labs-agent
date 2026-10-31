# Study branch `study/c3`: the C3 notebook as a Python package

Local study branch, never pushed. It holds the Assignment C3 business assistant (`business_agent.ipynb`, as submitted on `main` and `assignment-3`) rewritten as plain Python files, so it can be read and diffed against the C4 and C5 versions. The notebook itself is removed from this branch; it is unchanged on `main`.

**Faithful, not improved.** Every function and class is the notebook's code. A check that compares them by syntax tree (ignoring docstrings and the `config.` prefix) found all 36 identical, and all 13 constants (persona, instructions, tool definitions, prompts, test and scenario lists) are byte-identical.

## Where each notebook cell went

| Notebook | Cell | Now in |
| --- | --- | --- |
| 1. Setup: settings | 2 | `pickle_agent/config.py` |
| 1. Setup: usage meter, client | 3 | `pickle_agent/usage.py` |
| 1. Setup: meter self-test | 4 | `tests/test_setup.py::test_usage_meter` |
| 2. Knowledge | 6 | `pickle_agent/knowledge.py` (checks in `tests/test_setup.py`) |
| 3.1 Persona | 8 | `pickle_agent/persona.py` |
| 3.2 Instructions and route instructions | 10 | `pickle_agent/instructions.py` |
| 3.3 System prompt | 12 | `pickle_agent/system_prompt.py` (checks in `tests/test_setup.py`) |
| 4. Tool definitions, gating, docs | 14 | `pickle_agent/tools.py` (the doc printout is `print_tool_docs()`) |
| 4. Logging | 15, first half | `pickle_agent/logbook.py` |
| 4. Tool functions, dispatcher | 15, second half | `pickle_agent/tools.py` |
| 4. Tool tests | 16 | `tests/test_tools.py` |
| 5. `llm_call`, `extract_json` | 18 | `pickle_agent/llm.py` |
| 5. History, agent loop | 19 | `pickle_agent/agent_loop.py` |
| 5. Loop tests, `FakeLLM` | 20 | `tests/test_agent_loop.py`, `FakeLLM` in `tests/conftest.py` |
| 6. Router | 22 | `pickle_agent/router.py` |
| 6. Router tests | 23 | `tests/test_router_reflection_chat.py` |
| 6.1 Router table (LIVE) | 25 | `scripts/router_eval.py` |
| 7. Reflection | 27 | `pickle_agent/reflection.py` |
| 7. Reflection tests | 28 | `tests/test_router_reflection_chat.py` |
| 7. Seeded bad draft (LIVE) | 29 | `scripts/scenarios.py::seeded_reflection_demo` |
| 8. Chat turn, trace, conversation runner | 31 | `pickle_agent/chat.py` |
| 8. Chat turn tests | 32 | `tests/test_router_reflection_chat.py` |
| 8. Eight scenarios (LIVE) | 33 | `scripts/scenarios.py` |
| 9. Gradio interface | 35, 36 | `pickle_agent/app.py` |
| 10. Log viewer | 38 | `scripts/show_logs.py` |
| Printouts of cells 2, 6, 8, 10, 12, 14 | | `scripts/inspect_agent.py` |

## What changed, and only this

1. **Paths.** `BASE_DIR` is the repository folder (from `__file__`) instead of `Path.cwd()`, so the package runs from any folder.
2. **Shared settings are read through the module** (`config.LOG_DIR`, `config.MODEL_ID`, ...). In the notebook every cell saw the same globals; across files, reading `config.X` at call time keeps the notebook's behaviour that the tests can redirect `LOG_DIR`.
3. **No printing on import.** The notebook printed as each cell ran. Those printouts are now `scripts/inspect_agent.py` and `config.describe()`.
4. **Inline asserts became pytest tests.** The `try/finally` that swapped `LOG_DIR` and `QUIET_LOGS` is the `tmp_logs` fixture in `tests/conftest.py`. The disallowed-tool test seeds one lead first, because in the notebook it relied on a lead left by the previous test in the same cell.
5. **Live cells became scripts** (`scripts/router_eval.py`, `scripts/scenarios.py`). They are not part of the tests.
6. **Gradio** is built inside `build_demo()` instead of at import time, and launched by `python -m pickle_agent.app`. One extra test checks that it builds.

## Layout

```
pickle_agent/
├── config.py          settings, paths, the offline switch
├── usage.py           UsageMeter, OfflineModeError, LiveCallLimit, get_client
├── knowledge.py       loads me/business_summary.txt and me/about_business.pdf
├── persona.py         PERSONA (style only)
├── instructions.py    INSTRUCTION_LINES, ROUTE_INSTRUCTIONS (rules only)
├── system_prompt.py   build_system_prompt(route): persona + rules + route rules + knowledge
├── logbook.py         log_event / read_log (logs/*.jsonl)
├── tools.py           TOOL_DEFS (MCP-style), ROUTE_TOOLS, the 2 tools, dispatch()
├── llm.py             llm_call (Responses API), extract_json
├── agent_loop.py      clean_history, agent_turn (the model-tool-model loop)
├── router.py          ROUTER_PROMPT, classify_intent
├── reflection.py      REFLECT_PROMPT, reflect
├── chat.py            chat_turn = router -> agent_turn -> reflect; format_trace
└── app.py             Gradio ChatInterface
scripts/   inspect_agent.py (offline), router_eval.py (LIVE), scenarios.py (LIVE), show_logs.py
tests/     14 offline tests (PICKLE_OFFLINE=1 is forced, so no test can spend money)
```

A message flows: `app.py` -> `chat.chat_turn` -> `router.classify_intent` -> `agent_loop.agent_turn` (-> `tools.dispatch`) -> `reflection.reflect` -> reply.

## Run

```
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest tests                 # 14 offline tests
.venv/bin/python scripts/inspect_agent.py        # see the prompt and tools, no API calls
.venv/bin/python -m pickle_agent.app             # the Gradio demo (LIVE, needs OPENAI_API_KEY)
```
