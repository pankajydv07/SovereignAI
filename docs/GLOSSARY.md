# Glossary

Domain and technical vocabulary used across this repo. If you are an AI agent working here, read this before generating any document or naming any concept — several of these terms mean something specific and non-obvious.

## Domain — industrial / PSU

| Term | Meaning |
|---|---|
| **PSU** | Public Sector Undertaking — a government-owned Indian corporation. MRPL is one. |
| **MRPL** | Mangalore Refinery and Petrochemicals Limited — the problem statement owner. |
| **Approval note** | Formal internal document seeking sanction from a competent authority. The core deliverable. |
| **Competent authority** | The officer empowered to approve a given class of decision. Varies by value and subject. |
| **Maker–checker** | Two-person accountability: one prepares, another verifies and signs. Non-negotiable in PSU workflow. |
| **Inspection report** | Field record of equipment condition — often a scan of a handwritten form. |
| **NCR** | Non-Conformance Report — a recorded deviation from specification. |
| **P&ID** | Piping and Instrumentation Diagram. Schematic of equipment, piping, valves and instruments. Highly confidential. |
| **Instrument tag** | Identifier like `FT-1702` — letters denote function, digits the loop. ISA-style convention. |
| **Equipment register** | Authoritative asset list with tags, specifications and inspection history. |
| **SOP** | Standard Operating Procedure. Revision-controlled; superseded revisions must never be cited as current. |
| **Thickness survey** | Ultrasonic measurements of pipe or vessel wall thickness, used to compute remaining life. |
| **Retirement limit** | Minimum acceptable wall thickness before an asset must be replaced. |
| **Remaining life** | Projected service life from corrosion rate and current thickness. |
| **Hydro test** | Pressure test with water to verify integrity. |
| **IS / ASME / API / OISD** | Indian Standards / American Society of Mechanical Engineers / American Petroleum Institute / Oil Industry Safety Directorate — the governing standards bodies. |
| **Air gap** | Physical isolation from external networks. The organisational control this product must respect and prove. |
| **Shutdown** | Planned plant outage for maintenance. Discrepancies found here are expensive. |

## Product

| Term | Meaning |
|---|---|
| **SWARAJ** | This product. Sovereign Workbench for AI-assisted Reasoning, Analysis & Judgement. |
| **Project** | An opened folder plus its knowledge base and settings. |
| **Session** | A persistent conversation within a project, with full history and replay. |
| **Run** | One task execution within a session — a plan and its steps. |
| **Step** | A single tool call plus its observation, checkpointed. |
| **Deliverable** | A real output file (DOCX / PPTX / XLSX), not a chat reply. |
| **Artifact registry** | The UI surface listing everything a session produced. |
| **Provenance** | For any extracted value: its confidence, page and bounding box on the source. |
| **Confidence floor** | Threshold (default 0.85) below which a field must be human-verified before use. |
| **Approval gate** | The point where a run pauses for a human checker. |
| **Sovereignty monitor** | The live panel proving zero external egress. |
| **Attestation report** | Signed evidence bundle for a security auditor. |
| **Audit chain** | Hash-chained append-only record; each entry embeds the previous entry's hash. |

## Technical

| Term | Meaning |
|---|---|
| **Role** | A logical model slot (`planner`, `coder`, `writer`, `vision`, `embedder`, `classifier`). Code references roles, never model names. |
| **Model registry** | Auto-discovers installed Ollama models via `/api/tags` and `/api/show`, merged with `models.yaml`. |
| **Router** | Classifies a task, resolves a role, picks a model, sets residency. |
| **Priors** | Measured per-model quality per task class, produced by the local bench harness. Never copied from a leaderboard. |
| **Residency** | Which models are currently loaded in VRAM, managed via `keep_alive`. |
| **`keep_alive`** | Ollama parameter controlling how long a model stays in memory. `0` unloads immediately. |
| **`num_ctx`** | Ollama context length. Multiplied by parallelism, this is VRAM — treat it as a physical resource. |
| **Tool-call repair** | Re-prompting with the schema validation error when a local model emits malformed arguments. |
| **Compaction** | Summarising older conversation turns to stay inside the context budget. |
| **ACP** | Agent Client Protocol — the open JSON-RPC-over-stdio standard whose message shapes we adopt. |
| **MCP** | Model Context Protocol — how third-party tool servers plug in. Stdio transport only here. |
| **Sidecar** | The Python agent core, spawned and supervised by the Rust layer. |
| **PTY** | Pseudo-terminal. Gives the embedded terminal real shell behaviour. |
| **bubblewrap / `bwrap`** | Lightweight Linux sandbox. `--unshare-net` removes the network interface entirely. |
| **Side-effect class** | A tool's declared nature: `read`, `write` or `exec`. |
| **AUTO / ASK / DENY** | The policy engine's decision for a given tool call. |
| **Turbo comment** | `// turbo` above a command in an Antigravity workflow, letting it run without approval. |
