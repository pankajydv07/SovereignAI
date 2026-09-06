# AGENTS.md — SWARAJ

**Read this before writing any code. It overrides your defaults.**

This file loads on every session, so it is deliberately short. Detailed standards live in `.agents/rules/`, which load only when relevant:

| File | Loads when |
|---|---|
| `00-sovereignty.md` | Always — the air-gap invariants |
| `10-architecture-boundaries.md` | Always — who owns what |
| `20-python.md` | Touching `core/**/*.py` |
| `30-rust.md` | Touching `src-tauri/**/*.rs` |
| `40-typescript-react.md` | Touching `apps/desktop/src/**` |
| `50-design-lock.md` | Always — the visual system |
| `60-testing.md` | When tests or "is it done?" are in play |
| `70-local-models.md` | Anything touching Ollama, routing or prompts |

Also read: `PRD.md` (requirements), `docs/ARCHITECTURE.md` (design), `docs/GLOSSARY.md` (domain vocabulary you do not natively know).

---

## What this is

An **air-gapped desktop agentic AI workbench** for confidential industrial work — refineries, PSUs, defence units. Runs entirely on-premise against local Ollama. Claude-Code-grade interaction: project folders, chat sessions, tool calls with approval, a real terminal, diff review, MCP.

**It is not a general-purpose IDE.** No language servers, no debugger, no refactoring engine, no git GUI, no extension marketplace. Every addition must trace to a PRD requirement ID. Do not invent requirements.

---

## Seven invariants

Violating any of these is a build-breaking defect, regardless of whether tests pass.

1. **No network egress.** Only `127.0.0.1:11434`. No CDN links, no telemetry, no update checks.
2. **The agent core opens no listening socket.** Rust ↔ Python is JSON-RPC over stdio.
3. **Roles, never model names.** A model tag appears only in `models.yaml`.
4. **The model never produces bytes or arithmetic.** It emits schema-validated JSON; deterministic Python renders files; calculations run as sandboxed code with assertions.
5. **No business logic in the UI.** The frontend renders state and dispatches intents.
6. **Every tool is typed and classified** — input schema, output schema, side-effect class, timeout.
7. **Filesystem access is workspace-scoped**, verified before use. Traversal is a security defect.

---

## The anti-slop list

These are the specific failure modes of AI-written code. Each is shown as bad → good.

### Emoji, ever

❌ `console.log("✅ Session created!")` · `# 🚀 Fast path`
✅ `log.info("session_created", session_id=sid)`

Not in code, UI strings, logs, comments, or commit messages.

### Marketing tone in UI copy

❌ `"Oops! Something went wrong 😅 Let's try that again!"`
✅ `"Model unavailable: qwen3-coder:30b needs 4.1 GB more VRAM."`

Users are professionals. No exclamation marks, no encouragement, no "Let's get started".

### Comments that restate the code

❌
```python
# increment the retry counter
retries += 1
```
✅
```python
# Local models frequently emit a stringified number for an int field.
# One repair round with the validation error in context fixes most of these.
retries += 1
```

Comment *why*, never *what*.

### God files and junk-drawer names

❌ `utils.py`, `helpers.ts`, `misc.rs`, `common/index.ts`, a 900-line `agent.py`
✅ `core/context/compaction.py`, `core/tools/fs_read.py`

Any file over 400 lines gets decomposed before merge. Put the function where it belongs.

### Mock data in non-test code

❌
```tsx
const sessions = [
  { id: "1", title: "Sample session" },   // TODO: wire to real API
];
```
✅ Wire it to the core, or do not build the component yet.

A feature not connected to the real core is not done. Half-built features score zero, not half.

### Silent fallbacks

❌
```python
model = registry.get(requested) or registry.get("llama3")   # fall back to something
```
✅
```python
model = registry.resolve(role)
if model is None:
    raise NoModelForRoleError(role, available=registry.installed_tags())
```

Never substitute a different model, path or resource because the requested one was missing. Fail loudly and name what was absent.

### Broad exception handling

❌
```python
try:
    return await self._run_step(step)
except Exception:
    return StepResult.failed("something went wrong")
```
✅
```python
try:
    return await self._run_step(step)
except ToolTimeout as exc:
    return StepResult.timed_out(step, exc.timeout_s)
except ValidationError as exc:
    return await self._repair(step, exc)
```

Catch the specific exception at the specific line that raises it.

### Defensive chains that hide bugs

❌
```python
def render(note):
    if not note: return
    if not note.sections: return
    if not note.sections[0]: return
    ...
```
✅ Model it in the type. If a note without sections is invalid, `ApprovalNote` should not be constructible without them.

### Dead abstractions

❌ An interface with one implementation "for future flexibility". A factory constructing one class. An event bus with one subscriber. A `BaseRenderer` with only `DocxRenderer`.
✅ Add the abstraction when the second case actually exists.

### Re-implementing a dependency's job

❌ A custom terminal emulator, a hand-rolled PDF parser, a bespoke diff algorithm.
✅ `xterm.js`, `PyMuPDF`, an existing diff library.

### `sleep()` as synchronisation

❌ `time.sleep(2)  # wait for the model to load`
✅ `await self._wait_until_loaded(model, timeout_s=90)`

### Duplicated logic across processes

If Rust and Python both know how to resolve a workspace path, one of them is wrong. One implementation, one owner.

---

## Requires justification in the PR

Any new dependency (state licence, size, why the stdlib is insufficient) · any `# type: ignore`, `any`, `as`, `unwrap()`, `clippy::allow` · any file over 300 lines · any function over 50 lines or 5 parameters · any new cross-process message.

---

## Git

Conventional commits, scoped by package: `feat(router): add capability matching`. One logical change per PR. PR description states the PRD requirement ID, what was tested, and what was deliberately left out. Never commit generated files as manual edits, secrets, model weights, or `node_modules`. CI green — never merge with a skipped test.

---

## When you are unsure

**Stop and ask.** Specifically when: the PRD does not cover it · two requirements conflict · you would need to break an invariant · you do not know which process should own the logic · you cannot confirm a dependency's licence · you are about to add a fallback because something was unavailable.

"This isn't specified — here are two options and the tradeoff" beats a confident wrong implementation every time. In this codebase a plausible guess survives review and fails on stage.
