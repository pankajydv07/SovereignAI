# SWARAJ — Architecture

Companion to `PRD.md` (what to build) and `AGENTS.md` (how to write it). This document covers **tech stack, process design and build order**.

For the *why* behind each choice — including the four decisions where an independent research report disagreed with us — see **`docs/DECISION-LOG.md`** (ADR-001 to ADR-011).

---

## 1. The four decisions everything else follows from

### D1 — Tauri 2 shell, Rust core, Python agent sidecar

**Decision.** A Tauri 2 desktop app. Rust owns the OS surface (windows, PTY, filesystem, process supervision, sandbox launch, egress monitoring). A **Python sidecar** owns the agent loop, model routing, document ingest and deliverable rendering. They speak JSON-RPC over stdio.

**Why Tauri over Electron.** Production reports in 2026 put Tauri 2 at roughly 15–155 MB bundles and 45–120 MB idle RAM against Electron's 150–200 MB and 300–500 MB. This app sits open all day next to the user's other tools on a workstation that is also running Ollama and a 15 GB model; every megabyte we take is a megabyte the model does not get.

**What we accept in exchange** — state these when asked, do not pretend they are not real:
- No Node APIs in the main process (`fs`, `child_process`, `net` are gone). Everything native goes through Rust.
- The webview is WebKit/WebView2, not bundled Chromium, so rendering and Web API behaviour differ subtly across platforms.
- Smaller plugin ecosystem; no Chrome DevTools in production builds.
- Cross-platform PTY has genuine sharp edges — Windows `\r\r\n`, shell init scripts behaving differently in a non-standard terminal, PATH resolution. Budget real time for this; teams consistently underestimate it.

**Why Python for the agent core, and not Rust.** The document pipeline *is* Python: OCR, layout models, `python-docx`, `python-pptx`, `openpyxl`, PDF rasterisation, embeddings. Rewriting that ecosystem in Rust is not a real option, and a hybrid where half the pipeline lives in each language is worse than either. Rust does what Rust is good at; Python does what only Python has libraries for.

**Rejected alternative.** All-Rust: no document ecosystem. All-Electron/Node: same document problem plus the memory cost. Python-only with a web UI: loses the native terminal, the desktop feel, and the whole "works like Claude Code" requirement.

### D2 — ACP as the internal protocol

**Decision.** Adopt **ACP (Agent Client Protocol)** message shapes — Zed's open JSON-RPC-over-stdio standard for editor↔agent communication — as the contract between the UI and the agent core.

**Why.** ACP already defines exactly what this app needs and would otherwise be invented badly: session lifecycle (`new` / `load` / `resume` / `close`), streaming `SessionUpdate` notifications for message and thought chunks, tool-call creation/progress/completion, **permission requests with options** (allow-once / allow-always / deny), plan updates with task status, and first-class content types for **diffs** (`path`, `oldText`, `newText`) and **terminal references** (`terminalId`). It reuses MCP's JSON representations where possible and defaults to Markdown for human-readable text.

**Three consequences worth the adoption cost:**
1. The agent core becomes **headlessly testable** — drive it with JSON, no UI required.
2. The UI physically cannot accumulate business logic, because everything arrives as protocol messages.
3. Optionality for free: later you can host third-party ACP agents inside SWARAJ, or expose SWARAJ's agent to Zed and Neovim. Not a v1 goal, but it costs nothing now and is expensive to retrofit.

**Note.** Adopt the *shapes*, not necessarily the reference implementation. Where SWARAJ needs concepts ACP lacks (document provenance, maker–checker approval, deliverable artefacts), extend via ACP's `meta` fields rather than forking the model.

### D3 — Ollama is the runtime; roles are the abstraction

**Decision.** Ollama only, at `127.0.0.1:11434`. But **no application code names a model.** Code asks for a *role*; `models.yaml` maps roles to ordered candidate models.

```yaml
# models.yaml — the only file that knows model names
roles:
  planner:    [qwen3:30b, gpt-oss:20b]      # tries in order, first available wins
  coder:      [qwen3-coder:30b, qwen3:30b]
  writer:     [qwen3:30b]
  vision:     [qwen2.5vl:7b]
  embedder:   [bge-m3]
  classifier: [bge-m3]                       # embedding + logistic head

overrides:                                    # optional; auto-discovery fills the rest
  qwen3-coder:30b:
    num_ctx: 32768                            # cap below the model max to control VRAM
    keep_alive: 30m                            # residency policy for a hot role
    priors: {code_generate: 0.92, doc_summarise: 0.61}
```

**Auto-discovery is the extensibility mechanism.** On startup the registry calls `GET /api/tags` for installed models, then `POST /api/show` per model to read its real capabilities — vision, thinking, tool-calling — plus context length, parameter size and quantisation. `models.yaml` only supplies what Ollama cannot know: role assignment, context caps, residency policy, task priors.

So **adding a model is `ollama pull` plus at most one YAML line.** With four models today you assign roles; with eight later, nothing in `src/` changes. That is the requirement "new models addable without redesigning the system", satisfied structurally rather than promised.

**Ollama mechanics the design depends on** (these are not incidental — they *are* the multi-model strategy):

| Mechanism | How SWARAJ uses it |
|---|---|
| `keep_alive` per request (duration, `0` to unload now, negative to pin) | The residency manager. Hot role → `30m`; one-shot classification → `0`. Overrides the server default. |
| `OLLAMA_MAX_LOADED_MODELS` (default 3 × GPUs) | Caps concurrent residency. Set deliberately for the target GPU, not left at default. |
| `OLLAMA_NUM_PARALLEL` (default 1) | **RAM scales with `NUM_PARALLEL` × context length.** Leave at 1 on constrained hardware; this is the single easiest way to OOM a demo. |
| Queueing behaviour | If a new model cannot fit in VRAM, requests queue while idle models unload. On GPU, a model must fit *entirely* in VRAM to load concurrently. Surface the queue in the UI rather than letting a request look hung. |
| `GET /api/ps` | Powers the live model-residency view. |
| `options.num_ctx` | Per-model context budget, capped in the manifest. |
| `format` = JSON Schema | **Every structured extraction and every deliverable payload.** Pass the schema, set `temperature: 0`, and also state the schema in the prompt to ground it. |
| `tools` + streaming `thinking` / `content` / `tool_calls` | The agent loop. Accumulate all three per turn, append them together as the assistant message, then append `role: tool` messages with `tool_name`. |
| `images: [...]` (base64 or path) | Vision path. Note images are **not retained between turns** — re-attach when continuity is needed. |

**Honest limitation to design around.** Open-weight 7–11B vision models are usable but inconsistent on dense or low-resolution text, and weak on cursive. The design therefore uses a **dedicated OCR engine for text extraction plus a vision model for structure and handwriting** — the combination measurably beats either alone. Never route a scanned inspection report to a vision model alone and treat the output as ground truth.

### D4 — One codebase, two deployment shapes

All-in-one on a workstation (Ollama local), or the same desktop client pointed at a shared on-premise GPU server running Ollama on the internal network. A single config value. The PRD's demo target is the workstation; MRPL's eventual deployment is the server. Neither is a fork.

---

## 2. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Desktop shell | **Tauri 2** | System webview, Rust backend, capability-based permissions |
| Native core | **Rust 2021**, `tokio` | PTY, FS, process supervision, sandbox launch |
| PTY | **`portable-pty`** (wezterm lineage) | Do not hand-roll; cross-platform PTY is a deep well |
| Terminal UI | **`xterm.js`** + WebGL addon + fit/search addons | Handles ANSI, alt screen buffers, mouse reporting, Unicode widths |
| Frontend | **React 18 + TypeScript + Vite** | `strict: true`, no `any` |
| UI state | **Zustand** + **TanStack Query** | No `useEffect` data fetching |
| Styling | **Tailwind** + design tokens + **shadcn/ui** primitives | Tokens only, no arbitrary values |
| Editor / diff | **CodeMirror 6** | Diff review and file preview; not a full IDE editor |
| Agent core | **Python 3.12**, `asyncio`, **Pydantic v2** | `mypy --strict` |
| Model runtime | **Ollama** | `ollama-python` SDK or direct HTTP to loopback |
| Session store | **SQLite** (WAL) via `aiosqlite` | Sessions, steps, tool calls, audit chain |
| Vector store | **`sqlite-vec`** (workstation) / **pgvector** (server) | One store on the workstation; no separate vector service to air-gap |
| Keyword search | SQLite **FTS5** | Hybrid retrieval; essential for tags and clause numbers |
| Reranking | Cross-encoder via `sentence-transformers` | Local, CPU-acceptable |
| OCR | **Tesseract** and/or **Surya** | Dedicated text extraction; vision model assists, does not replace |
| Layout / preprocess | **OpenCV**, layout-detection model | Deskew, denoise, binarise, region typing |
| Object detection | **RF-DETR** (fine-tuned) | P&ID symbols; a public ~3,800-image / 11-class dataset reaches ~99% mAP@50 |
| PDF | **PyMuPDF** | Rasterisation, born-digital text extraction with coordinates |
| Deliverables | **`python-docx` / `docxtpl`**, **`python-pptx`**, **`openpyxl`** | Deterministic rendering from validated JSON |
| Sandbox (Linux) | **bubblewrap** default; **Podman/Docker** if available | `--unshare-net` — no network interface at all |
| Sandbox (Windows) | Job object + restricted token, network disabled | Honestly weaker than Linux; documented, not overclaimed |
| MCP | Custom **stdio-only** client, allowlisted | No HTTP/SSE transports compiled in |
| Protocol | JSON Schema → Pydantic / serde / Zod, generated | `make protocol` |
| Logging | `structlog` (Python), `tracing` (Rust) | Local files only |
| Packaging | Tauri bundler (`.deb`, `.rpm`, `.AppImage`, `.msi`) + offline wheel/model bundle | No internet at install time |
| CI | GitHub Actions or local runner | mypy, clippy, tsc, ruff, tests, protocol-staleness, **sovereignty grep** |

---

## 3. Process architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  WEBVIEW  (React + TS)                                               │
│  file tree │ sessions │ conversation + tool cards + diffs │ terminal │
└───────────────┬──────────────────────────────────┬───────────────────┘
                │ Tauri IPC (typed commands/events)│
┌───────────────▼──────────────────────────────────▼───────────────────┐
│  RUST CORE  (src-tauri)                                              │
│  • window & menu management                                          │
│  • PTY manager (portable-pty) → byte stream events → xterm.js        │
│  • workspace FS ops, path scoping, file watcher                      │
│  • sidecar supervision (spawn, health, restart, backpressure)        │
│  • sandbox launcher (bubblewrap / container, no network)             │
│  • egress monitor (socket enumeration; optional eBPF)                │
│  • settings.json + recent projects  ← sole owner                     │
└───────────────┬──────────────────────────────────────────────────────┘
                │ JSON-RPC over stdio  (ACP shapes)   ← no socket, no port
┌───────────────▼──────────────────────────────────────────────────────┐
│  PYTHON AGENT CORE  (core/)                                          │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐ │
│  │  Session   │ │ Model        │ │ Router       │ │ Context       │ │
│  │  manager   │ │ registry     │ │ (rules +     │ │ manager       │ │
│  │            │ │ (auto-disc.) │ │  classifier) │ │ (budget,      │ │
│  └────────────┘ └──────────────┘ └──────────────┘ │  compaction)  │ │
│  ┌────────────────────────────┐ ┌───────────────┐ └───────────────┘ │
│  │ Agent loop                 │ │ Tool registry │                    │
│  │ plan → act → observe →     │ │ (typed, class-│                    │
│  │ critique, checkpointed     │ │  ified)       │                    │
│  └────────────────────────────┘ └───────────────┘                    │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐ │
│  │ Ingest     │ │ Knowledge    │ │ Renderers    │ │ Audit         │ │
│  │ OCR/vision │ │ base         │ │ docx/pptx/xls│ │ hash chain    │ │
│  └────────────┘ └──────────────┘ └──────────────┘ └───────────────┘ │
│  owns sessions.db + knowledge base  ← sole owner                     │
└───────────────┬──────────────────────────────────────────────────────┘
                │ HTTP → 127.0.0.1:11434   (the only network call in the product)
┌───────────────▼──────────────────────────────────────────────────────┐
│  OLLAMA        4+ models · keep_alive residency · /api/ps            │
└──────────────────────────────────────────────────────────────────────┘
```

**Why stdio and not a local HTTP server for the sidecar.** No port, no bind, no auth surface, no chance of exposure on a network interface. It makes the sovereignty claim structural: `ss -lntp` shows the agent core listening on nothing at all. Blobs (documents, generated files) pass by filesystem path, not by wire.

---

## 4. The agent loop

```
1. RECEIVE prompt + attachments
2. FEATURISE      modalities, MIME types, est. tokens, code fences, keyword hits
3. CLASSIFY       embedding + logistic head → task class (~20 ms)
                  hard overrides: images → vision; /code → coder; low conf → planner
4. RESOLVE ROLE   task class → role → first available candidate from models.yaml
5. BUILD CONTEXT  system prompt (AGENTS.md hierarchy) + compacted history
                  + retrieved KB chunks + attachment summaries, within budget
6. PLAN           structured output (format=JSON Schema) → render plan → user approves
7. STEP LOOP      for each step:
                    a. permission check → approval request if write/exec
                    b. call model with tools; accumulate thinking/content/tool_calls
                    c. validate tool args against schema → repair loop (max 2)
                    d. execute tool → stream progress to UI
                    e. append assistant msg (thinking+content+tool_calls) and
                       role:tool messages with tool_name
                    f. critique: did this satisfy the step's output schema?
                    g. checkpoint to SQLite
8. GATE           deliverable → maker–checker approval
9. RENDER         validated JSON → deterministic renderer → file + provenance footer
10. SEAL          hash-chained audit record
```

### 4.1 Tool-call reliability on local models — do not skip this

Local open-weight models call tools less reliably than frontier models. This is the single most common reason a local agent "doesn't work", and it is an engineering problem, not a model problem:

1. **Validate before executing.** Parse arguments against the tool's JSON Schema. Never pass unvalidated args to a tool.
2. **Repair, don't fail.** On validation failure, re-prompt with the specific validation error appended (max 2 attempts). Most failures are a wrong field name or a stringified number.
3. **Structured-output fallback.** For a model whose `/api/show` capabilities do not include tool-calling, run a ReAct-style envelope using `format` = JSON Schema with `temperature: 0` instead of native tools.
4. **Constrain the surface.** Expose only the tools relevant to the current task class. A 25-tool menu degrades selection accuracy on small models; 6 well-chosen tools does not.
5. **Prefer few, coarse tools** over many fine-grained ones. `fs_edit` with a diff beats `insert_line` / `delete_line` / `replace_range`.
6. **Tell the model it is in a loop** and may call tools repeatedly — Ollama's own agent-loop guidance, and it measurably helps.

### 4.2 Context management — why it matters more locally

On a cloud model, context is a budget. On Ollama, **`num_ctx` × `OLLAMA_NUM_PARALLEL` is VRAM you do not have**, and exceeding it either OOMs or silently evicts a model you wanted resident. Treat context as a hard physical resource:

- Budget per model from the registry, minus a response reserve.
- File reads support line ranges; whole-file reads over a threshold are refused with a hint to narrow.
- Tool outputs clamped with an explicit truncation marker naming what was dropped.
- Compaction at ~70% of budget: summarise the oldest turns, retain the most recent user messages verbatim, keep all pending plan state.
- Live context meter in the UI. When a user watches the meter, they self-correct before the agent degrades.

---

## 4.3 Policy engine — AUTO / ASK / DENY

Two separate concepts, deliberately:

- A tool's **side-effect class** (`read` / `write` / `exec`) is a static property declared at registration.
- The policy engine's **decision** (`AUTO` / `ASK` / `DENY`) is computed per call, from the side-effect class plus the subject, the resource, and the project's saved preferences.

```
decide(subject, tool, resource, side_effect) -> AUTO | ASK | DENY
```

`AUTO` runs silently (`fs_read`, `kb_search`, `glob`). `ASK` raises an approval request carrying the **exact** command or diff — never a summary — with options allow-once / allow-session / always-allow / deny, persisted per project. `DENY` blocks and logs, and the agent receives a "permission denied" observation it must adapt to.

The engine is deterministic and lives outside the model's reach. **The model never decides its own safety.** Denials are surfaced to the user with the rule that produced them, never silently swallowed.

## 4.4 Session replay and the artifact registry

Every state change is an event, appended to the session log: plan created, step started, tool requested, approval decided, file written, artifact produced, run completed. Two consequences worth building for deliberately:

- **Replay.** The event log alone reconstructs the session's UI state, with no model calls. This is the audit story, and it doubles as demo insurance — if the GPU misbehaves at a venue, a recorded run still shows the workflow end to end.
- **Artifact registry.** Every generated file is registered as it is produced: type, timestamp, approval status, inline preview. It is the surface where a user finds what the agent actually made, rather than scrolling a transcript for it.

## 5. Sandboxing — and where it is honestly weaker

Sandbox strength is an **operator setting**, because a locked-down PSU workstation may not permit a container runtime at all, while a server deployment can afford a microVM:

| Tier | Isolation | Overhead | Extra dependency |
|---|---|---|---|
| **bubblewrap** (default) | Namespaces; `--unshare-net` removes the interface entirely | Minimal | None |
| Rootless container | Namespaces, no root | Minimal | Podman/Docker |
| gVisor | Syscall interposition in user space | 10–30% on I/O-heavy work | runsc |
| Firecracker microVM | Hardware-level, KVM-backed | ~100ms boot | KVM |

All tiers run with **no network interface**. The tier is configurable; the network guarantee is not.

| Control | Linux (primary) | Windows (secondary) |
|---|---|---|
| Network | `bwrap --unshare-net` — **no interface exists** | Network disabled for the job object |
| Filesystem | `--ro-bind /` + `--bind <workspace>` | Restricted token, workspace ACL |
| Process | `--unshare-pid`, `--die-with-parent` | Job object kill-on-close |
| Resources | cgroups v2 CPU/memory/pids caps | Job object limits |
| Syscalls | seccomp allowlist | Not available |

Podman/Docker with `--network=none` is used when a container runtime is present and permitted — stronger, but an extra dependency on a locked-down PSU machine.

**State this plainly rather than overclaiming:** a desktop sandbox is weaker than the microVM isolation a server deployment can use. On Linux with bubblewrap the network guarantee is genuinely absolute (there is no interface to use), while filesystem and syscall isolation are good but not VM-grade. On Windows, isolation is meaningfully weaker and `code_exec` should default to requiring approval every time. Volunteering this earns more credibility than a blanket "it's sandboxed".

---

## 6. Repository layout

```
swaraj/
├─ AGENTS.md                    ← engineering constitution (read first)
├─ PRD.md
├─ Makefile                     ← make dev | protocol | bench | test | demo
├─ models.yaml                  ← the ONLY file naming models
├─ docs/
│  ├─ ARCHITECTURE.md           ← this file
│  ├─ INSTALL.md  OPS-RUNBOOK.md  SECURITY.md
├─ packages/
│  ├─ protocol/schema/          ← JSON Schema source of truth
│  └─ design-tokens/
├─ apps/desktop/
│  ├─ src/                      ← React: components, stores, protocol.ts (generated)
│  └─ src-tauri/src/            ← pty.rs, fs.rs, sidecar.rs, sandbox.rs, egress.rs
├─ core/
│  ├─ protocol/                 ← generated Pydantic models
│  ├─ session/  models/  router/  agent/  context/
│  ├─ tools/                    ← one file per tool
│  ├─ ingest/  kb/  render/  audit/
│  └─ errors.py
├─ eval/                        ← routing testset, graders, bench harness
└─ templates/                   ← org letterhead, note formats
```

---

## 7. Build order

Every milestone ends with something demoable. Never integrate for the first time late.

| # | Milestone | Build | Done when |
|---|---|---|---|
| 0 | **Skeleton + sovereignty** | Tauri shell; Rust core; Python sidecar over stdio; one model streaming; PTY pane with xterm.js; egress monitor | `make demo` on a clean machine; monitor reads 0; `ss -lntp` shows the core listening on nothing |
| 1 | **Protocol + sessions** | JSON Schema → three languages; SQLite sessions; session list; resume | Kill the app mid-session, reopen, history intact |
| 2 | **Agent + tools** | Tool registry; plan/act/critique loop; fs tools; diff review; approval flow; checkpointing | A multi-step file task completes with approvals and a visible trace |
| 3 | **Registry + router** | Auto-discovery via `/api/tags` + `/api/show`; roles; classifier; routing badge; `/api/ps` residency view | Two task types → two models; add a model live with no code change |
| 4 | **Sandbox + code** | bubblewrap runner; `code_exec`; verifier loop; terminal integration | Write → run → fail → repair → pass, visibly; `ip addr` in sandbox shows loopback only |
| 5 | **Ingest + KB** | Preprocess, layout, OCR, vision assist, provenance model; sqlite-vec + FTS5 hybrid + rerank; citations | Click a field → the scan highlights the exact region |
| 6 | **Deliverables** | Renderers, templates, calc engine, maker–checker gate | Journey J1 end-to-end under 90 s |
| 7 | **Vision + P&ID** | RF-DETR symbols, tag OCR, register reconciliation, handwriting | Journey J4 passes |
| 8 | **Hardening** | Audit chain, attestation, eval harness, metrics, docs, offline installer | All PRD acceptance criteria; **feature freeze** |

**Build the egress monitor in milestone 0, before any AI feature.** It is a day of work, it is the product's central claim, and building it first means every later feature is developed inside the constraint instead of being retrofitted into it.

---

## 8. Where vibe-coding will fail on this project

Be deliberate about these; they are the places where prompting produces plausible code that is wrong in ways tests do not catch.

| Area | Failure mode | Countermeasure |
|---|---|---|
| Cross-process boundaries | Hand-mirrored types drift; a field renames on one side only | Generated contracts + staleness gate in CI |
| PTY handling | Works on Linux, subtly broken on Windows; resize not propagated | Write the PTY layer deliberately, with tests; treat Windows as its own task |
| Streaming accumulation | Dropping `thinking` or partial `tool_calls` chunks, producing malformed follow-up requests | Recorded streaming fixtures; a round-trip test per model family |
| Context budgeting | Off-by-one that OOMs the GPU under load | Property tests on the budget arithmetic |
| Path scoping | A traversal case that escapes the workspace | Explicit negative tests; single implementation, one process |
| Cancellation | Tools keep running after the user cancels | Every long-running tool takes a cancellation token; tested |
| Error handling | Broad `try/except` that makes a demo survive while hiding the bug | Banned in `AGENTS.md`; typed errors only |
| Sovereignty | A dependency or CDN link quietly adds egress | Sovereignty grep in CI; per-commit checklist |
| UI density | Rounder, bigger, softer, more whitespace on every regeneration | Tokens only; no arbitrary values; a manual design pass each milestone |

The three UI properties an AI will always "helpfully" undo — **13px base font, 4px radii, and monospaced machine values** — are exactly the three that carry the instrument feel. Re-assert them every time.
