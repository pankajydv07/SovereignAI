---
description: Build a new UI screen or panel in the SWARAJ desktop app, to the design system.
---

# /new-screen

## Before writing any JSX

1. Read `.agents/rules/50-design-lock.md` and `docs/UI-SPEC.md`.
2. State back to me: the screen's purpose, its layout geometry, which existing primitives you will reuse, and what data it needs from the core. Wait for confirmation.

## Build

3. Reuse primitives before creating new ones: `DataTable`, `MonoValue`, `StatusChip`, `ConfidenceBar`, `SignalBanner`, `SplitPane`, `ModelDot`. Adding a near-duplicate primitive is a defect.

4. Implement **all five states**, not just the happy path:
   - default
   - empty — terse, one primary action, no illustration, no encouraging copy
   - loading — **named stage plus elapsed time**, never a bare spinner
   - error — real error text, plain-language consequence, and a button performing the actual remedy
   - degraded — names the lost capability and the fallback

5. Wire keyboard navigation with a visible 2px accent focus ring. Add the screen to the command palette.

6. Validate every payload crossing the IPC seam with its Zod schema before it enters state.

## Verify

7. Check at 1280px width and at 150% OS scaling.
8. Re-check the three locked properties: 13px base font, 4px radii, monospace for every machine-produced value.
9. Take a screenshot and show it to me.

## Do not

- Add business logic. The UI renders state and dispatches intents; the core decides.
- Use arbitrary Tailwind values. Extend the token set instead.
- Add emoji, shadows on cards, gradients, or rounded-xl.
