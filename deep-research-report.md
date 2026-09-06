# Executive Summary

We propose building the sovereign agentic workbench as a **desktop application** using a web-technology stack with a lightweight Rust backend (e.g. [Tauri](https://v2.tauri.app/){target=_blank}). This gives a cross‑platform shell that can host React/TypeScript UIs (Monaco editor, xterm.js, etc) with minimal footprint. The core is a **multi-layer architecture**: a **Presentation Layer** (UI), a **Workbench API** layer, an **Agent Runtime**, a **Capability/Tool layer (via MCP)**, and a **Data/Infra layer** (DB, models, files). Each layer has a clear contract, enabling replayable, event‑driven sessions. For example, the UI opens a “project” and “session” context and streams events (agent messages, tool outputs, file events) over WebSockets/SSE. The agent runtime (using something like LangGraph) runs a loop: plan → invoke model → call tools → observe output → repeat. All code execution happens in a secure sandbox (e.g. rootless container or microVM) under a **deterministic policy engine** that enforces approvals and RBAC. 

Key decisions: 

- **UI/UX**: Project/session-centric (not a “how can I help?” chat). We show a project explorer, session tabs, and in-session panels: chat/plan, tool logs, file editor (Monaco), artifact preview, and an embedded terminal (xterm.js). Agents append to a session transcript rather than start afresh, and emit structured events. The UI handles events like `agent.plan`, `tool.request`, `tool.stdout`, etc., rendering chat bubbles, terminal output, and preview artifacts in real-time. 
- **Agent orchestration**: Use a lightweight orchestration framework (e.g. LangGraph) instead of a giant prompt. LangGraph provides durable, streaming, human‑in‑loop workflows, mixing deterministic code with LLM steps. For example, Claude Code’s architecture employs a simple model–tool loop, surrounded by a **permission system**, **context memory**, **MCP extensions**, and append-only logs. We adopt these best practices: explicit per-action permissions (with approval UI), append‑only transcripts, and hierarchical context (global “AGENTS.md”, project instructions, session history, retrieved knowledge). 
- **Local models**: We run inference locally (Ollama or similar). Ollama provides a local HTTP API (default `http://localhost:11434/api`) to serve open models. We build a **Model Gateway** to swap providers (Ollama, vLLM, llama.cpp, etc.) per task. This satisfies “multi-model” and “open weights” requirements, while the UI can show which model is used.
- **Tools via MCP**: We expose “tools” (filesystem, terminal, custom scripts, knowledge search) through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io){target=_blank}. MCP is an open standard (like a “USB‑C port for AI”) that lets the agent call, for example, a `read_file` or `search_docs` tool. By implementing an MCP server, any new capability plugs in easily. The UI shows tool requests and outputs as part of the session transcript, and also prompts the user for approval if needed. 
- **Search/RAG**: We ingest all relevant docs (PDFs, scans, emails, images). A pipeline (e.g. using Tesseract or PaddleOCR for scanned pages, plus PDF parsers) extracts text, tables, images. We chunk text and index it in PostgreSQL: use ParadeDB (BM25) for keyword search and pgvector for embeddings. Queries fuse BM25+vector (RRF or similar) to get both precise and semantic matches. This hybrid retrieval is entirely in Postgres, requiring no external vector DB.  
- **Security/isolation**: Every code execution happens in a sandbox. For example, spawn a rootless Linux container or gVisor per session; more strictly, use a lightweight VM (Firecracker/Kata) under controlled resource limits. Each tool call is checked by a **policy engine**: certain commands auto-approve (e.g. `read_file`), others require user consent (`sudo`, `pip install`), and dangerous operations (network access, deleting home) are denied. The results and logs are recorded. We provide an on-screen network audit (“0 external calls, 0 blocked”) to prove full offline operation. 
- **Observability**: All actions are logged as structured events (JSON). For example, a plan step, a tool invocation or approval, file writes, and the final artifact creation all generate events. The UI can replay or audit a session from these logs. By design there is an **append-only transcript** that cannot be modified by the agent (auditability over convenience). We also log the policy decisions and resource usage.  

This report details requirements, design, and implementation guidance. We assume the platform targets Linux/macOS/Windows desktops (no mobile for now), with ~4–8 devs over several months. The threat model is internal/offline use (no untrusted internet content), but with strong requirements for data privacy, auditable actions, and post-hoc review. Any team can adapt these ideas by plugging in their choice of local LLMs, sandbox tech, and business rules.

 *Figure: Conceptual architecture of an agentic workbench – the user UI (left) connects via a local API to the agent runtime and tool/sandbox layer (right). This diagram is illustrative (source: NVIDIA Secure Agent Workspace design).*

## Product Requirements

From the request and security context, the workbench must: 

- **Project/Session focus:** The user organizes work into Projects and Sessions (like Claude Code). A Project has a knowledge base (files, instructions) and multiple Sessions for tasks. 
- **Polished IDE-like UI:** Code editor (Monaco for .py, .md), integrated terminal (xterm.js), file explorer, artifact viewer. The look/feel should match modern IDEs (no chattiness or casual tone).
- **Agentic Loop:** The system should run autonomous agents that plan and execute tasks. The agent must maintain context (AGENTS.md, code, conversation, retrieval results) and refine output iteratively. 
- **Tool Usage & Permissions:** The agent can call tools (shell, file I/O, search, document gen). Each tool invocation is mediated by a policy: some auto-run, others need user approval with a clear UI dialog.  
- **Safety & Audit:** All agent actions must be logged. Users must see agent “thoughts” and ask for approval before sensitive actions. The system runs entirely **on-device**: no external model API calls or data leaks. A visible network-audit panel should show “External calls: 0”.  
- **Local Models:** Support for open LLMs via an on-device server (e.g. Ollama). Allow multiple models (e.g. one for coding, one for vision) with automatic selection. 
- **Knowledge Base:** Ability to ingest and query documents locally. Support scanned PDFs, images, tables. Provide search over past correspondence, manuals, SOPs, etc., using local indexing.  
- **Artifact Generation:** The agent should produce actual deliverables: code files, .docx/.xlsx/.pptx reports, PDFs, images, etc. The UI must list and preview these artifacts. 
- **Event-driven UI:** Under the hood, the backend emits a stream of events (agent message, tool output, file change). The frontend renders them in real-time (chat view, terminal output, file explorer, artifact preview). 
- **Session Replay:** The entire session history (requests, events, tool actions, files) must be saved so that it can be replayed or audited later.
- **Offline/Offline installation:** All components (UI, models, tools) run offline. Installable via offline bundles/installers for Windows, macOS, Linux (Tauri supports AppImage, DMG, MSI, Snap, etc). 
- **Compliance:** Output should be verifiable. E.g. if generating code, the agent must run tests in a sandbox and show results. For documents, the agent might cite relevant SOP sections. The design should enable review (e.g. agent plan steps listed, verification checks).

## User Journeys

1. **Project Setup:** The user creates or opens a Project (directory). They see a “Projects” list. Choosing a project shows existing Sessions. They click “New Session” and enter a prompt/task.  
2. **Running a Session:** The UI splits into panes: a chat/planning area (agent’s reasoning), a terminal, and a file/preview pane. The user asks, “Analyze report.pdf and draft an approval note.” The agent responds with a plan (e.g. read file, OCR pages, search SOPs, write note). Each step appears as “agent plan” list.  
3. **Tool Execution:** For each step, the agent invokes a tool. E.g. `read_file("report.pdf")` → UI shows “Tool: read_file → ... (contents)”. For a shell command, a modal asks “Agent wants to run: `python ocr.py report.pdf` – Approve?” [Allow/Deny]. Upon approval, output streams in the xterm pane.  
4. **Artifact Generation:** When ready, the agent creates files (approval_note.docx, findings.xlsx). The “Artifacts” pane lists them. Clicking an artifact shows an inline preview (e.g. embedded Word/PDF viewer, or image). All file changes update live in the file explorer.  
5. **Review & Output:** The user inspects the drafts. The agent might have also run verification (e.g. spellcheck, format). The UI highlights “Verification passed: all sections present”. Network panel shows no external requests. The user closes the session, now seeing a summary. They can re-open it to see all logs.  

Throughout, the UI feels like a desktop IDE (keyboard shortcuts, split views, theming). Key UX elements: a **threaded chat view with markdown** (to show plans and code snippets), an interactive **terminal**, a **code editor** (Monaco) for any file edits, and an **artifact panel** showing generated outputs. Every message (user or agent) is a discrete block, not a free-form chat.

## UX Patterns

- **Project/Session Sidebar:** A navigation pane listing Projects and Sessions. Users switch contexts here.  
- **Session Workspace:** Inside a session, top area is a *chat timeline*: messages (user prompt, agent plan, agent outputs) appear sequentially. Each message can have attachments (code blocks, images).   
- **Agent Plan Pane:** Often agents present a checklist/plan before execution. We reserve a small panel to show the plan/tasks (e.g. “1. Read PDF ✓, 2. OCR ✓, 3. Search SOP...”).  
- **File Explorer & Preview:** A pane shows the project directory. Double-click opens files in editor or preview. When the agent creates a new file, it appears here (artifact). We can show a “Preview Panel” (like in ADE) for images/PDF/MD.  
- **Terminal Pane:** xterm.js gives a real terminal. It supports tabs, splits, and persistent sessions. The agent can run commands; output appears here. Users can also manually enter commands if needed.  
- **Approval Dialogs:** When agent requests an action (e.g. shell command, network request), show a dialog listing the action and options [Allow | Deny]. Log the decision as an event. The user must explicitly consent to non-ordinary operations.  
- **Artifact Registry:** A sidebar “Artifacts” lists all generated files (with timestamp, type). Icons indicate type (docx, pdf, code). Clicking shows inline preview (WYSIWYG for docs, image viewer, or code diff).  
- **Context Panel:** Optional side panel showing current context: open files, retrieved knowledge snippets, relevant AGENTS.md instructions. The agent can retrieve context (e.g. relevant SOP sections) and we display these under “Context”.

These UX elements match modern agent IDE references. For example, the open-source **ADE (Agentic Development Environment)** uses Tauri + React + xterm.js and provides terminal tabs, scratchpad prompts, live preview, and an agent dashboard. We would mimic its clean, keyboard-friendly style but tailor it to secured workflows (strict approval prompts, no whimsical features).

## Event-driven Frontend/Backend Contracts

We design the backend as an **event producer** and the frontend as a **subscriber**. All state changes and agent actions are emitted as events over a WebSocket or Server-Sent Events (SSE) stream. Example event types (JSON):

- `session.created` – new session started.  
- `user.prompt` – user message.  
- `agent.plan` – agent has created/updated its plan list.  
- `agent.message` – agent’s chat message (with possible markdown).  
- `tool.request` – agent requests a tool (includes tool name, args).  
- `tool.stdout/tool.stderr` – streaming output lines from tools (for terminal).  
- `tool.exit` – tool finished with code.  
- `file.created/modified/deleted` – file events.  
- `artifact.created` – an output file designated as artifact.  
- `approval.required` – UI must show an approval dialog (contains action details).  
- `network.status` – updates on allowed/blocked network calls.  
- `agent.completed` – agent finishes the task.  

On the front end, different components subscribe to relevant events. For example, `agent.message` and `agent.plan` feed the chat/plan view, `tool.stdout` appends lines to the terminal, `file.created` refreshes the file tree and triggers preview, and `approval.required` pops up a dialog. This separation (publish-subscribe) **decouples** the UI: we do not simply render LLM text, but handle each event type specifically. It also enables **session replay**: the entire event log can reconstruct the UI state if reloaded.

Example JSON snippet for an event stream:

```json
{ "type": "tool_request", "tool": "filesystem.write_file", "args": {"path":"README.md","content":"# Hello"} }
```
```json
{ "type": "tool_response", "tool": "terminal", "stdout": "running tests...\nAll passed", "exitCode": 0 }
```
The API could use WebSocket/SSE. For instance, the frontend might send the user prompt via REST, then open a WebSocket to receive the live stream of events.

## System Architecture

We follow a **layered architecture**:

```mermaid
flowchart TB
    subgraph "Desktop Application (Tauri)"
      UI[User Interface (React + Monaco + xterm.js)] 
      UI -->|API calls/WebSocket| BackendAPI[(Backend API Server)]
    end
    
    subgraph "Agent Runtime & Tools"
      BackendAPI --> AgentRuntime[Agent Orchestration (LangGraph)]
      AgentRuntime --> ToolRouter[Tool Dispatcher (MCP Router)]
      ToolRouter --> LocalTools[Local Tools (filesystem, subprocess, RAG search, OCR, doc gen)]
      ToolRouter --> MCPServices[MCP Servers (Knowledge DB, calculators, SOP search)]
      LocalTools --> Sandbox[Sandbox (Container/VM)]
    end

    subgraph "Infrastructure"
      Sandbox --- OS[OS kernel & resources]
      BackendAPI --> ModelGateway[(LLM Model API (Ollama/vLLM))] 
      ModelGateway --> LocalModelServer[Ollama / vLLM / llama.cpp]
      LocalTools --> Filesystem[Local Storage (files, SQLite, Postgres+pgvector)]
      MCPServices --> Filesystem
      BackendAPI --> Database[(PostgreSQL + pgvector)] 
    end

    UI -- SSE/WebSocket --> AgentRuntime
    AgentRuntime --- Database
```

- **Presentation Layer (Tauri UI):** A Tauri app (Rust backend + Web UI) provides windows and menus. The UI (React/TypeScript + Monaco editor + xterm.js + Tailwind/Radix) calls the local backend via HTTP/WS. We isolate all logic server-side, keeping the front end as a thin renderer of events.
- **Workbench API (FastAPI):** The Rust backend (Tauri’s backend) proxies to a Python FastAPI process (could also embed Python via PyO3 but separate is cleaner). This “Workbench API” handles project/session management, file I/O, memory stores, and acts as the coordinator. It exposes endpoints for UI actions (open project, start session, post message).
- **Agent Runtime (Python/LangGraph):** The core agent loop runs here. It maintains session state, context assembly, planning, and iterative execution. We use LangGraph or a similar orchestrator to handle streaming, persistence, and human-in-the-loop steps. The runtime uses a **Context Manager** service to curate what to feed the LLM (AGENTS.md, session history, relevant docs). Memory across tasks (project and session memory) is stored in a DB or vector store and queried when needed. 
- **Capability Runtime / Tools (MCP):** When the agent calls a tool, it goes through a Router. For builtin tools (like file ops, shell, doc generation), the router invokes local implementations. For complex or organizational tools (domain-specific databases, SOP search), the router calls an MCP server (a separate HTTP service that follows MCP spec) which performs the operation and returns results. This split means adding new capabilities (e.g. ChatGPT skill, enterprise DB) is just writing an MCP server. The tool calls occur inside a **Sandbox** that enforces resource limits and no network. 
- **Infrastructure:** At the bottom are the models and data stores. The agent calls LLMs via a **Model Gateway** which abstracts Ollama or other backends. Ollama’s local API (default `localhost:11434`) serves models on device. We also run a local database (Postgres+pgvector) for knowledge retrieval, and a document store (raw files, embeddings). The sandbox uses container or VM technologies (details below) backed by the OS.

This architecture cleanly separates concerns. For example, the Model Gateway can later switch to vLLM or llama.cpp without changing higher layers. The use of MCP means the agent need not know implementation details of each tool. And with event-driven APIs, the frontend remains simple and reactive.

## Repository & Code Layout

We suggest a **monorepo** with this approximate structure:

```
sovereign-workbench/
├── apps/
│   ├── desktop/          # Tauri app (Rust + React frontend)
│   └── api/              # Backend API (Python FastAPI)
├── agents/
│   ├── context_manager/  # Context assembly code
│   ├── planning/         # Planner logic (LangGraph nodes)
│   ├── execution/        # Execution loop harness
│   └── memory/           # Memory (session/project) services
├── tools/
│   ├── filesystem/       # Tools: read_file, write_file, list_dir
│   ├── terminal/         # Terminal (node-pty management)
│   ├── sandbox/          # Sandbox launcher logic
│   ├── rag/              # RAG services (ingest, search)
│   ├── document/         # Document generation (DOCX, etc)
│   └── custom/           # Company-specific MCP tools
├── mcp/                  # MCP server implementations
├── models/               # Model gateway interface and adapters
├── storage/              # DB schema, migrations, PG setup
├── agents.md             # Root AGENTS.md (workspace-level instructions)
├── docs/                 # Documentation, architecture diagrams
└── tests/                # Automated tests (pytest, Playwright, Vitest)
```

- **apps/desktop** contains the Tauri project. Inside `src/` are React components (projects list, session view, terminal component with xterm.js, file editor with Monaco, etc). We use **Zustand** or Redux for local state (UI state), plus WebSocket client logic. The `src-tauri/` directory contains Rust side code to launch the Python API as a background process and manage the WebView.
- **apps/api** contains the Python backend. We use FastAPI with Pydantic models. This includes endpoints like `/sessions/create`, `/projects/open`, plus WebSocket endpoints for event streaming. Dependencies: SQLAlchemy (Postgres), asyncio tasks, MCP client adapters.
- **agents/** contains the core agent orchestration code, possibly using LangGraph or a custom loop. It takes prompts, builds context (with help from `agents/context_manager`), generates plans, invokes tools via `tools/`, and records state. We keep it decoupled from the API so it could later become a service. 
- **tools/** includes code for each tool. For example, `tools/filesystem` has Python functions for `read_file()`, `write_file()`, `search_files()`. `tools/terminal` wraps a PTY (via Python’s pty or node-pty in Tauri) to run shell commands. `tools/sandbox` sets up containers or Firecracker VMs. `tools/rag` has ingestion and search code (PDF parsers, OCR, chunking, embedding generation, query). `tools/document` uses libraries (python-docx, python-pptx, openpyxl, ReportLab) to create DOCX/PPTX/XLSX/PDF.
- **mcp/**: any MCP server code (could be simple Flask or Node) that connects e.g. a company’s internal knowledge base. 
- **models/** abstracts the LLMs. It might have a Python interface `def generate(model, prompt) -> text`. Underneath it calls Ollama’s HTTP API or llama.cpp.
- **storage/** holds DB schema scripts. We would define tables like `projects`, `sessions`, `users`, plus a `memories` table for session memory (text or embeddings), and an `artifacts` table (id, path, type, session_id, timestamp). For RAG, use `documents` and `chunks` tables with ParadeDB index on text (for BM25) and a vector column for pgvector.  
- **AGENTS.md**: We place a workspace-level AGENTS.md here, plus each project (and subfolder) can have its own AGENTS.md. At runtime, the context manager will concatenate them (global → project → session-level instructions) to form system prompts. 

This monorepo keeps UI code separate from backend logic and tools, but version-controlled together so developers can cross-reference. Packages for agent runtime, tools, and models could be broken into Python packages if needed.

## Database & Memory

We use **PostgreSQL + pgvector** for storage and retrieval. Key schemas:

- `projects(id, name, path, instructions_text, ...)`  
- `sessions(id, project_id, user_prompt, started_at, finished_at, transcript_log, ...)`  
- `memories(id, project_id, session_id, memory_type, content, embeddings)` – to store long-term project facts or session short-term memory. `embeddings` is a vector column (pgvector) for similarity search.  
- `documents(id, project_id, metadata, raw_content)`, `chunks(id, document_id, text, vector, ...)` for RAG ingestion (ParadeDB BM25 index on `chunks.text`, and vector on `chunks.vector`).  
- `artifacts(id, session_id, path, type, created_at)` to track output files.  
- `users(id, name, roles, ...)` and `permissions` tables for RBAC (e.g. which tools a user can auto-approve, etc).

We also use Redis (optionally) for ephemeral state (tool output buffers, rate limits), and a vector index (pgvector) to support similarity search. Full-text search can use ParadeDB’s extension for BM25, or Postgres’ native GIN indexes if ParadeDB isn’t available.

Memory manager design: Agent context comes from multiple sources: session transcript (JSON), relevant AGENTS.md, retrieved chunks (from RAG), and user-provided files. We **summarize** or **limit** content to fit token budgets. LangGraph or a custom **Context Service** can automatically prune older messages (e.g. summarise them), and fetch only top-N vector-similar chunks. For persistence, session memory could also write summaries or final decisions back to the `memories` table, so the agent “knows” what was decided. This aligns with LangGraph’s “comprehensive memory” benefit.

## AGENTS.md Specification

We support **hierarchical agent instructions**. Each project can have an `AGENTS.md` file at its root (and optionally in subfolders), containing guidelines and policies. For example:

```markdown
# Project AGENTS.md

- Always prefer Python 3.12, use type hints, and include pydantic for data models.
- Testing: require 100% unit test coverage for new code. Use pytest.
- Security: sandbox all external commands. Never allow internet calls.
- Architecture: use MVC pattern, with separate modules for routes, services, models.
- Company SOP: When drafting approval notes, cite sections from company manuals.
- Code Style: follow PEP8, run `flake8` and `black`.
```

The system merges these with session instructions. The effective context prompt is something like:

```
SYSTEM: [Global AGENTS.md ...] [Project AGENTS.md ...] 
USER: Please draft an approval note for inspection_report.pdf.
```

By codifying instructions, we “tell the agent how we want it to behave” consistently. This matches the user’s idea of an “agents start MD file”. The context manager will automatically load `AGENTS.md` from the workspace root, then project folder, and even the current file’s folder if applicable, to form a policy context. Any developer can add or update these files, and the agent honors them (e.g. style, compliance, tools to use).

## Tool Registry & MCP Integration

We maintain a **tool registry** mapping tool names to functions or MCP endpoints. For example:

```yaml
filesystem.read_file:
    type: native
    python: tools.filesystem.read_file
terminal.exec:
    type: native
    subprocess: /bin/bash  # or via node-pty
kb.search:
    type: mcp
    endpoint: http://localhost:8001/search
docgen:  
    type: native  
    python: tools.document.generate_docx  
```

Using MCP, the agent simply calls `kb.search(query)` and under the hood our MCP client makes an HTTP call to a knowledge base server. This decouples the agent from the implementation. We follow MCP spec so that existing MCP connectors (e.g. Claude’s) are compatible. 

Practically, the agent’s code might look like:

```python
# In agent logic:
cursor = langchain.LLMChain(prompt=my_prompt).run(agent_request)
if action == "search_knowledge":
    result = mcp_client.call("knowledge_search", query=cursor)
```

The front end will show MCP calls as “Tool: knowledge_search” with results. Importantly, our policy engine can treat MCP calls like any other: either auto-allowed or flagged. For example, a query that might leak sensitive data could require approval.

## Sandboxing & Isolation Comparison

Code and commands run inside isolated environments. We compare several options:

| Option            | Security                                  | Performance                       | Complexity                    | Offline Suitability         |
|-------------------|-------------------------------------------|------------------------------------|-------------------------------|-----------------------------|
| **Rootless Containers (e.g. Docker rootless/Podman)** | **Moderate** – Shares host kernel, but no root privileges (user namespace). Escape risk exists but limited. | **High** – Near-native speed, minimal overhead. | **Low** – Easy setup, just run containerd in rootless mode. | **High** – Fully offline once container image is local. |
| **gVisor (e.g. runsc)** | **High** – User-space kernel intercepts syscalls, reducing kernel exposure. Not hardware-level, but significantly better than plain containers. | **Medium** – ~10–30% overhead on I/O heavy tasks. OK for CPU-bound workloads. | **Medium** – Requires installing runsc and configuring runtimes. No nested VM needed. | **High** – Offline; just install runsc package. |
| **Firecracker (microVM)** | **Very High** – KVM-backed microVMs provide hardware-level isolation. Adversarial escapes require breaking hypervisor. | **Medium** – Good (<100ms boot, ~<10% runtime overhead). Minimal compute overhead, but heavier than containers. | **High** – Requires KVM support, VM images. More tooling needed (launch control plane). | **Medium** – Needs KVM-enabled kernel; offline once hypervisor is installed. |
| **Kata Containers**  | **Very High** – Actually packages Firecracker/QEMU under Kubernetes integration. Shares microVM security. | **Medium** – Similar to Firecracker, but extra layer. | **High** – Complex (often used with K8s). | **Medium** – As with Firecracker. |
| **Chroot / Namespaces**  | **Low** – Minimal isolation (no root? not recommended for untrusted code). | **High** – Native speed. | **Low** – Simple Linux feature. | **High** – Offline inherently. |

From this, we see:
- **Rootless containers** are easiest to use but provide only moderate safety. We can use them for dev or non-sensitive code.  
- **gVisor** strikes a balance: much safer than plain containers with acceptable overhead. It intercepts syscalls to sandbox them. Ideal for CPU-bound ML tasks.  
- **Firecracker/Kata** offer maximum isolation, at cost of complexity. If absolute security is needed (defense-in-depth), use a microVM. Firecracker boots extremely fast (~100ms) and can be run container-like.

**Offline Suitability:** All options can work offline once set up, as none require internet. We must bundle container images or VM kernels in our installer. 

Ultimately, we can allow configurations: a “Sandbox Mode” setting where operators pick Rootless (fast, low-overhead), gVisor, or Firecracker for execution. In any case, the **policy engine** runs outside the sandbox to decide what gets launched.

## Policy & Approval Engine

A deterministic **Policy Engine** sits between the agent and the sandbox. It inspects each `tool.request` event and categorises it as:

- **AUTO**: Safe operations (e.g. `read_file`, simple `ls`). Allowed without user prompt.  
- **ASK**: Potentially sensitive (e.g. `python install package`, `shell remove directory`, network access). These generate an `approval.required` event. The UI shows the exact command and context, letting the user [Allow]/[Deny].  
- **DENY**: Forbidden actions (e.g. outbound network, accessing protected files, escalating privileges). Immediately blocked with an error event.

For example, Claude Code’s design uses a multi-mode permission system and ML classifier, but here we keep it simple: a ruleset configurable by policy. The AGENTS.md or admin configuration can list allowed/denied commands. The policy enforces that **“the model does not decide its own safety.”** We log every decision. If the user denies an action, the agent gets a special “Permission Denied” observation and must adapt.

The UI’s approval dialog should clearly show the command, its purpose, and an option to “Always allow in this project” or “Always deny”, so repetitive approvals can be streamlined. 

## Terminal (PTY) Design

We embed **xterm.js** in the frontend for a real terminal experience. On the backend, we use a pseudo-tty (PTY) interface (e.g. Python’s `pty` or Node’s `node-pty`) to launch a shell subprocess inside the sandbox. The PTY driver allows full interactive I/O. Through the WebSocket, the UI sends keystrokes and receives output. This gives us shell features: command history, interactive programs, colors, etc.

The PTY is allocated per session or tab. Tabs/splits are managed in the React state (like a VSCode terminal). We ensure sessions survive (no reset on focus change). All commands entered by the agent or user go through the policy, just like script calls. The terminal pane also shows a prompt legend (e.g. green for success, red for error).

## RAG Pipeline & Multimodal Processing

We implement a **Document Ingestion Pipeline** to handle PDFs, scans, images, etc. The stages:

1. **Collect:** The user (or agent) adds files (PDF, Word, JPEG). We store them in a workspace directory.
2. **Parse & OCR:** For each new PDF/image, we run OCR. Scanned PDFs go through Tesseract or PaddleOCR. Native PDFs use a text extractor (pdfminer or PyMuPDF). We handle special content (tables, formulas) by either OCR plus heuristic table detectors, or calling a vision model if available (e.g. LayoutLM for table structure). Non-text (e.g. diagrams) we either skip or send to a separate image recognition tool. Accuracy is crucial here.
3. **Chunk:** The extracted text is split into chunks (~1000 characters or by paragraphs). We apply cleaning: remove hyphenation, attach source metadata (filename, page). We ignore boilerplate (headers/footers). This stage can use langchain text splitters or custom logic.
4. **Embed & Index:** Each chunk is embedded (using an embedding model from the local LLM suite) and stored in Postgres `chunks` table. We also maintain a ParadeDB (or Postgres FTS) index for BM25 on the text. As [32†L299-L307] notes, for semantic queries the vector index is used, and for keyword queries the text index is used. We can combine results (e.g. Reciprocal Rank Fusion) to get robust retrieval.  

During a session, when the agent calls `search_knowledge("query")`, we run two queries: a BM25 SQL query (using ParadeDB’s operators) and a vector similarity search (pgvector KNN). We then merge or rerank results by confidence. The top hits (e.g. snippets of manuals) are returned to the agent with citations (we include document title/page). This grounds the agent’s answers in actual content.

All of this runs **locally**. We launch OCR and embedding jobs asynchronously (e.g. via Python workers) and show progress in UI (for large files, a status bar). The UI can show an OCR progress indicator: “Page 3 of 12: processed” (like [15†L258-L262]’s activity feed). Once done, the agent can use the content.

Finally, we support images: if the user asks about an image or the agent sees an image file, we can call a vision model to describe it or extract text from it. (Not detailed in requirements, but aligned with “multimodal” mention.)

## Artifact Generation

When the agent needs to create deliverables (Word docs, Excel sheets, PDFs), it uses template-based generation. For example:

- **DOCX:** Use `python-docx`. We can create a document, style headings/paragraphs, insert tables. If we have a template, we can fill it.  
- **PPTX:** Use `python-pptx` to generate slides with text and images.  
- **XLSX:** Use `openpyxl` or `xlsxwriter` to create spreadsheets with data and formatting.  
- **PDF:** Use a library like `ReportLab` or convert HTML to PDF (WeasyPrint). Alternatively, generate a DOCX and use Pandoc to convert to PDF.  
- **Code files:** Just write to disk with syntax highlighting if needed (Monaco can do .py with color).

These tools run in the sandbox. The agent’s plan might include “Draft approval note” → it calls a `document.generate_docx` tool with content. We record an `artifact.created` event and add the file to the Artifacts pane. 

No external service is needed; we rely on open-source libraries (no internet calls). We may also allow simple templates in the project (e.g. a boilerplate .docx with header) that the agent can load and fill. This ensures consistency with corporate branding.

## Model Gateway & Inference

We abstract LLM calls behind a **Model Gateway**. For each task, the agent can use different models. For example, “coding” tasks may use a code-specialized model, while “text” tasks use an instruction model. The gateway can route `generate()` calls to:

- **Ollama API:** By default, we run the official Ollama server on the device. It hosts many open models (Gemma, GPT-J, etc.) and is optimized for local use. The API is fixed at port 11434.  
- **vLLM or llama.cpp:** For smaller/embedded use, we could spin up vLLM as a service or use `llama.cpp` for CPU inference. The gateway hides this detail.  
- **Configuration:** The user can select which model or provider to use (via settings or even per-session). 

The gateway also handles token streaming back to the agent loop. We ensure all models used are offline (e.g. downloaded weights). No queries go to OpenAI or similar cloud by default (and policies block network if needed). In effect, the entire LLM execution is on-premises.

## Observability, Audit & Network Monitor

Every session produces a **trace**. We log every event (as described above) and store them. For production, we can output JSON logs or even integrate with a tracing system (e.g. LangSmith for LangGraph). 

Critical audit data includes: agent plans, tool invocations, policy decisions (user allowed/denied what), file changes, and final artifacts. We might also log resource usage (time spent per tool, tokens used, etc.) for performance debugging.

Specifically for security, we include a **network monitor panel** in the UI. It shows all network attempts by the agent. Since we intend no Internet, it should show “External network: 0 attempts”. If a tool tries to reach out (e.g. a malicious `curl http://`), the sandbox/firewall drops it, and we log that “Blocked network access to http://...” in the UI. This provides demonstrable proof of “air-gap”.

All logs and events are encrypted at rest if needed, but since this is on-device, it’s already private. However, an organization may want to periodically export logs to its SIEM; we could provide an “Export audit log” function.

## Security & Hardening

- **RBAC:** The app can have user accounts/roles (especially on shared workstations). Certain projects may be restricted. The backend enforces permissions from a user DB. 
- **Deterministic Policy:** As noted, the LLM never decides security – a fixed policy does. We can code the policy rules and not expose them to the model. 
- **Dependency Vetting:** Only pre-approved local models and tools are allowed. We should ship the application as an offline bundle (including all binaries and model files) and perhaps checksum-verify them. No dynamic downloading of code. 
- **Minimal Network:** The system must not connect to outside. So no analytics, no updating of models at runtime. Updates (e.g. Tauri updates) happen via offline packages or air-gapped file transfers.
- **Testing & CI:** We will have a test suite (pytest) for backend logic and unit tests for agent and tools. For the UI, we use **Vitest** for component tests and **Playwright** or Tauri’s WebDriver setup for end-to-end (covering Windows/mac/Linux). CI pipelines (GitHub Actions) run all tests and a lint-check before merges.
- **Signing & Packaging:** We use Tauri’s build tools to produce signed installers (MSI for Windows, DMG for macOS, AppImage/Snap for Linux). We configure them for offline install (bundling all assets). We will also disable Electron-only features, to keep the bundle small (Tauri minimal).

## Testing & CI

We adopt continuous integration with the following strategy:
- **Backend (Python)**: Unit tests with pytest (pytest-cov for coverage >90%). Integration tests for the API (FastAPI TestClient) and for the agent logic (mocking tools). We simulate tool calls and verify the correct events and file outputs.  
- **Frontend (React)**: Component tests with Vitest or React Testing Library. E2E tests with Playwright, which can drive the Tauri app in headless mode. We write tests for user flows: creating a project, running a simple agent plan, and verifying results. Tauri’s docs mention example setups with Selenium/WebDriver.  
- **Sandbox & Safety**: We write policy tests to ensure certain commands are blocked. We simulate malicious agent prompts to check network calls are caught.  
- **CI Integration**: GitHub Actions can build the app on each push, run tests on Linux/macOS/Windows runners, and produce artifacts (installers) on release tags.

Automated tests ensure that feature regressions (e.g. UI not showing agent output) are caught early. We will also have a “smoke test” with a known LLM (like a small Llama-2 model) to run a demo task and verify the outputs.

## Packaging and Deployment

Using **Tauri 2**, we can produce native installers with one command. For example, running `tauri build` on each platform yields:
- **Windows:** MSI or EXE installer (with code-signing for SmartScreen, if corporate policies require).  
- **macOS:** `.app` bundle and signed DMG.  
- **Linux:** AppImage and Snap. We can also publish to AUR or create a Deb/RPM.  

For offline deployment, we create a single installer that includes the Node/Vite app, Rust binary, Python runtime, and all models. Tauri’s philosophy is minimal size: “by using the OS’s native web renderer, a Tauri app can be as little as 600KB” (not counting our code). We must test installers on clean VMs to ensure no hidden web calls.

Installation can be done via USB or internal repository. We will also provide an **enterprise bundle** docker or VM image that includes the API server, so one could run a dedicated server if multiple users share the app (optional).

## Tech Stack

**Recommended stack (all open-source/offline-capable):**

- **Desktop Shell:** Tauri 2 (Rust+WebView).  
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + Radix UI + [Monaco Editor](https://microsoft.github.io/monaco-editor/) + [xterm.js](https://xtermjs.org). State management with Zustand or Redux Toolkit.  
- **Backend/API:** Python 3.12, FastAPI, Pydantic (for models). Use asyncio for parallelism.  
- **Agent Framework:** LangGraph (for orchestration), supplemented by custom logic for policies and memory. Possibly use LangChain components for embedding search integration.  
- **Models:** Ollama (with Docker or native install) for core LLMs. Plan to support plug-in of vLLM or llama.cpp via the Model Gateway.  
- **Tools:** Python subprocess/PTY for shell, Pandas/OpenPyXL for spreadsheets, python-docx/pptx for docs, Tesseract/PyMuPDF for OCR/PDF.  
- **Knowledge & Retrieval:** PostgreSQL + ParadeDB (BM25) + pgvector. Redis only if needed for caching. Optionally use SQLite for simple note-taking.  
- **Security:** Linux containerd (rootless) or Firecracker (if high isolation) with seccomp and resource limits.  
- **Testing:** pytest (backend), Vitest (frontend), Playwright (E2E).  
- **CI/CD:** GitHub Actions or internal CI runner. Use Tauri’s CI docs for signing and building across OSes.  
- **Packaging:** Tauri build (MSI/DMG/AppImage). Provide installer and offline updater (no automatic internet updates).  

This stack is entirely open-source and suitable for on-premise use. It avoids Electron (for smaller footprint and security) and avoids cloud-only services. Performance-wise, Tauri apps are lightweight compared to Electron, and Python+FastAPI scales for our user counts (few concurrent sessions). All critical components (React, FastAPI, PostgreSQL, Tauri) have active support and documentation.

## API/Event Contract Examples

Below are example JSON events to illustrate the WS/SSE protocol. Each event has a `type` and payload:

```json
// User prompts the agent
{ "type": "user.prompt", "session_id": 123, "text": "Analyze report.pdf and draft approval note." }

// Agent creates a plan
{ "type": "agent.plan", "session_id": 123, "plan": ["Read report.pdf", "OCR pages", "Search SOP", "Write note"] }

// Agent requests a tool (e.g. file read)
{ "type": "tool.request", "session_id": 123, "tool": "read_file", "args": {"path": "report.pdf"} }

// Tool returns data
{ "type": "tool.response", "session_id": 123, "tool": "read_file", "output": "<binary PDF data>"} 

// Agent prints to terminal
{ "type": "agent.message", "session_id": 123, "content": "All relevant data extracted." }

// Agent invokes shell command (requires approval)
{ "type": "tool.request", "session_id": 123, "tool": "terminal.exec", "args": {"command": "python3 ocr.py report.pdf"}} 

// Policy needs approval
{ "type": "approval.required", "session_id": 123, "tool": "terminal.exec", "command": "python3 ocr.py report.pdf", "reason": "Non-auto tool"} 

// User allows it
{ "type": "tool.response", "session_id": 123, "tool": "terminal.exec", "stdout": "OCR done, 18 pages.", "exit_code": 0 }

// Agent creates artifact
{ "type": "artifact.created", "session_id": 123, "path": "approval_note.docx", "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }
```

The frontend listens for these events. When it sees `tool.request` of type `approval.required`, it pops up an [Allow/Deny] dialog. When it sees `agent.message` or `agent.plan`, it renders them in the chat pane. When it sees `tool.response` with stdout, it writes to the terminal widget.

## Phased Roadmap

We recommend developing in **vertical slices**. Each phase builds a usable subsystem. For example:

| Phase | Key Deliverables                          | Acceptance Criteria                             | Effort (p-weeks) |
|-------|-------------------------------------------|-------------------------------------------------|------------------|
| 1. **Workbench Shell** | Tauri app with Project/Session UI, file explorer, Monaco editor, xterm terminal (static). Backend stub responding. | Can open project folder, create session, open files, run simple CLI in terminal. UI is responsive. | 4 |
| 2. **Basic Agent Loop** | Integrated FastAPI + dummy agent loop. Tools: `read_file`, `list_dir`, `write_file`. | User sends prompt, agent returns canned plan, reads a local file and displays content in chat. | 3 |
| 3. **Approval System** | Policy engine added. UI prompts on dangerous tools (e.g. shell). | Attempting a known-denied action shows approval dialog. Granting permission runs it. Policy logs decisions. | 2 |
| 4. **Context & Memory** | Load AGENTS.md, session logs, basic vector DB. Context manager fetches relevant context. | Agent can query project files or memory and include results in prompt. Session transcript limited to last N turns. | 3 |
| 5. **MCP & Tools** | Implement MCP client/server for e.g. knowledge search. Tool registry. | Agent calls a mocked `knowledge_search` via MCP; results return to chat. New MCP tool integration demonstrated. | 3 |
| 6. **Sandbox Integration** | Execute agent tools inside a container or VM. Enforce network off. | Verified using netstat that no external traffic. File writes happen only in isolated sandbox. | 4 |
| 7. **RAG Knowledge Base** | Document ingestion pipeline (OCR, chunking, indexing). Search interface. | Upload a PDF, see it indexed. Agent uses `search_docs` to retrieve relevant text snippets. | 4 |
| 8. **Artifact Generation** | Tools to create DOCX/PPTX/XLSX, integrate into agent. | Agent produces an actual .docx file. UI lists it and shows a preview. | 3 |
| 9. **Multimodal Support** | Image and scan processing (OCR + optional vision models). | Upload image with text; agent can extract and search it. | 3 |
| 10. **Security/Hardening** | RBAC, encrypted storage, offline packaging, thorough audit logs. | Penetration test: agent cannot read disallowed files or send network. All sensitive actions logged. | 2 |
| 11. **Polish & QA** | Testing, documentation, UI refinements, installer builds. | UI matches design, tests pass on all OS, installers build correctly. | 4 |

(If any estimates are uncertain, we note “TBD”.)

Milestones can be set at the end of each phase. For example, after Phase 4 the system can show a simple agent working with context. After Phase 7, a preliminary demo can be given (inspection-report → findings → note) to stakeholders. 

## Merits and Sources

Our design follows recent best practices. We align with Anthropic’s “Claude Code” analysis (use of a while-loop, permission layers, append-only logs), and reuse proven components (Tauri for cross-platform GUI, xterm.js for terminal). We leverage MCP as intended to keep the system extensible. We cite sources like ParadeDB’s hybrid search guide and LlamaIndex’s ingestion pipeline to ensure robustness.

In summary, this **agentic workbench** is not a simple chatbot; it’s an IDE-level platform where AI is one subsystem among many. Each part is designed for production use: real UI components, strong sandboxing, clear events, and audit trails. By following the phased roadmap and leveraging open-source tools, a dev team can build a polished on-premise agent IDE that meets the project’s strict security and functionality requirements.

**Sources:** Tauri documentation, Ollama docs, LangGraph overview, MCP spec, Claude Code research, open-source IDE example, Postgres hybrid search guide, ingestion pipeline reference, container isolation comparison. These informed our architecture and choices.