"""Pickle Labs business assistant, Assignment C3, ported from business_agent.ipynb.

One folder per building block, in the order the agent is put together and then called:

    config/         step 1      settings: model, effort, output caps, limits, paths
    prompt/         steps 2-5   persona, instructions, knowledge, and the system prompt that joins them
    tools/          steps 6-9   definitions, gating, functions (+ logbook), dispatch
    memory/         step 10     short-term memory: the cleaned chat history
    llm/            step 11     the OpenAI client, the cost meter, and the one function that calls the model
    loop/           step 12     agent_turn: the model-tool-model loop
    orchestration/  steps 13-15 router, reflection, and chat_turn that chains router -> loop -> reflection
    interface/      step 16     the Gradio app
"""
