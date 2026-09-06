---
trigger: always_on
description: Which process owns what. Read before writing code in any layer.
---

# Architecture boundaries

Write code in the right process. "Just this once" across a boundary is how the architecture dies.

## Ownership map

| Location | Language | Owns | Must NOT contain |
|---|---|---|---|
| `apps/desktop/src/` | TypeScript + React | Rendering, local UI state, dispatching intents | Routing logic, prompt text, tool decisions, business rules |
| `apps/desktop/src-tauri/` | Rust | Windows, PTY, filesystem, process supervision, sandbox launch, egress monitor, app settings | LLM calls, prompts, agent logic, document parsing |
| `core/` | Python | Agent loop, model registry, router, tools, context management, ingest, knowledge base, renderers, audit | PTY handling, window management, any socket bind |
| `packages/protocol/` | JSON Schema | The single definition of every cross-process message | Hand-written duplicates |

## Single-writer rule

Every datastore has exactly one owning process:

- `core/` owns `sessions.db` and the knowledge base.
- `src-tauri` owns `settings.json` and the recent-projects list.

Never write to a store you do not own. Request it through the protocol.

## Types across boundaries are generated, never hand-written

```
packages/protocol/schema/*.json   ← the only source of truth
   ├── core/protocol/models.py       (Pydantic)
   ├── src-tauri/src/protocol.rs     (serde)
   └── apps/desktop/src/protocol.ts  (TypeScript + Zod)
```

Run `make protocol` after any schema change. Never edit a generated file — they carry a header saying so. Hand-mirrored types drift within a week and surface as a runtime bug during a demo.

Wire format is `camelCase`. Python uses `snake_case` internally with Pydantic aliases.

## Protocol shapes follow ACP

We use **ACP (Agent Client Protocol)** message shapes for session lifecycle, streaming updates, tool calls, permission requests, diffs and terminal references. Before inventing a new message concept, check whether ACP already has one — it usually does. Extend via `meta` fields rather than forking the model.

## The test that catches boundary violations

Ask: *could I run the agent core headlessly, driving it with JSON and no UI at all?* If a change makes that impossible, the change is in the wrong layer.
