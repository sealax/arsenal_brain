# Arsenal Brain agent demonstration

An agent can now search the existing Arsenal history document through one read-only MCP tool, `search_arsenal_knowledge`. Results contain original passages, document hashes and exact character spans so citations can be checked.

This local demo uses lexical retrieval. It does not exercise the separate OpenAI/pgvector API, generate embeddings, refresh football facts or demonstrate production adoption. The tool runs offline; the agent client uses its existing model login. Source passages are sent to that model during a run.

## Setup and tests

From the repository root with Python 3.12:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate_retrieval.py
```

`requirements-demo.lock` records the full tested environment. Install it instead of `requirements-test.txt` to reproduce the captured dependency set. The MCP SDK is pinned to v1.30.0; v2 tutorials use different APIs. Original API dependencies remain separate.

## Record a real agent call

Install Codex CLI and sign in first. The demo uses the existing account's usage allowance. It needs no API key and changes no global settings: the runner supplies temporary per-invocation MCP configuration.

```sh
.venv/bin/python scripts/run_agent_demo.py --case founding
.venv/bin/python scripts/run_agent_demo.py --case missing
.venv/bin/python scripts/run_agent_demo.py --case unsupported_match
```

Each run saves ignored raw client events, stderr, a server tool trace and a shareable `*.evidence.json`. The export records prompt, client call, server response, final answer, corpus fingerprint and code commit. The runner fails without a corresponding real MCP invocation, or if completed events show shell commands, web search or file edits. The prompt explicitly asks the agent to use the tool; the model chooses search arguments. This is not a claim of unprompted tool discovery.

Inspect unsupported cases carefully. A current-captain question has no useful lexical matches. A stadium WiFi question matches passages which lack the answer. The agent should abstain in both; keyword overlap is not answerability. The ten-case evaluation measures retrieval behaviour, not ten live agent conversations.

## Connect manually

Use your client's normal approval controls and replace these absolute paths:

```toml
[mcp_servers.arsenal]
command = "/absolute/path/to/arsenal_brain/.venv/bin/python"
args = ["-m", "app.mcp_server"]
cwd = "/absolute/path/to/arsenal_brain/api"
required = true
```

The server exposes no filesystem path input, writes or arbitrary URLs. `ARSENAL_CORPUS_DIR` selects a corpus at server startup. `ARSENAL_TOOL_TRACE` optionally selects a local log. Questions and passages appear in traces: review before sharing and use public source data.

## Architecture and decisions

```text
Model selects query -> MCP stdio and schemas -> KnowledgeIndex.search
    -> existing data/raw/*.txt -> original passages with citations -> model answer
```

Lexical search keeps a small public-corpus demo reproducible without a database or paid embedding calls. It is a second path alongside the original pgvector API, not vector-backed MCP retrieval. A vector-service adapter can follow with its own integration tests.

Chunks are at most 850 characters with a 180-character target overlap and exact original offsets. TF-IDF-like scores are ranking values, not probabilities. A small explicit alias map handles “originally” versus “founded”; this is not general semantic search. Input limits are 3–500 characters and 1–5 results. The corpus is limited to 100 text files and 2 MB; symlinks are rejected. The server loads a snapshot at startup; restart it after changing sources.

Hashes establish the searched text, not factual truth or freshness. The source contains historical snapshot claims and is not live football data. Retrieved text is untrusted data; guidance to ignore embedded instructions is not a guarantee against every prompt injection.

Two initial tests failed: natural wording found no result, and a chunk boundary separated Herbert Chapman's name from the WM-formation sentence. Query aliases and overlap fixed those labelled cases, which remain as regressions. This narrow validation is not a general accuracy benchmark.

## Interview walkthrough

1. Explain the original retrieval project and why an agent needs a discoverable tool with bounded inputs and structured output.
2. Open `api/app/mcp_server.py`. Explain the schema, read-only hints and transport. Hints describe behaviour; the implementation must enforce it.
3. Open `api/app/knowledge.py`. Trace validation, chunking, ranking and source offsets. Explain a match which cannot answer a question.
4. Run the three demo cases and show the selected query, real tool response and final answer.
5. Run tests and the ten retrieval cases. Distinguish protocol tests, retrieval checks and live-model behaviour.
6. Make one small change yourself, predict the result and verify it. For example, reduce the default result count to two and explain which context is lost or retained. Do not claim to have completed this exercise until you have.

## Attribution and CV wording

Christopher proposed the original project and requested the integration. Codex generated and tested this extension in an AI-assisted session. A trace proves agent invocation, not unaided authorship, external adoption or completion of the walkthrough.

After reproducing and understanding it: “Extended Arsenal Brain with an AI-assisted, read-only MCP retrieval tool; demonstrated agent calls with source-linked answers and explicit handling of unsupported questions.” Link actual traces and tests. Do not claim production scale or pgvector-backed MCP usage from this demo.

## References

- [MCP Python SDK v1.30.0](https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0)
- [MCP tools specification](https://modelcontextprotocol.io/specification/latest/server/tools)
- [Official Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)
