---
description: Verify a SWARAJ milestone actually meets the definition of done before closing it.
---

# /milestone-check

Run this before declaring any milestone complete. Be strict — the PRD's own rubric gives **zero credit for half-built features**, and a feature that only works in the happy path is a half-built feature.

## Automated gates

```bash
// turbo
make lint && make typecheck && make test
```

```bash
// turbo
make protocol && git diff --exit-code --stat || echo "FAIL: generated protocol files are stale"
```

## Manual audit — answer each honestly

**Completeness**
- [ ] Every feature claimed for this milestone is wired to the real core. No mock data, no `TODO: replace`.
- [ ] Loading, empty, error and degraded states exist for every new surface.
- [ ] Everything that can run over two seconds is cancellable, and cancellation actually stops the work.

**Quality**
- [ ] No file over 400 lines. Report any that are.
- [ ] No new `any`, `unwrap()`, `# type: ignore`, or broad `except Exception` without a justifying comment.
- [ ] No duplicated logic across processes.
- [ ] No dead abstractions — no interface with one implementation, no factory building one class.

**Design**
- [ ] 13px base font, 4px radii, monospace on every machine-produced value.
- [ ] No emoji, no card shadows, no gradients, no arbitrary Tailwind values.

**Sovereignty**
- [ ] Run `/sovereignty-audit` and paste the result.

**Traceability**
- [ ] Every new tool appears in the run trace and the audit record.
- [ ] Each feature maps to a PRD requirement ID. List them.

## Output

Produce a short report: what passed, what failed, and what you are recommending we cut rather than ship half-finished. Do not mark the milestone done if anything above fails — tell me instead.
