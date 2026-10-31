# Part 1: MCP concepts and a server critique

## MCP in the article

Ksenia Se presents the Model Context Protocol as a fix for integration sprawl. Before MCP, every link between a model and a tool was custom code, so N assistants and M tools meant N×M connectors. With one open protocol, each side implements it once and the cost drops to N+M. MCP is model-facing: a server describes its capabilities, and any compliant agent discovers them at runtime instead of having them hard-coded. A server offers three primitives: tools the model calls, resources the host application reads, and prompt templates the user picks.

The article leaves the roles informal; the specification makes them precise. The **Host** is the application the user talks to (Claude Desktop, an IDE, or my Agents SDK agent); it holds the conversation and calls the model. Inside the host, one **Client** per server keeps a 1:1 connection, lists that server's capabilities and forwards calls as JSON-RPC. The **Server** is a small program wrapping one system, often "just a thin wrapper around that tool's API". As the article warns, more tools do not mean better tool use: "success still hinges on the quality of these descriptions".

## The Fetch server

I read the reference Fetch server (`modelcontextprotocol/servers`, `src/fetch`). It exposes one tool, `fetch(url, max_length, start_index, raw)`, plus the same capability as a prompt. Against the class principles it mostly holds up. Its responsibility is narrow: read one URL. The optional parameters each document their type and default, and the two numeric ones their bounds. Side effects are declared through annotations (read-only, idempotent, open-world). Predictable failures (robots.txt refusal, HTTP error, private address) return `isError` with a readable reason, not silence.

I see three weaknesses. First, errors travel two ways: "No more content available", the truncation notice and a failed HTML simplification arrive as normal text in `<error>` tags, so a client checking `isError` misses them, and none carries an error code. Second, the description fails the "and" test ("Fetches a URL from the internet and optionally extracts its contents as markdown"), yet I would keep `raw` as a flag, because two overlapping fetch tools would cause more wrong picks than one. Third, the description spends a paragraph persuading the model ("this tool now grants you internet access") while the output stays an untyped string. The best idea is the tool and prompt split: the model's tool call obeys robots.txt, the user's prompt does not, which shows who controls each primitive.

## Sources

1. K. Se, "What Is MCP, and Why Is Everyone Suddenly! Talking About It?", Hugging Face blog, 17 Mar. 2025. https://huggingface.co/blog/Kseniase/mcp
2. K. Se, "What Is MCP? Model Context Protocol in Agentic AI, Explained", Turing Post, 15 Mar. 2025. https://www.turingpost.com/p/mcp (the full text of [1]; the quotations come from here)
3. Model Context Protocol, "Specification 2026-07-28: Architecture" and "Server Features". https://modelcontextprotocol.io/specification/2026-07-28/architecture
4. Model Context Protocol, "Fetch MCP Server", `src/fetch` in `modelcontextprotocol/servers`. https://github.com/modelcontextprotocol/servers/tree/main/src/fetch
