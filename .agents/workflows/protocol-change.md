---
description: Add or change a cross-process message in the SWARAJ protocol, regenerating all three languages.
---

# /protocol-change

Cross-process types are **generated, never hand-mirrored**. Hand-mirrored types drift within a week and surface as a runtime bug in a demo.

## Steps

1. **Check ACP first.** We follow Agent Client Protocol shapes for session lifecycle, streaming updates, tool calls, permission requests, diffs and terminal references. Before inventing a message, confirm ACP does not already define it. If ACP has a near-match, extend it via `meta` rather than creating a parallel concept. Tell me which you chose and why.

2. Edit the schema in `packages/protocol/schema/`. Wire format is `camelCase`.

3. Regenerate:
   ```bash
   make protocol
   ```
   This writes Pydantic models, serde structs and TypeScript + Zod schemas. **Never edit a generated file.**

4. Handle the message in all three places:
   - `core/` — produce or consume it
   - `src-tauri/` — relay it
   - `apps/desktop/src/` — reduce it into UI state, validating with Zod at the seam

5. Add a round-trip serialisation test proving a message survives Python → Rust → TypeScript unchanged.

6. Verify nothing is stale:
   ```bash
   // turbo
   make protocol && git diff --exit-code --stat || echo "STALE: generated files differ, commit them"
   ```

## Report back

State which schema files changed, which generated files were rewritten, and confirm the round-trip test passes.
