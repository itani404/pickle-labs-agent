agent-evolution/c3/
├── pickle_agent/                  one folder per building block, in build order
│   ├── config/                    step 1
│   │   └── settings.py            model, effort, output caps, limits, paths, the offline switch
│   ├── prompt/                    steps 2-5: who the agent is and what it knows
│   │   ├── persona.py             Dr. Rick (style only)
│   │   ├── instructions.py        the 10 rules plus per-route rules
│   │   ├── knowledge.py           loads the summary and the PDF
│   │   └── system_prompt.py       persona + rules + route rules + whole knowledge
│   ├── tools/                     steps 6-9: what the agent can do
│   │   ├── definitions.py         MCP-style TOOL_DEFS (what the model sees)
│   │   ├── gating.py              ROUTE_TOOLS: which route gets which tool
│   │   ├── functions.py           the 2 tools (the code that runs)
│   │   ├── logbook.py             logs/*.jsonl (where the tools write)
│   │   └── dispatcher.py          dispatch(): the guard in front of the tools
│   ├── memory/                    step 10
│   │   └── history.py             clean_history: short-term memory
│   ├── llm/                       step 11: the model connection
│   │   ├── client.py              OpenAI client, cost meter, offline switch
│   │   └── call.py                llm_call: the one function that calls the API
│   ├── loop/                      step 12
│   │   └── agent_loop.py          agent_turn: model → tool → model loop
│   ├── orchestration/             steps 13-15: the pipeline around the agent
│   │   ├── router.py              the intent classifier
│   │   ├── reflection.py          the draft reviewer
│   │   └── chat.py                chat_turn = router → loop → reflection
│   └── interface/                 step 16
│       └── gradio_app.py          Gradio (python -m pickle_agent.interface.gradio_app)
├── scripts/                       inspect_agent.py (free), router_eval.py and scenarios.py (live), show_logs.py
├── tests/                         14 offline tests
└── PORTING.md                     where every notebook cell went, and the only things changed
