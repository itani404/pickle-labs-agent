# Study branch `study/c3`: the C3 notebook as a Python package

Local study branch, never pushed. It holds the Assignment C3 business assistant (`business_agent.ipynb`, as submitted on `main` and `assignment-3`) rewritten as plain Python files, so it can be read and diffed against the C4 and C5 versions. The notebook itself is removed from this branch; it is unchanged on `main`.

**Faithful, not improved.** Every function and class is the notebook's code. A check that compares them by syntax tree (ignoring docstrings and the `settings.` prefix) found all 36 identical, and all 13 constants (persona, instructions, tool definitions, prompts, test and scenario lists) are byte-identical.

## Where each notebook cell went

| Notebook | Cell | Now in |
| --- | --- | --- |
| 1. Setup: settings | 2 | `pickle_agent/config/settings.py` |
| 1. Setup: usage meter, client | 3 | `pickle_agent/llm/client.py` |
| 1. Setup: meter self-test | 4 | `tests/test_setup.py::test_usage_meter` |
| 2. Knowledge | 6 | `pickle_agent/prompt/knowledge.py` (checks in `tests/test_setup.py`) |
| 3.1 Persona | 8 | `pickle_agent/prompt/persona.py` |
| 3.2 Instructions and route instructions | 10 | `pickle_agent/prompt/instructions.py` |
| 3.3 System prompt | 12 | `pickle_agent/prompt/system_prompt.py` (checks in `tests/test_setup.py`) |
| 4. Tool definitions | 14 | `pickle_agent/tools/definitions.py` |
| 4. Tool gating, docs printout | 14 | `pickle_agent/tools/gating.py` (`ROUTE_TOOLS`, `tools_for_route`, `print_tool_docs`) |
| 4. Logging | 15, first half | `pickle_agent/tools/logbook.py` |
| 4. Tool functions | 15, second half | `pickle_agent/tools/functions.py` |
| 4. Dispatcher | 15, end | `pickle_agent/tools/dispatcher.py` |
| 4. Tool tests | 16 | `tests/test_tools.py` |
| 5. `llm_call`, `extract_json` | 18 | `pickle_agent/llm/call.py` |
| 5. History (short-term memory) | 19 | `pickle_agent/memory/history.py` (`clean_history`, `TRACE_MARKER`) |
| 5. Agent loop | 19 | `pickle_agent/loop/agent_loop.py` (`agent_turn`, `FALLBACK_REPLY`) |
| 5. Loop tests, `FakeLLM` | 20 | `tests/test_agent_loop.py`, `FakeLLM` in `tests/conftest.py` |
| 6. Router | 22 | `pickle_agent/orchestration/router.py` |
| 6. Router tests | 23 | `tests/test_router_reflection_chat.py` |
| 6.1 Router table (LIVE) | 25 | `scripts/router_eval.py` |
| 7. Reflection | 27 | `pickle_agent/orchestration/reflection.py` |
| 7. Reflection tests | 28 | `tests/test_router_reflection_chat.py` |
| 7. Seeded bad draft (LIVE) | 29 | `scripts/scenarios.py::seeded_reflection_demo` |
| 8. Chat turn, trace, conversation runner | 31 | `pickle_agent/orchestration/chat.py` |
| 8. Chat turn tests | 32 | `tests/test_router_reflection_chat.py` |
| 8. Eight scenarios (LIVE) | 33 | `scripts/scenarios.py` |
| 9. Gradio interface | 35, 36 | `pickle_agent/interface/gradio_app.py` |
| 10. Log viewer | 38 | `scripts/show_logs.py` |
| Printouts of cells 2, 6, 8, 10, 12, 14 | | `scripts/inspect_agent.py` |

## What changed, and only this

1. **Paths.** `BASE_DIR` is the repository folder (from `__file__`) instead of `Path.cwd()`, so the package runs from any folder.
2. **Shared settings are read through the module** (`settings.LOG_DIR`, `settings.MODEL_ID`, ...). In the notebook every cell saw the same globals; across files, reading `settings.X` at call time keeps the notebook's behaviour that the tests can redirect `LOG_DIR`.
3. **No printing on import.** The notebook printed as each cell ran. Those printouts are now `scripts/inspect_agent.py` and `settings.describe()`.
4. **Inline asserts became pytest tests.** The `try/finally` that swapped `LOG_DIR` and `QUIET_LOGS` is the `tmp_logs` fixture in `tests/conftest.py`. The disallowed-tool test seeds one lead first, because in the notebook it relied on a lead left by the previous test in the same cell.
5. **Live cells became scripts** (`scripts/router_eval.py`, `scripts/scenarios.py`). They are not part of the tests.
6. **Gradio** is built inside `build_demo()` instead of at import time, and launched by `python -m pickle_agent.interface.gradio_app`. One extra test checks that it builds.
7. **Files are grouped by building block** (`config/`, `prompt/`, `tools/`, `memory/`, `llm/`, `loop/`, `orchestration/`, `interface/`). The notebook's settings are read as `settings.X` (from `pickle_agent.config import settings`). `tools.py` is split into definitions, gating, functions and dispatcher, and `clean_history` moved from the loop into `memory/`. Only code moved: the syntax-tree check against the flat layout finds all 64 functions, classes and constants identical, except `BASE_DIR`, which needs one more `.parent` because settings sit one folder deeper.

## Layout

One folder per building block, in the order the agent is put together and then called (also listed in `pickle_agent/__init__.py`):

```
pickle_agent/
├── config/          step 1      settings.py: model, effort, output caps, limits, paths, the offline switch
├── prompt/          steps 2-5   persona.py, instructions.py, knowledge.py, system_prompt.py (joins the three)
├── tools/           steps 6-9   definitions.py, gating.py, functions.py (+ logbook.py), dispatcher.py
├── memory/          step 10     history.py: clean_history, the short-term memory
├── llm/             step 11     client.py (OpenAI client, cost meter), call.py (llm_call, extract_json)
├── loop/            step 12     agent_loop.py: agent_turn, the model-tool-model loop
├── orchestration/   steps 13-15 router.py, reflection.py, chat.py (chat_turn = router -> loop -> reflection)
└── interface/       step 16     gradio_app.py
scripts/   inspect_agent.py (offline), router_eval.py (LIVE), scenarios.py (LIVE), show_logs.py
tests/     14 offline tests (PICKLE_OFFLINE=1 is forced, so no test can spend money)
```

Each folder's `__init__.py` re-exports its public names, so `from pickle_agent.tools import dispatch` also works.

A message flows: `interface/gradio_app.py` -> `orchestration/chat.chat_turn` -> `orchestration/router.classify_intent` -> `loop/agent_loop.agent_turn` (-> `tools/dispatcher.dispatch`) -> `orchestration/reflection.reflect` -> reply.

## Run

```
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest tests                 # 14 offline tests
.venv/bin/python scripts/inspect_agent.py        # see the prompt and tools, no API calls
.venv/bin/python -m pickle_agent.interface.gradio_app   # the Gradio demo (LIVE, needs OPENAI_API_KEY)
```
