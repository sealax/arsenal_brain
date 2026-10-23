# Recorded Arsenal Brain agent demonstration

On 23 October 2026, a Codex agent invoked Arsenal Brain's `search_arsenal_knowledge` tool over MCP stdio in three separate live runs. Each run contains a model-selected query, a completed native MCP client event, a matching server response and a final answer. These are actual agent calls, separate from mocked or protocol tests.

| Case | Agent outcome | Evidence |
|---|---|---|
| Founding date and original name | Answered 1886 and Dial Square, citing returned source `arsenal_history.txt:1344-2188` | [Client call, server response and answer](founding.json) |
| Current captain in 2026 | Tool returned no matching sources; agent said the snapshot does not establish the answer | [Trace](missing.json) |
| Emirates Stadium WiFi password | Tool returned stadium passages; agent recognised that they contain no password and declined to invent one | [Trace](unsupported-match.json) |

## What the first run actually did

The user question was: “When was Arsenal founded, and what was the club originally called?”

The agent selected these arguments:

```json
{"question":"When was Arsenal founded and what was its original name?","top_k":3}
```

The tool returned exact passages from the repository's original `arsenal_history.txt`, including:

> In 1886, munitions workers at the Royal Arsenal in Woolwich founded the club as Dial Square.

The agent's recorded final answer was:

> Arsenal was founded in **1886**, originally called **Dial Square**. [source_id: arsenal_history.txt:1344-2188]

The corpus fingerprint, document hash and original character spans are included in each trace. The exported client result is checked against the server result, and passages can be checked against the actual file with `scripts/verify_evidence.py`.

## Verification

- Three live-model runs, each with one successful native MCP call. Requested model: `gpt-6.1-sol`; bundled Codex CLI: `0.162.0-alpha.17.2`. Provider routing is not independently attested.
- Captured implementation commit: `ffbfbb7f4a798ee78028300567a46c7e17c757a7`; each recorded working tree was clean. Later commits add evidence verification and packaging; the retrieval implementation is unchanged.
- [32 passing automated tests](test-results.txt), including actual stdio protocol discovery/calls, input rejection, source-span checks and evidence-tampering checks.
- [Ten deterministic retrieval cases](retrieval-evaluation.json): 10 passed. These are not ten live-agent evaluations or a general retrieval benchmark. They overlap with the regression examples and are not a held-out dataset.
- The three final answers were separately reviewed against the returned passages. No database, embedding service or paid application API was needed inside the tool. The agent used the signed-in Codex account.

## Scope and attribution

This is a local read-only tool using lexical retrieval over the project's existing static corpus. It does not demonstrate pgvector-backed MCP calls, production deployment, third-party adoption or ongoing use. The prompt asks the model to use the connected tool; the model selects its query, consumes the returned text and writes the answer.

Christopher originated Arsenal Brain and requested the extension. Codex generated and tested it in an AI-assisted session. The recorded call proves the integration works with an agent; it does not prove unaided authorship. Christopher should reproduce the run and complete the [technical walkthrough](../../docs/AGENT_DEMO.md#interview-walkthrough) before representing personal proficiency.

Exports contain only public-corpus passages, prompts, tool-call data and run metadata. Raw client logs remain locally ignored; their hashes are recorded for traceability. These are captured project records, not third-party attestations.
