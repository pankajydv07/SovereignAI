---
description: Add or reassign an Ollama model in the SWARAJ registry without touching application code.
---

# /new-model

## Steps

1. Ask me which model tag to add, if I haven't said.

2. Confirm it is installed and inspect its real capabilities:
   ```bash
   // turbo
   ollama list
   ```
   ```bash
   // turbo
   curl -s http://127.0.0.1:11434/api/show -d '{"model":"<tag>"}' | head -60
   ```
   Report back: does it support tool calling, vision, thinking? What is its context length, parameter count and quantisation?

3. Add to `models.yaml` — **the only file permitted to name a model**:
   ```yaml
   roles:
     coder: [<new-tag>, <existing-fallback>]   # order = preference
   overrides:
     <new-tag>:
       num_ctx: 32768        # cap below model max to control VRAM
       keep_alive: 30m       # residency policy
   ```

4. Run the benchmark to populate routing priors:
   ```bash
   make bench MODEL=<tag>
   ```

5. Report the scorecard and whether the role assignment still looks right.

## Hard rule

**Do not modify any file under `core/`, `apps/` or `packages/`.** If adding a model appears to require a code change, stop and tell me — the abstraction is broken and that is the bug to fix, not the symptom.

## Sanity check before finishing

```bash
// turbo
grep -rn --include=*.py --include=*.ts --include=*.rs -E ':[0-9]+b|qwen|llama|gemma|mistral' core/ apps/ packages/ || echo "clean: no model names in source"
```
