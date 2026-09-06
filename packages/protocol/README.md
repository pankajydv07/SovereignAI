# Protocol Schemas (`packages/protocol/schema`)

This directory is the **single source of truth** for all cross-process messages in SWARAJ (Rust shell ↔ Python agent core ↔ TypeScript React frontend).

## Usage

1. Add or edit JSON Schema files in `packages/protocol/schema/`.
2. Run `make protocol` (or `python packages/protocol/generate.py`).
3. Generated files produced automatically:
   - `core/protocol/models.py` (Pydantic v2)
   - `apps/desktop/src-tauri/src/protocol.rs` (serde Rust types)
   - `apps/desktop/src/protocol.ts` (TypeScript types + Zod)

**Do not manually edit generated files.** They carry a `// GENERATED` header.
