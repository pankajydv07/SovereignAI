# SWARAJ Core (Python Agent Engine)

Python 3.12 package owning the agent loop, model registry, router, tool execution, OCR/ingestion, and SQLite session storage.

## Execution Model

The core runs as a stdio sidecar managed by Rust (`src-tauri`).
- **No network sockets** opened (`ss -lntp` shows nothing).
- Reads ACP JSON-RPC requests from `stdin`.
- Writes ACP JSON-RPC responses and notifications to `stdout`.
