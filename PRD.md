# SWARAJ — Product Requirements Document

> **Sovereign Workbench for AI-assisted Reasoning, Analysis & Judgement**
> An air-gapped, on-premise agentic AI desktop application for confidential industrial knowledge work.

| | |
|---|---|
| **Version** | 1.0 (draft) |
| **Status** | Approved for build |
| **Problem statement** | Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work |
| **Organisation** | Mangalore Refinery and Petrochemicals Limited (MRPL) |
| **Model runtime** | Ollama (local, `127.0.0.1:11434`) |
| **Target platforms** | Linux (primary), Windows 10/11 (secondary) |

---

## 1. Problem

Refineries, PSUs, defence-linked manufacturing units and government offices produce large volumes of routine but sensitive knowledge work: approval notes, board presentations, engineering calculations, internal tooling code, and review of scanned drawings and inspection reports.

None of it can go through cloud AI assistants, because the underlying material is confidential — P&IDs, financials, vendor negotiations, unreleased designs, internal correspondence, business strategy. Organisational policy keeps this data on premises.

The result is a two-sided failure:

1. **Lost productivity.** The work is done manually, at manual speed.
2. **Silent policy breach.** Some staff paste confidential material into public tools anyway. The perimeter is therefore *already* informally breached, without monitoring or record.

Open-weight reasoning models are now good enough to close this gap. The blocker is not model capability — it is that **no deployable product exists that industrial users can work with the way they use Claude Code or Codex.**

### 1.1 Framing

The productivity gap is a *security artefact*. SWARAJ is not "a local ChatGPT"; it is the tool that removes the incentive to leak, while making every action attributable.

---

## 2. Users

| Persona | Role | Primary need |
|---|---|---|
| **Inspection Engineer** | Reads scanned inspection reports, drafts findings | Extract findings from poor scans with verifiable provenance; draft an approval note in the org's format |
| **Deputy Manager (Mech/Process)** | Prepares approval notes, reviews subordinates' work | Draft fast, then **check and sign** work with a full audit trail |
| **Design / Projects Engineer** | Engineering calculations, P&ID review | Calculations with steps shown against cited standards; tag reconciliation against the equipment register |
| **Internal Tools Developer** | Small scripts and internal utilities | A coding agent that runs and verifies code in a sandbox, on-premise |
| **IT / Security Officer** | Owns the air gap | Provable zero egress, per-user access records, tamper-evident audit |

---

## 3. Goals & Non-Goals

### 3.1 Goals

- **G1** — A desktop application whose interaction quality matches Claude Code / Antigravity: open a project folder, run chat sessions, watch the agent use tools, approve commands before they run, see a real terminal.
- **G2** — Multi-model: automatically select the right locally-installed model for the task; add or swap models without code changes.
- **G3** — Genuinely agentic: plan multi-step work, call local tools, iterate on failure, don't stop after one answer.
- **G4** — Multimodal: scanned PDFs, handwritten notes, engineering drawings, photographs — processed on-device.
- **G5** — Real deliverables: DOCX / PPTX / XLSX files, working code, calculations with derivation shown. Not chat replies.
- **G6** — Grounded in the organisation's own manuals, SOPs and correspondence via a local knowledge base.
- **G7** — **Provable** zero egress: demonstrated by logs and a visible monitor, not asserted.
- **G8** — Production-grade: typed, tested, observable, documented, installable by an IT team from an offline bundle.

### 3.2 Non-Goals (v1)

Stated explicitly because scope discipline is the primary delivery risk.

- **Not a general-purpose IDE.** No language servers, no debugger, no refactoring engine, no git GUI, no extension marketplace. We borrow Claude Code's *interaction patterns*, not its coding-IDE surface area.
- No model training or fine-tuning.
- No cloud sync, telemetry, accounts, licensing servers, or auto-update over the internet.
- No mobile or web client.
- No multi-tenant billing.
- No P&ID logic reconstruction (line tracing, control-loop validation) — symbol and tag extraction only.
- No CAD file editing.
- No real-time collaborative editing.

---

## 4. Product Shape

### 4.1 Windows

1. **Launcher** — recent projects, open folder, new project, model status, sovereignty status.
2. **Workspace** — one window per project, containing:
   - **File tree** (left) — the project folder
   - **Sessions list** (left) — persistent chat sessions per project
   - **Conversation** (centre) — messages, tool cards, diffs, plans, approval prompts
   - **Terminal pane** (bottom, tabbed) — real PTY, agent-run commands visible live
   - **Inspector** (right, tabbed) — run trace, sources, deliverables
3. **Settings** — models and roles, tools and permissions, MCP servers, knowledge base, sovereignty, appearance.

### 4.2 Core interaction loop

```
user states a task
   → agent proposes a PLAN (visible, editable, approvable)
   → for each step:  tool call → [approval if required] → execute → observe → critique
   → deliverable produced
   → human review & approval (maker–checker)
   → audit record sealed
```

---

## 5. Functional Requirements

### 5.1 Projects & Sessions

| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | Open an existing folder as a project; create a new project folder | P0 |
| FR-1.2 | Recent-projects list persisted across restarts | P0 |
| FR-1.3 | Multiple named chat sessions per project, persisted to disk | P0 |
| FR-1.4 | Resume a session with full history; rename, archive, delete | P0 |
| FR-1.5 | Session export as Markdown, including tool calls and outputs | P1 |
| FR-1.6 | Multiple project windows open simultaneously | P1 |
| FR-1.7 | Per-project settings override global settings | P1 |
| FR-1.8 | **Session replay** — the complete event log reconstructs the session's UI state for audit or post-hoc review, and can be replayed step by step without re-running any model | P0 |
| FR-1.9 | **Artifact registry** — a per-session list of every generated file with type icon, timestamp, approval status and inline preview | P0 |

### 5.2 Models & Routing

| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | Auto-discover installed Ollama models via `/api/tags` and `/api/show`, including declared capabilities (vision, thinking, tool-calling) and context length | P0 |
| FR-2.2 | **Logical roles** (`planner`, `coder`, `writer`, `vision`, `embedder`, `classifier`) mapped to ordered candidate models in `models.yaml`. Application code references roles, never model names | P0 |
| FR-2.3 | Automatic task classification and role selection across at least the coding / document / vision / extraction classes | P0 |
| FR-2.4 | Routing decision visible per response: chosen model, task class, confidence, latency; expandable to show all candidates and why each lost | P0 |
| FR-2.5 | Add a model by `ollama pull` plus (optionally) one manifest line — **no code change, no restart** | P0 |
| FR-2.6 | Model residency managed via per-request `keep_alive`; live view of loaded models via `/api/ps` | P0 |
| FR-2.7 | Manual model override per session and per message | P1 |
| FR-2.8 | Graceful degradation: if a role has no available model, state which capability is unavailable and what the fallback is | P0 |
| FR-2.9 | Local benchmark harness that measures per-model task-class quality and populates routing priors | P2 |

### 5.3 Agent Runtime

| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | Multi-turn tool-calling loop with streaming, accumulating `thinking`, `content` and `tool_calls` per turn | P0 |
| FR-3.2 | Explicit plan generation, rendered before execution, editable and cancellable by the user | P0 |
| FR-3.3 | Typed tool registry; every tool declares input/output schema, side-effect class, required permission and timeout | P0 |
| FR-3.4 | Tool-call repair: validate arguments against schema, re-prompt on failure (max 2), fall back to structured-output mode for models without native tool support | P0 |
| FR-3.5 | Step checkpointing; a session survives application restart mid-run and resumes or replays | P0 |
| FR-3.6 | Budget caps per run: max steps, max tokens, wall-clock. Exceeding a cap is a clean terminal state with partial results retained | P0 |
| FR-3.7 | Cancellation at any point, with in-flight tools terminated | P0 |
| FR-3.8 | Critique step after each tool call; retry with the error in context before escalating | P1 |
| FR-3.9 | Depth-limited subagents for parallelisable work (e.g. per-page extraction) | P2 |

### 5.4 Tools

| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | `fs_read`, `fs_list`, `glob`, `grep` — scoped to the project directory | P0 |
| FR-4.2 | `fs_write` — always surfaced as a reviewable **diff** before applying | P0 |
| FR-4.3 | `terminal_exec` — runs in a real PTY, output streamed to the terminal pane, **approval required** | P0 |
| FR-4.4 | `code_exec` — executes in a **network-isolated sandbox**, workspace-scoped, resource-capped | P0 |
| FR-4.5 | `kb_search` — hybrid retrieval over the local knowledge base with citations | P0 |
| FR-4.6 | `doc_ingest` — PDF/image ingestion producing structured content with per-field confidence and bounding boxes | P0 |
| FR-4.7 | `vision_analyse` — vision-model analysis of images and document regions | P0 |
| FR-4.8 | `render_docx`, `render_pptx`, `render_xlsx` — deterministic template rendering from validated JSON | P0 |
| FR-4.9 | `sheet_ops` — read/compute/write spreadsheets with formulas preserved | P1 |
| FR-4.10 | `calc` — model writes a function with assertions; sandbox executes it; steps captured for the deliverable | P0 |
| FR-4.11 | MCP client (**stdio transport only**) with an explicit server allowlist | P1 |

### 5.5 Permissions & Approvals

| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | Every tool call classified `read` / `write` / `exec`; `write` and `exec` require approval by default | P0 |
| FR-5.2 | Approval options: **Allow once / Allow for this session / Always allow / Deny**, persisted per project | P0 |
| FR-5.3 | Approval prompt shows the exact command or diff that will be executed — never a summary | P0 |
| FR-5.4 | Auto-approve allowlist configurable per project (e.g. `git status`, `pytest`) | P1 |
| FR-5.5 | Maker–checker gate on every generated deliverable, with reviewer identity recorded | P0 |
| FR-5.6 | Rejection requires a reason; the reason is retained in the audit record | P0 |
| FR-5.7 | Deliverable approval is blocked while any low-confidence extracted field remains unverified | P0 |

### 5.6 Multimodal Ingest

| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | Classify PDFs as born-digital or scanned and route accordingly | P0 |
| FR-6.2 | Image preprocessing: deskew, denoise, binarise, upscale | P0 |
| FR-6.3 | Layout detection with region typing (text, table, formula, figure, handwriting, stamp) | P0 |
| FR-6.4 | OCR via a dedicated engine, with vision-model assistance for handwriting and complex regions | P0 |
| FR-6.5 | Every extracted field carries value, unit, confidence, page and bounding box | P0 |
| FR-6.6 | Click-through provenance: field ↔ source region, bidirectional | P0 |
| FR-6.7 | Fields below the confidence threshold are flagged and require human verification | P0 |
| FR-6.8 | P&ID symbol detection plus instrument-tag OCR, reconciled against an equipment register; unreadable tags reported explicitly | P1 |
| FR-6.9 | Hindi / bilingual document support | P1 |

### 5.7 Knowledge Base

| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | Ingest from local folders and SMB shares; incremental re-index on change | P0 |
| FR-7.2 | Layout-aware chunking with heading path retained | P0 |
| FR-7.3 | Hybrid retrieval (keyword + vector) with reranking | P0 |
| FR-7.4 | Document classification levels and role-based retrieval filtering, enforced **in the data layer** | P0 |
| FR-7.5 | Citations with click-through to the source region | P0 |
| FR-7.6 | Superseded revisions excluded by default and labelled when shown | P0 |
| FR-7.7 | Retrieval log: who queried what, and which documents were returned | P1 |

### 5.8 Deliverables

| ID | Requirement | Priority |
|---|---|---|
| FR-8.1 | Model emits schema-validated JSON; deterministic renderers produce the file. The model never emits file bytes | P0 |
| FR-8.2 | Types: approval note, inspection summary, review deck, cost sheet, engineering calculation | P0 |
| FR-8.3 | Organisation templates loaded from a user-managed folder (letterhead, note format) | P0 |
| FR-8.4 | Calculations executed as sandboxed code, never generated arithmetic; derivation table rendered with cited standards | P0 |
| FR-8.5 | Provenance footer on every generated file: models used, run id, sources, confidence, approval state | P0 |
| FR-8.6 | Spreadsheet formulas preserved as live formulas | P1 |

### 5.9 Context Management

| ID | Requirement | Priority |
|---|---|---|
| FR-9.1 | Per-model context budget derived from the registry, with a reserve for the response | P0 |
| FR-9.2 | `AGENTS.md` hierarchy loaded into the system prompt: global → project → subdirectory, nearest wins | P0 |
| FR-9.3 | Automatic compaction (summarise oldest turns) at a configurable share of budget | P0 |
| FR-9.4 | Tool output clamping with explicit truncation markers; file reads support line ranges | P0 |
| FR-9.5 | Live context-usage indicator in the UI | P1 |
| FR-9.6 | `/compact`, `/clear`, `/context` session commands | P1 |

### 5.10 Sovereignty & Audit

| ID | Requirement | Priority |
|---|---|---|
| FR-10.1 | No component makes any network connection other than to `127.0.0.1` (Ollama). No listening socket is opened by the agent core | P0 |
| FR-10.2 | Persistent sovereignty indicator on every screen | P0 |
| FR-10.3 | Live egress monitor: connection attempts with process, destination and verdict; blocked attempts pinned until acknowledged | P0 |
| FR-10.4 | Loss of physical network link is presented as a **success** state, not an error | P0 |
| FR-10.5 | Signed attestation report: interfaces, routes, egress log, model hashes | P1 |
| FR-10.6 | Hash-chained append-only audit log with an integrity verification action | P0 |
| FR-10.7 | Fully offline installation from a bundle; no internet required at any point | P0 |

---

## 6. Key User Journeys

### J1 — Scanned inspection report → approval note *(the flagship demo)*
1. Engineer opens the project and drops in a 6-page scanned inspection report.
2. Ingest reports "scanned, 6 pages, handwriting detected"; the agent proposes a plan.
3. Engineer approves. The agent extracts findings, cross-checks SOP-114 in the knowledge base, computes remaining life via sandboxed code, and drafts the note.
4. Two low-confidence fields are amber-flagged; the engineer clicks one, sees the exact highlighted region on the scan, and confirms the value.
5. Approval gate fires. A checker reviews the draft with citations, then approves.
6. A DOCX on the organisation's letterhead is produced, with a derivation table and provenance footer. The audit record is sealed.

**Acceptance:** end-to-end in under 90 seconds on the demo machine; every substantive claim cited; approval impossible while a flagged field is unverified.

### J2 — Coding task, verified in a sandbox
Engineer asks for a script to parse thickness-survey CSVs and flag readings below the retirement limit. The router selects the coder model. The agent writes code and tests, runs them in the sandbox, sees one failure, repairs it, and re-runs to green. Terminal output is visible throughout. `ip addr` inside the sandbox shows loopback only.

**Acceptance:** the fix-and-rerun cycle is visible; the sandbox has zero network interfaces.

### J3 — Model auto-selection
Two prompts in one session — a document summary, then a coding request — route to different models. The routing badge changes; the model-residency view shows the swap. Adding a fifth model requires only `ollama pull` and one manifest line.

**Acceptance:** ≥95% top-1 routing accuracy on a held-out labelled set; routing overhead under 50 ms.

### J4 — Engineering drawing
Engineer uploads a scanned P&ID. Output: annotated overlay, symbol inventory by class, extracted instrument tags with confidence, unreadable tags flagged, and a reconciliation table against the equipment register showing one tag absent from the register.

**Acceptance:** tag extraction accuracy reported honestly; unreadable regions never silently dropped.

### J5 — Sovereignty proof
The monitor reads zero throughout. An operator runs `curl https://api.anthropic.com` inside the sandbox: it fails, the blocked counter increments, and the event appears with process and destination. The network cable is then unplugged and J1 is repeated with no degradation.

**Acceptance:** zero external packets across a 60-minute session; 100% of deliberate attempts logged.

---

## 7. Non-Functional Requirements

| Area | Requirement |
|---|---|
| **Performance** | App cold start < 3 s; UI interaction < 100 ms; first token < 2 s on a resident model; PTY output latency < 50 ms |
| **Footprint** | Installer < 250 MB excluding models; idle RAM < 400 MB excluding Ollama |
| **Reliability** | No data loss on crash — sessions checkpointed per step; sandbox crash never takes down the app |
| **Security** | Workspace-scoped filesystem access; sandboxed execution with no network; no secrets in logs; MCP stdio-only with allowlist |
| **Accessibility** | Full keyboard operability; WCAG AA contrast; never colour-alone signalling; legible at 150% scaling |
| **Observability** | Structured logs, per-run traces, model/token/latency metrics, all local |
| **Installability** | Offline bundle; documented prerequisites; single-command install verified on a clean machine |
| **Licensing** | Only permissively licensed dependencies and open-weight models; licence surfaced per model in the UI |

---

## 8. Success Metrics

| Metric | Target |
|---|---|
| Router top-1 accuracy | ≥ 95% on a 300-item held-out set |
| Routing overhead | < 50 ms p95 |
| OCR field accuracy (printed) | ≥ 95% on a 50-report labelled corpus |
| OCR field accuracy (handwritten) | ≥ 85% |
| Instrument-tag extraction | ≥ 90% exact match after validation |
| Scanned report → drafted note | < 90 s end-to-end |
| External egress | **0 packets**, whole session |
| Blocked-attempt detection | 100% logged with process and destination |
| Audit chain integrity | 100% of runs in an unbroken chain |
| Approval note drafting time | ~45 min → ~6 min (measured with 5 users) |

---

## 9. Release Plan

| Milestone | Contents | Exit criterion |
|---|---|---|
| **M0 — Skeleton** | Tauri shell, Rust core, Python sidecar over stdio, one model, streaming chat, PTY pane, egress monitor | `make demo` works on a clean machine; monitor reads 0 |
| **M1 — Agent** | Tool registry, plan/act loop, fs tools, diff review, approval flow, checkpointing | A multi-step file task completes with approvals |
| **M2 — Routing** | Registry auto-discovery, roles, classifier, routing badge, residency view | Two task types route to different models; a new model added live |
| **M3 — Sandbox & code** | Sandbox runner, `code_exec`, verifier loop, terminal integration | J2 passes end-to-end |
| **M4 — Documents** | Ingest pipeline, provenance UI, knowledge base, citations | A scanned report is extracted with click-through provenance |
| **M5 — Deliverables** | Renderers, templates, calc engine, maker–checker | J1 passes end-to-end |
| **M6 — Vision** | P&ID detection, tag reconciliation, handwriting | J4 passes |
| **M7 — Hardening** | Audit chain, attestation, metrics, eval harness, docs, offline installer | All acceptance criteria met; feature freeze |

---

## 10. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Effort exceeds available capacity** | **Highest** | An independent estimate for this scope came to roughly **35 person-weeks — 4–8 developers over several months**. That is honest for everything described here. Treat §3.2 and the milestone table as a forcing function: build M0–M5 to production quality rather than M0–M8 to demo quality. Half-built features score zero, not half. |
| Scope creep toward a general IDE | **Highest** | §3.2 is enforced by a named owner; any addition must displace something |
| Local models call tools unreliably | High | Tool-call repair layer (FR-3.4); structured-output fallback; role-based model choice |
| Context exhaustion on local models | High | Hard budgets, compaction, output clamping — `num_ctx` × parallelism is VRAM you don't have |
| Desktop sandboxing weaker than server isolation | Medium | Bubblewrap/container with no network by default; documented honestly, never overclaimed |
| VRAM thrash from model swapping | Medium | `keep_alive` policy per role; residency caps; swap cost in the routing score |
| Handwriting OCR underperforms | Medium | Confidence flagging with mandatory verification is already the design; report the real number |
| Cross-platform PTY edge cases | Medium | Linux first; Windows treated as a separate hardening task, not an afterthought |
| Vibe-coded architecture drift | High | `AGENTS.md`, generated cross-language contracts, CI gates, per-module definition of done |

---

## 11. Open Questions

1. Which four models are installed, and what are their exact tags and quantisations? (Determines the initial role map.)
2. Is there a real MRPL approval-note template available, or should a representative one be authored?
3. Single-user workstation only, or must a shared GPU server serve multiple users in v1?
4. Is a container runtime permitted on target machines, or must sandboxing rely on bubblewrap alone?
