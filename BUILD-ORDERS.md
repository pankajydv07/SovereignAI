# BUILD-ORDERS.md — Prompts for building SWARAJ with Antigravity

Copy-paste prompts, in order. Each produces one verifiable slice. The starter kit (`AGENTS.md`, `.agents/rules/`, `.agents/workflows/`) must already be in the repo root.

---

## How to run these

**One prompt, one commit.** Commit before each prompt so you always have a clean rollback point. This is the cheapest insurance available.

**Fresh session per prompt.** Antigravity carries context within a session. A long session drifts and gets expensive. Start a new one per prompt; the rules files reload automatically.

**Read every diff.** The failure mode of AI-assisted building is not bad code — it is *plausible* code that quietly crosses an architectural boundary. That passes tests and surfaces in month three.

**Re-anchor when it drifts.** One sentence usually does it:

> This is a professional instrument for engineers in a refinery control-room environment — dense, calm, monospaced for machine facts, zero consumer-chat conventions. Re-read `.agents/rules/50-design-lock.md`.

**Never accept "done" without evidence.** A screenshot, a passing test, or a command output. Not a claim.

### Template for anything not covered here

```
GOAL: <one sentence>
READ FIRST: <the specific rule and doc files that apply>
CONSTRAINTS: <the invariants this touches>
DONE WHEN: <observable criteria, not "it works">
VERIFY BY: <the command or screenshot that proves it>

Plan first and show me the plan. Do not write code until I confirm.
```

---

# Session 0 — Verify the kit is live

Run this once, before anything else.

```
Which rules, workflows and skills are installed in this workspace?

List each one with its file path and activation mode. Then read AGENTS.md,
GEMINI.md and docs/ARCHITECTURE.md and summarise back to me in 10 bullet points:
what we are building, the seven invariants, and which process owns what.

Do not write any code.
```

**Check the answer names all 8 rules, 6 workflows and the `swaraj-domain` skill.** If it doesn't see them, the paths are wrong — fix that before writing a line of code.

---

# Milestone 0 — Skeleton and the sovereignty proof

Build the egress monitor **before any AI feature**. It is a day of work, it is the product's central claim, and building it first means every later feature is developed inside the constraint instead of retrofitted into it.

### P0.0 — Grill the milestone

```
/grill-me

I am starting milestone 0 of SWARAJ: the application skeleton plus the
sovereignty monitor. Grill me until the scope is unambiguous.

Context you must not have to guess: Tauri 2 + Rust + React/TS/Vite/Tailwind.
Python 3.12 agent core as a sidecar over stdio JSON-RPC — no listening socket.
Ollama-only at 127.0.0.1:11434. Linux primary, Windows secondary.
Read AGENTS.md and docs/ARCHITECTURE.md first.
```

### P0.1 — Repo scaffold

```
GOAL: Create the monorepo scaffold for SWARAJ. No AI features yet — structure only.

READ FIRST: README.md (repo layout), AGENTS.md, .agents/rules/10-architecture-boundaries.md

BUILD:
- apps/desktop/ — Tauri 2 app, React 18 + TypeScript + Vite + Tailwind, strict tsconfig
- apps/desktop/src-tauri/ — Rust workspace, tokio, thiserror
- core/ — Python 3.12 package, pyproject with pydantic v2, mypy strict, ruff
- packages/protocol/ — empty schema dir with a README explaining generation
- packages/design-tokens/ — tokens from docs/UI-SPEC.md as CSS variables and a
  Tailwind theme extension. Self-host Inter and IBM Plex Mono; a Google Fonts
  link would be a sovereignty defect.

DONE WHEN:
- `make setup`, `make lint`, `make typecheck` all pass on a clean checkout
- The app window opens showing only the 44px top bar and the 56px left rail
- Base font renders at 13px, radii at 4px

VERIFY BY: screenshot of the empty shell, plus `make lint typecheck` output.

Plan first. Do not add any feature beyond the shell.
```

### P0.2 — Sidecar over stdio

```
GOAL: Rust spawns and supervises the Python core, communicating over stdio JSON-RPC.

READ FIRST: .agents/rules/00-sovereignty.md, .agents/rules/10-architecture-boundaries.md

BUILD:
- Rust: spawn the Python core as a child process with piped stdin/stdout/stderr.
  Supervise it: health ping, restart on crash with backoff, clean shutdown.
- Python: a JSON-RPC loop over stdin/stdout. Implement `initialize` and `ping`.
- Log stderr from the child into the Rust tracing output.

CONSTRAINTS:
- NO listening socket anywhere. No FastAPI, no uvicorn, no port binding.
- Structured errors on both sides, no unwrap() outside main().

DONE WHEN:
- The app pings the core on startup and shows its version in the top bar
- Killing the Python process makes it restart within 2s, visible in the UI
- `ss -lntp` shows nothing listening from this app

VERIFY BY: paste the `ss -lntp` output and show the restart happening.
```

### P0.3 — Streaming chat through the core

```
GOAL: End-to-end streaming from Ollama through the core to the UI. One model, no routing.

READ FIRST: .agents/rules/70-local-models.md

BUILD:
- core/models/ollama.py — async client for /api/chat with streaming.
  Accumulate `thinking`, `content` and `tool_calls` separately per turn.
- core/models/registry.py — read models.yaml, resolve Role.WRITER to a tag.
  NO model name anywhere outside models.yaml.
- Stream tokens over the stdio protocol to the UI as they arrive.
- A minimal conversation pane: no bubbles, no avatars. Full-width blocks with a
  2px left border, per docs/UI-SPEC.md.

DONE WHEN:
- Typing a message streams a response with zero layout shift
- A Stop button cancels mid-stream and the process actually stops
- `make model-names` passes

VERIFY BY: screenshot mid-stream, plus `make model-names`.
```

### P0.4 — Terminal pane

```
GOAL: A real PTY terminal in the bottom pane.

READ FIRST: .agents/rules/30-rust.md

BUILD:
- Rust: PTY manager using portable-pty. One PTY per terminal tab. Stream bytes
  to the frontend as events. Handle resize, and propagate it to the PTY.
- Frontend: xterm.js with the WebGL renderer and fit addon. Tabs. Persistent
  scrollback across tab switches.

CONSTRAINTS:
- Do not write a custom terminal renderer. xterm.js handles ANSI, alternate
  screen buffers, mouse reporting and Unicode widths.
- Resize must propagate, or full-screen programs render wrongly. Test it.

DONE WHEN:
- `vim` and `htop` render correctly and respond to resizing the pane
- Colours, progress bars and interactive prompts all work
- Closing a tab kills its process

VERIFY BY: screenshot of htop running in the pane after a resize.
```

### P0.5 — The sovereignty monitor

```
GOAL: The egress monitor and sovereignty rail. This is the product's central claim.

READ FIRST: docs/SECURITY.md, docs/UI-SPEC.md (Sovereignty monitor section)

BUILD:
- Rust: enumerate outbound socket activity for our process tree. If bpftrace or
  a cilium/ebpf probe is available, use a tcp_connect kprobe; otherwise fall back
  to periodic /proc/net polling and say so in the UI.
- Record every attempt: pid, process name, destination, port, verdict.
- Persistent rail in the top bar on every screen: shield, AIR-GAPPED,
  EGRESS 0, GPU %.
- Full Sovereignty screen: hero counter, four verified assertions, live event feed.
  Internal rows dim; blocked rows critical-coloured, 2px left border, PINNED to the
  top until acknowledged.

CRITICAL BEHAVIOUR:
- Losing the physical network link shows a GREEN success banner:
  "AIR-GAPPED — no physical network link detected. All functions nominal."
  No reconnect button.
- If the monitor is not attached, do NOT show green. Show amber:
  "Egress monitoring inactive — enforcement is active but unverified."

DONE WHEN:
- The rail reads 0 and stays there
- Running `curl https://api.anthropic.com` in the terminal produces a pinned
  blocked row with pid and destination within one second
- Unplugging the network shows the green banner

VERIFY BY: screenshots of all three states.
```

### P0.6 — Close the milestone

```
/milestone-check
```
```
/sovereignty-audit
```

Then take the screenshot of the sovereignty panel reading zero. **That screenshot goes in your SIH submission deck.**

---

# Milestone 1 — Protocol and sessions

### P1.1 — Generated protocol types

```
GOAL: One schema source generating types for Python, Rust and TypeScript.

READ FIRST: .agents/rules/10-architecture-boundaries.md, docs/DECISION-LOG.md ADR-004

BUILD:
- packages/protocol/schema/*.json — JSON Schema, camelCase wire format.
  Adopt ACP shapes: session lifecycle, SessionUpdate notifications, tool calls,
  permission requests with options, plan updates, diff and terminal content types.
  Where SWARAJ needs concepts ACP lacks (provenance, maker-checker, deliverables),
  extend via meta fields rather than inventing parallel concepts. Tell me which.
- packages/protocol/generate.py — emits Pydantic, serde and TypeScript+Zod.
  Every generated file carries a "// GENERATED — do not edit" header.

DONE WHEN:
- `make protocol` regenerates all three cleanly
- `make protocol-fresh` passes
- A round-trip test proves a message survives Python → Rust → TypeScript unchanged

VERIFY BY: the round-trip test output.
```

### P1.2 — Session store

```
GOAL: Persistent sessions in SQLite, owned solely by the Python core.

READ FIRST: docs/DECISION-LOG.md ADR-005

BUILD:
- SQLite (WAL) with aiosqlite. Tables: projects, sessions, events, steps,
  tool_calls, artifacts.
- Sessions are an append-only EVENT LOG — every state change is an event.
  This is what makes replay possible later; design for it now.
- Protocol methods: session/new, session/load, session/resume, session/close,
  session/list.

CONSTRAINTS:
- The core is the sole writer. Rust never touches this database.

DONE WHEN:
- Kill the app mid-session, reopen, history is intact and complete
- Session list loads in under 100ms with 100 sessions

VERIFY BY: demonstrate the kill-and-resume.
```

### P1.3 — Project and session UI

```
GOAL: Project picker and session list, wired to the real core.

READ FIRST: docs/UI-SPEC.md, .agents/rules/40-typescript-react.md

BUILD:
- Launcher window: recent projects, open folder, model status, sovereignty status
- Left rail: file tree (real, from Rust) and session list
- New session, rename, archive, delete
- Session resume restores the full transcript

DONE WHEN:
- All five states implemented for both lists: default, empty, loading with named
  stage, error with a working remedy button, degraded
- No mock data anywhere
- Keyboard navigation works, focus rings visible

VERIFY BY: screenshot of each of the five states.
```

---

# Milestone 2 — The agent loop

This is the heart. Take it slowly.

### P2.0 — Grill it

```
/grill-me

Milestone 2 of SWARAJ: the agent runtime — tool registry, plan/act/observe/critique
loop, policy engine, approval gates, checkpointing.

Constraints you must not have to guess: local Ollama models call tools unreliably,
so argument repair is mandatory. Read .agents/rules/70-local-models.md first.
Grill me on failure modes, cancellation, and what happens when a step fails twice.
```

### P2.1 — Tool registry and the first tools

```
/new-tool
```
Then, in the same session:
```
Implement the tool registry infrastructure plus three tools: fs_read, fs_list, glob.

The registry must derive the Ollama `tools` JSON schema automatically from each
tool's Pydantic input model. Never hand-write that schema.

Every tool declares: name, kind, side_effect (read/write/exec), scopes,
timeout_s, input_model, output_model.

fs_read must support line ranges and refuse whole-file reads over a threshold
with a hint to narrow — context is VRAM here.

All paths go through workspace scoping. Write negative tests for ../,
absolute paths, and symlinks pointing outside the workspace.
```

### P2.2 — The turn loop

```
GOAL: The agent turn loop with tool calling and repair.

READ FIRST: .agents/rules/70-local-models.md, docs/ARCHITECTURE.md §4

BUILD:
- Stream from Ollama accumulating thinking + content + tool_calls per turn.
  Append them together as one assistant message, then append role:"tool"
  messages with tool_name. Dropping any of the three produces a malformed
  follow-up that fails in a way that looks like a model problem.
- Validate tool arguments against the schema BEFORE executing.
- On validation failure, re-prompt with the exact validation error, max 2
  attempts, then fail cleanly with a useful message.
- For models whose /api/show shows no tool-calling capability, fall back to
  structured output: JSON Schema in `format`, temperature 0, schema restated
  in the prompt.
- Expose at most 6 tools per task class.

DONE WHEN:
- A test feeds deliberately malformed arguments and repair converges
- A test replays a tool call split across streaming chunks and reassembles it
- The loop terminates cleanly on budget exhaustion with partial results kept

VERIFY BY: those two tests passing.
```

### P2.3 — Plan preview

```
GOAL: The agent produces a visible plan before executing.

BUILD:
- Plan generation via structured output (JSON Schema in `format`, temperature 0)
- Plan card in the conversation: numbered steps, tool icon, expected output
  schema name, side-effect chip. Amber chip on steps needing approval.
- Actions: Run plan / Edit plan / Cancel. Editing allows reorder and delete.

DONE WHEN: a multi-step task shows its plan and waits. Editing the plan changes
what executes.

VERIFY BY: screenshot of a 5-step plan, then the trace showing it executed in
the edited order.
```

### P2.4 — Policy engine and approvals

```
GOAL: AUTO / ASK / DENY, with an approval UI that shows the exact action.

READ FIRST: docs/ARCHITECTURE.md §4.3

BUILD:
- decide(subject, tool, resource, side_effect) -> AUTO | ASK | DENY.
  Deterministic, outside the model's reach. The model never decides its own safety.
- ASK raises an approval request showing the EXACT command or diff — never a
  summary. Options: allow once / allow session / always allow / deny.
  Persist the choice per project.
- DENY blocks, logs, and returns a "permission denied" observation the agent
  must adapt to.
- The approval card renders inline in the trace as a blocking card. The run
  visibly halts — it must feel deliberate, not like a stall.

DONE WHEN:
- A write outside scratch pauses and shows the diff
- "Always allow" persists across restart
- A denied action shows the rule that denied it and the role required

VERIFY BY: screenshots of the approval card and a denial.
```

### P2.5 — Checkpointing and the run trace

```
GOAL: Every step checkpointed; the trace renders live; runs resume after a crash.

BUILD:
- Checkpoint to SQLite after every step transition
- Run trace UI per docs/UI-SPEC.md: budget meter, 30px step rows, status glyphs,
  expandable input/output JSON, failed steps showing retry count and the
  critique text verbatim
- New steps slide in over 120ms; auto-scroll unless the user scrolled up
- Kill the app mid-run, reopen, resume from the last checkpoint

DONE WHEN: the kill-and-resume works and the trace is complete afterwards.

VERIFY BY: demonstrate it.
```

### P2.6 — Close

```
/milestone-check
```

---

# Milestone 3 — Registry and router

### P3.1 — Auto-discovery

```
GOAL: The registry discovers installed models and their real capabilities.

READ FIRST: .agents/rules/70-local-models.md, docs/DECISION-LOG.md ADR-009

BUILD:
- On startup: GET /api/tags for installed models, then POST /api/show per model
  for capabilities (vision, thinking, tool-calling), context length, parameter
  size, quantisation.
- Merge with models.yaml: role assignment, num_ctx caps, keep_alive policy, priors.
- Residency management via per-request keep_alive. Hot role 30m, one-shot 0.
- Poll /api/ps for the live residency view.

DONE WHEN:
- The model roster page lists your real installed models with real capabilities
- Adding a model with `ollama pull` makes it appear without restarting the app
- `make model-names` passes

VERIFY BY: screenshot of the roster, and add a model live.
```

### P3.2 — The router

```
GOAL: Two-stage routing with measured accuracy.

BUILD:
- Stage 0: featurise (modalities, mime types, estimated tokens, code fences,
  keyword hits)
- Stage 1: embedding + logistic head → task class, ~20ms. Hard overrides:
  images → vision; /code → coder; confidence below floor → planner.
- Stage 2: capability match against the registry
- Stage 3: score = quality prior + VRAM fit + latency estimate − swap cost
- Stage 4: verifier failure escalates once to the declared fallback

- eval/routing_testset.jsonl — at least 300 labelled prompts across the 9 classes.
  Generate realistic refinery-domain prompts; read .agents/skills/swaraj-domain/SKILL.md
  so they sound like real tasks, not generic ones.

DONE WHEN:
- test_router_accuracy asserts >= 0.95 and passes
- Routing overhead is under 50ms p95

VERIFY BY: the test output and the measured latency.
```

### P3.3 — Routing badge and GPU bar

```
GOAL: Make routing visible. This is a trust feature, not debug output.

READ FIRST: docs/UI-SPEC.md

BUILD:
- Routing badge on every agent response, all monospace, 11px:
  "● devstral-2-22b · code_generate · 0.98 · 28ms"
- Click opens a 420px popover: feature vector, then one row per candidate model
  with quality prior, VRAM fit, latency estimate, swap cost, total. Winner has a
  sovereign left border. Losers show a terse reason: "context too short",
  "capability missing: vision", "not resident, swap cost 6.1s".
- GPU allocation bar, 28px stacked, model tints, sleeping models hatched at 35%
  opacity, free space bordered. Reallocates over 400ms during a swap with a glow
  on the waking segment.
- Model swaps get their own trace row: "waking qwen3-coder… 4.2s" with a live timer.

DONE WHEN: two different task types in one session route to different models,
the badge changes, and the GPU bar visibly reallocates.

VERIFY BY: screen recording of the swap.
```

### P3.4 — Bench harness

```
GOAL: Measured priors, never copied from a leaderboard.

BUILD:
- eval/bench.py — ~200 domain tasks with programmatic graders across the task
  classes. Writes priors into models.yaml.
- `make bench MODEL=<tag>` benchmarks one model.
- A scorecard view: grouped bars per model per task class, stamped
  "measured on <gpu> · <date> · eval suite v1".

DONE WHEN: `make bench` populates priors and the router uses them.
```

---

# Milestone 4 — Sandbox and code execution

### P4.1 — Sandbox runner

```
GOAL: Network-isolated execution, tiered by operator setting.

READ FIRST: docs/SECURITY.md, .agents/rules/30-rust.md

BUILD:
- Rust sandbox launcher. Default tier: bubblewrap with --unshare-net
  --unshare-pid --die-with-parent, read-only rootfs, workspace bind at /work,
  cgroups v2 caps, 60s wall clock.
- Optional tiers: rootless container, gVisor, Firecracker — configurable.
- Pre-baked environment: numpy, pandas, scipy, openpyxl, matplotlib.
  NO pip at runtime.
- Artefacts leave by copy-out of declared paths only.

DONE WHEN:
- `ip addr` inside the sandbox shows loopback only
- `curl https://pypi.org` fails because there is no interface
- A runaway loop is killed at the wall clock limit

VERIFY BY: paste all three outputs.
```

### P4.2 — code_exec and the verifier loop

```
/new-tool
```
```
Implement code_exec: runs Python in the sandbox, streams stdout/stderr to the
terminal pane, returns structured results.

Then wire the verifier loop: for code tasks, the agent writes code plus tests,
runs them, reads failures, repairs, re-runs. Maximum 3 iterations before
surfacing to the human.

DONE WHEN: ask for a function with tests, watch one test fail, watch the agent
repair it and re-run to green — all visible in the trace and terminal.

VERIFY BY: screen recording of the fix-and-rerun cycle.
```

---

# Milestone 5 — Documents and knowledge

### P5.1 — Ingest pipeline

```
GOAL: Scanned and born-digital document ingest with provenance.

READ FIRST: docs/ARCHITECTURE.md §1 (multimodal notes), .agents/skills/swaraj-domain/SKILL.md

BUILD:
- Classify born-digital vs scanned by text-layer heuristic
- Preprocess: deskew, denoise, adaptive binarise, upscale to 300dpi (OpenCV)
- Layout detection with region typing: text, table, formula, figure, handwriting, stamp
- Region routing: dedicated OCR engine for text; vision model for handwriting and
  complex regions. Do NOT route a scanned report to a vision model alone and treat
  the output as ground truth — the combination beats either alone.
- Every extracted field carries: value, unit, confidence, page, bbox, extractor

DONE WHEN: a scanned PDF produces a structured field list where every field has
a bounding box and a confidence.

VERIFY BY: the JSON output for one real scanned page.
```

### P5.2 — Provenance viewer

```
GOAL: The signature interaction — click a field, see the exact pixels it came from.

READ FIRST: docs/UI-SPEC.md (Provenance viewer)

BUILD:
- Split 50/50, synchronised. Left: page canvas with bbox overlays colour-coded by
  confidence state. Right: field table.
- Click a field → canvas scrolls, zooms to the bbox with 40px padding, pulses
  exactly twice, holds the highlight.
- Click a bbox → the field scrolls into view and flashes.
- Both stay linked while selected. j/k navigates fields with the canvas following.
- Pre-render adjacent pages so there is NO loading state between click and highlight.
- Verify flow: inline edit, then a "verified by <user> · <time>" stamp, confidence
  becomes 1.00, the bbox turns sovereign green.

DONE WHEN: the interaction is instant and precise in both directions.

VERIFY BY: screen recording. This is the moment that sells the product — make it fast.
```

### P5.3 — Knowledge base

```
GOAL: Hybrid retrieval with citations and permission filtering.

BUILD:
- Layout-aware chunking, ~500 tokens, with the heading path prefixed into the
  chunk text ("SOP-114 › Section 4 › 4.2 Acceptance Criteria › <body>").
  Tables chunked whole with their caption.
- SQLite: FTS5 for keyword, sqlite-vec for dense. RRF fusion, then cross-encoder
  rerank. Hybrid is not optional — dense-only fails on equipment tags and clause
  numbers, which is exactly what this domain runs on.
- Every chunk row carries classification, dept, allowed_roles, effective_date,
  superseded_by. Filter by role IN THE QUERY, before rows are returned.
- Superseded revisions excluded by default, labelled when deliberately shown.
- Citations click through to the source region.

DONE WHEN:
- A query returns cited results, and the same query as a different role returns
  a filtered set
- An ungroundable question returns "not found in the knowledge base" rather than
  a fluent guess

VERIFY BY: the two-role comparison, side by side.
```

---

# Milestone 6 — Deliverables

### P6.1 — Renderers

```
GOAL: Real files from validated JSON. The model never emits bytes.

READ FIRST: .agents/skills/swaraj-domain/SKILL.md (approval note structure)

BUILD:
- JSON Schema per deliverable type: approval note, inspection summary, review deck,
  cost sheet, engineering calculation
- Model emits schema-validated JSON via `format`; deterministic renderers produce
  the file: docxtpl, python-pptx, openpyxl
- Templates load from a user-managed folder — every PSU mandates its own note
  format, and a tool that cannot honour it does not get adopted
- Spreadsheet formulas stay live, not flattened to values
- Provenance footer on every file: models used, run id, sources, min confidence,
  fields human-verified, "DRAFT — requires approval by competent authority"

DONE WHEN: a generated DOCX opens in Word with correct letterhead, structure,
citations and footer.

VERIFY BY: attach the generated file.
```

### P6.2 — Calculation engine

```
GOAL: Calculations executed as code, never generated as text.

BUILD:
- The model writes a Python function with explicit units and inline assertions
- code_exec runs it in the sandbox
- An independent recompute (different formulation or a dimensional check) verifies it
- The renderer emits the derivation table: given values with sources, the governing
  clause quoted FROM THE KNOWLEDGE BASE with a citation, formula, substitution,
  intermediate results, final answer with units

DONE WHEN: a remaining-life calculation appears in a DOCX with every step shown
and the governing standard cited from the KB, not from model memory.

VERIFY BY: the rendered derivation.
```

### P6.3 — Review and approve

```
GOAL: The maker-checker gate.

READ FIRST: docs/UI-SPEC.md (Review & approve), .agents/skills/swaraj-domain/SKILL.md

BUILD:
- Deliverable preview on a white page with letterhead at true proportions, in
  light mode regardless of app theme
- Evidence panel: citations, fields with confidence, provenance
- Action bar: maker/checker identity chips; Reject with reason / Edit & approve /
  Approve, with a 24px gap before Approve
- BLOCKING banner when preconditions fail: "Cannot approve: 2 fields unverified ·
  1 claim without citation" with a jump link. Approve disabled AND the banner
  explains why — never a silently dead button.
- Rejection requires a reason; it enters the audit record
- Show the exact approval stamp before confirming

DONE WHEN: approval is impossible while a flagged field is unverified, and the
approved file carries both identities.

VERIFY BY: screenshots of the blocked state and the approved state.
```

**At this point journey J1 works end to end. That is your demo.** Time it — the target is under 90 seconds.

---

# Milestone 7 — Vision and P&ID

### P7.1 — Symbol detection

```
GOAL: P&ID symbol detection and instrument-tag extraction.

BUILD:
- Fine-tune RF-DETR Small on a public P&ID symbol dataset (~3,800 annotated
  diagrams, 11 classes). Report real mAP@50 on a held-out split.
- Filter detections to text-bearing classes (instrument tag, instrument DCS) —
  do not waste OCR on every valve glyph
- Crop with padding from the ORIGINAL image, never the annotated overlay
- OCR each crop; validate against a tag regex and the equipment register
- Unreadable regions emitted explicitly as "unreadable", never silently dropped
- Output: annotated overlay, symbol inventory by class, tag list with confidence,
  reconciliation table against the register

DONE WHEN: a scanned P&ID produces the overlay plus a reconciliation table
showing at least one discrepancy.

BE HONEST IN THE UI: this does not reconstruct drawing logic — no line tracing,
no control-loop validation. State that where the user can see it.

VERIFY BY: screenshot of the overlay and the reconciliation table.
```

---

# Milestone 8 — Hardening

### P8.1 — Audit chain

```
GOAL: Tamper-evident audit.

BUILD:
- Append-only records, hash-chained: each record embeds the previous record's hash
- Contents: run id, user, prompt, plan, every step, documents retrieved with
  classification, models used, deliverables, approval event with identity and edits
- Chain verification as a first-class UI action
- DESIGN THE FAILURE STATE FIRST: on a break, the header turns critical and names
  the exact record index where verification failed. A tamper-evident log whose UI
  cannot show tampering is pointless.
- Exports are themselves audited

DONE WHEN: manually corrupting one record makes verification fail and name it.

VERIFY BY: do exactly that and screenshot the result.
```

### P8.2 — Attestation and metrics

```
GOAL: The evidence bundle and the numbers you quote on stage.

BUILD:
- `--offline-attest`: signed report with interface inventory, routing table,
  active ruleset, session egress log, SHA-256 of every loaded model
- Metrics view: routing accuracy with sample size and date, route latency p95,
  swap time, OCR field accuracy, tag accuracy, end-to-end task time, egress count
- Always state sample size and measurement date next to an accuracy figure. An
  unqualified percentage invites exactly the question you do not want.

DONE WHEN: the attestation report generates and the metrics view shows real
measured numbers, not placeholders.
```

### P8.3 — Final gates

```
/milestone-check
```
```
/sovereignty-audit
```
```
Run the thermo-nuclear code quality review on this codebase.

Note: our file-size limit is 400 lines, not the default 1,000. Our architecture
boundaries are in .agents/rules/10-architecture-boundaries.md — flag any violation
of the ownership map or the single-writer rule as critical.
```

---

## Prompts you will need repeatedly

**When it drifts on design**
```
Re-read .agents/rules/50-design-lock.md. Check the current screen against the
three locked properties: 13px base font, 4px radii, monospace on every
machine-produced value. Report each as pass or fail with a screenshot, then fix
whatever failed. Do not change anything else.
```

**When something "works" but you doubt it**
```
Show me this working end to end with evidence, not a description. If any part is
mocked, stubbed, or not wired to the real core, say so explicitly and list which
parts. Do not describe a partially-working feature as complete.
```

**When a file has grown**
```
This file is over 400 lines. Decompose it along its actual responsibilities —
not into a utils file. Propose the split before making it, and state what each
new module owns.
```

**Before any demo**
```
/sovereignty-audit
```

**When you catch the same mistake a third time**
```
I have now corrected this three times: <describe it>. Add a rule to
.agents/rules/ that prevents it, with a bad example and a good example. Choose
the right activation mode and tell me why. Keep it under 300 words.
```

That last one is how this system compounds instead of decaying.
