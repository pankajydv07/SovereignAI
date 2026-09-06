# Decision Log

Architecture decisions, why they were made, and what would reverse them. Recorded so the team stops re-litigating them in month three.

Status key: **Accepted** · Superseded · Proposed

---

## ADR-001 — Tauri 2, not Electron

**Status:** Accepted

**Decision.** Desktop shell is Tauri 2: system webview plus a Rust backend.

**Why.** 2026 production reports put Tauri at ~15–155 MB bundles and 45–120 MB idle RAM, against Electron's 150–200 MB and 300–500 MB. This app sits open all day beside Ollama holding a 15 GB model. Every megabyte we take is one the model does not get.

**Costs accepted.** No Node APIs in the main process. WebKit/WebView2 instead of bundled Chromium, so rendering differs subtly across platforms. Smaller plugin ecosystem. No Chrome DevTools in production builds. Cross-platform PTY has real sharp edges — Windows `\r\r\n`, shell init scripts, PATH resolution.

**Reverses if.** We need a Chrome-only web API, or Windows PTY reliability becomes unrecoverable.

---

## ADR-002 — Python agent core as a sidecar

**Status:** Accepted

**Decision.** Rust owns the OS surface. A Python sidecar owns the agent loop, routing, ingest and document rendering.

**Why.** The document pipeline *is* Python — OCR, layout models, `python-docx`, `python-pptx`, `openpyxl`, PDF rasterisation, embeddings. Rewriting that ecosystem in Rust is not a real option, and splitting the pipeline across two languages is worse than either.

**Reverses if.** A credible Rust document-generation ecosystem appears. Not soon.

---

## ADR-003 — stdio JSON-RPC, not a local HTTP server

**Status:** Accepted
**Conflicts with:** the external research report, which proposed FastAPI + WebSocket.

**Decision.** Rust ↔ Python communication is JSON-RPC over stdio. The agent core opens no listening socket.

**Why.** A bound port on an air-gapped sovereignty product is an auth surface, a misconfiguration risk, and a demo liability. With stdio, `ss -lntp` shows the agent core listening on nothing at all — that is a demonstrable property, not an assertion. Blobs pass by filesystem path, not over the wire.

**Cost accepted.** Harder to debug. No "open it in a browser tab". We pay this deliberately.

**Reverses if.** We ship a genuine multi-client architecture where several UIs attach to one core. Then the port comes with authentication, and the sovereignty story is re-argued explicitly.

---

## ADR-004 — ACP message shapes, not a bespoke event vocabulary

**Status:** Accepted
**Conflicts with:** the research report's custom event list (`agent.plan`, `tool.request`, `approval.required`, …).

**Decision.** Adopt Agent Client Protocol shapes for session lifecycle, streaming updates, tool calls, permission options, plans, diffs and terminal references.

**Why.** The report's invented vocabulary maps almost 1:1 onto ACP — it re-derived the standard without knowing it existed. ACP has already solved the parts that are easy to get wrong: how to represent a file diff, how to reference a terminal, how permission requests carry options. Adopting it also makes the core headlessly testable and leaves the door open to hosting third-party agents or exposing ours to other editors.

**Cost accepted.** One spec to learn. We extend via `meta` where SWARAJ needs concepts ACP lacks — document provenance, maker–checker, deliverables.

**Reverses if.** ACP stalls or diverges sharply from our needs. Even then the shapes remain a reasonable private format.

---

## ADR-005 — SQLite on the desktop, Postgres on the server

**Status:** Accepted
**Conflicts with:** the research report, which proposed Postgres + pgvector + ParadeDB + Redis everywhere.

**Decision.** Desktop deployment uses SQLite with `sqlite-vec` and FTS5. The shared-server deployment uses Postgres with pgvector.

**Why.** Postgres plus two extensions plus Redis is four services an IT team must install, configure, migrate and keep alive — offline, on a locked-down PSU machine. SQLite is one embedded file: no service, no port, no migration daemon. The report's stack is genuinely better for many concurrent users, which is exactly the server case, and our design already separates the two shapes.

**Reverses if.** The desktop app grows real concurrency needs, or a customer mandates Postgres on workstations.

---

## ADR-006 — Native typed tools; MCP for third parties only

**Status:** Accepted
**Conflicts with:** the research report, which routed all tools including filesystem and terminal through an MCP server on `localhost:8001`.

**Decision.** Our own tools are native, typed Python. MCP is the extensibility seam for outside servers, stdio transport only, allowlisted.

**Why.** Routing our own filesystem reads through HTTP MCP adds a hop, loses end-to-end type safety, and opens another listening socket — the same problem as ADR-003. MCP is a door for guests, not the hallway inside the house.

**Reverses if.** We want tools to be hot-swappable at runtime by end users. Even then, native stays for filesystem and terminal.

---

## ADR-007 — Hand-written agent loop, not LangGraph

**Status:** Accepted, with reservations
**Conflicts with:** the research report, which proposed LangGraph.

**Decision.** Write the plan/act/observe/critique loop ourselves, with SQLite checkpointing.

**Why.** The deciding factor is local models. Open-weight models on Ollama call tools unreliably, and fixing that requires surgery on the exact loop LangGraph encapsulates — argument validation, schema-error repair prompts, structured-output fallback for models without native tool support, per-task-class tool subsetting. We would spend more time fighting the abstraction than it saves. Secondary: a large dependency tree to vet and bundle offline, and an ecosystem that churns fast enough to break code written against it.

**What we concede.** LangGraph's durable checkpointer and `interrupt`-based human-in-the-loop are genuinely well-designed and map cleanly onto our resume-after-crash and approval-gate requirements. We are re-implementing something real, not something trivial.

**Mitigation.** Steal both concepts explicitly: checkpoint after every step, and model pause-for-human as a first-class state rather than a callback.

**Reverses if.** The team grows past ~6 experienced developers, or local tool-calling proves reliable enough that fine control stops mattering.

---

## ADR-008 — CodeMirror 6, not Monaco

**Status:** Accepted (closest call in this log)
**Conflicts with:** the research report, which proposed Monaco.

**Decision.** CodeMirror 6 for diff review and file preview.

**Why.** Users in this product mostly *review* what the agent produced; they do not hand-write code all day. CodeMirror is lighter and far simpler to wire up under Tauri and Vite. Monaco's ~5 MB and worker configuration buy IDE-grade editing we do not need in v1.

**Reverses if.** Hand-editing becomes a primary workflow. Then take Monaco and accept the weight — its built-in diff editor is genuinely better.

---

## ADR-009 — Roles, not model names

**Status:** Accepted

**Decision.** Application code references logical roles (`planner`, `coder`, `writer`, `vision`, `embedder`, `classifier`). `models.yaml` is the only file permitted to name a model. The registry auto-discovers installed models via `/api/tags` and `/api/show`.

**Why.** The problem statement requires that new open-weight models be addable without redesigning the system. Roles satisfy that structurally: adding a model is `ollama pull` plus at most one YAML line. Auto-discovery means Ollama itself reports each model's real capabilities — vision, thinking, tool-calling, context length — so the manifest only supplies what Ollama cannot know.

**Enforcement.** A CI grep fails the build if a model tag appears under `core/`, `apps/` or `packages/`.

---

## ADR-010 — AUTO / ASK / DENY policy vocabulary

**Status:** Accepted
**Adopted from:** the research report, which named this better than we did.

**Decision.** A tool declares a **side-effect class** (`read` / `write` / `exec`) as a static property. The policy engine returns a **decision** (`AUTO` / `ASK` / `DENY`) for a given call in a given context. The two are separate concepts.

**Why.** Clear separation between what a tool *is* and what is *permitted right now*. The engine is deterministic and configurable; the model never decides its own safety.

---

## ADR-011 — Tiered, configurable sandbox

**Status:** Accepted
**Adopted from:** the research report's comparison, with bubblewrap added.

**Decision.** Sandbox mode is an operator setting: **bubblewrap** (default, lightest) → **rootless container** → **gVisor** → **Firecracker microVM**. All run with no network interface.

**Why.** Different deployments have different threat models and different available runtimes. A locked-down PSU workstation may not permit a container runtime at all; bubblewrap needs nothing extra. A server deployment can afford a microVM.

**Stated honestly.** Desktop sandboxing is weaker than server microVM isolation. On Linux with bubblewrap the *network* guarantee is absolute — there is no interface to use — while filesystem and syscall isolation are good but not VM-grade. On Windows, isolation is meaningfully weaker and `code_exec` defaults to requiring approval every time. We say this rather than implying uniform strength.
