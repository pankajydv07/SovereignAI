# SWARAJ

**Sovereign Workbench for AI-assisted Reasoning, Analysis & Judgement**

An air-gapped, on-premise agentic AI desktop application for confidential industrial knowledge work — refineries, PSUs, defence-linked manufacturing units and government offices.

Nothing leaves the machine. It is built to prove that, not merely claim it.

---

## Read these first

| If you are… | Read |
|---|---|
| An AI agent about to write code | **`AGENTS.md`**, then `GEMINI.md` |
| Deciding what to build | `PRD.md` |
| Deciding how to build it | `docs/ARCHITECTURE.md` |
| Wondering why a choice was made | `docs/DECISION-LOG.md` |
| Building UI | `docs/UI-SPEC.md` + `.agents/rules/50-design-lock.md` |
| Confused by domain vocabulary | `docs/GLOSSARY.md` |
| Driving this build with AI skills | `docs/AI-WORKFLOW.md` |

---

## What it does

- **Multi-model, auto-selected.** Routes each task to the right locally-installed model. Adding a model is `ollama pull` plus one line of YAML — no code change.
- **Genuinely agentic.** Plans multi-step work, calls local tools, iterates on failure, pauses for human approval at every consequential step.
- **Multimodal.** Scanned PDFs, handwritten notes, engineering drawings, photographs — processed on-device, with confidence and bounding-box provenance on every extracted value.
- **Real deliverables.** DOCX, PPTX, XLSX, working code, calculations with derivation shown. Not chat replies.
- **Grounded.** Hybrid retrieval over the organisation's own manuals, SOPs and correspondence, with permission filtering enforced in the data layer.
- **Provably sovereign.** Four layers of egress denial, a kernel-level monitor, and an attestation report for your security auditor.

---

## Stack

Tauri 2 · Rust (PTY, filesystem, processes, sandbox) · Python 3.12 agent core over stdio JSON-RPC · React + TypeScript + Vite + Tailwind · xterm.js · CodeMirror 6 · SQLite + sqlite-vec + FTS5 · Ollama.

The agent core **opens no listening socket**. `ss -lntp` shows it listening on nothing.

---

## Repository layout

```
swaraj/
├─ AGENTS.md              cross-tool engineering constitution
├─ GEMINI.md              Antigravity-specific overrides (takes precedence)
├─ PRD.md                 requirements
├─ models.yaml            THE ONLY file that names a model
├─ .agents/
│  ├─ rules/              activation-scoped rules (always-on, glob, model-decision)
│  ├─ workflows/          /new-tool /new-model /new-screen /protocol-change
│  │                      /milestone-check /sovereignty-audit
│  ├─ skills/             swaraj-domain
│  └─ mcp_config.json     stdio transports only
├─ docs/                  ARCHITECTURE · DECISION-LOG · UI-SPEC · SECURITY
│                         TESTING · GLOSSARY · AI-WORKFLOW
├─ packages/protocol/     JSON Schema → Pydantic + serde + Zod (generated)
├─ apps/desktop/          Tauri app: src/ (React) + src-tauri/ (Rust)
├─ core/                  Python agent core
├─ eval/                  routing test set, graders, bench harness
└─ templates/             org letterhead and note formats
```

---

## Prerequisites

Rust stable · Node 20+ with pnpm · Python 3.12 · Ollama running locally · Linux: `bubblewrap` for sandboxing.

## Getting started

```bash
make setup       # install dependencies
make protocol    # generate cross-language types
make dev         # run the app in development
make test        # full test suite
make demo        # one-command bring-up on a clean machine
```

---

## Non-goals

This is **not a general-purpose IDE**. No language servers, no debugger, no refactoring engine, no git GUI, no extension marketplace. We borrow the interaction patterns of modern coding agents; we do not rebuild their surface area. See `PRD.md` §3.2 — it is the most valuable page in the repository.

## Licence

All dependencies and model weights must be permissively licensed. Model licences are surfaced in the UI; non-commercial weights are marked undeployable.



(.venv) PS C:\Users\PREDATOR\OneDrive\Desktop\sih_app\SovereignAI\apps\desktop> $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"                                                  
>> pnpm tauri dev                                                                                                                                                                    