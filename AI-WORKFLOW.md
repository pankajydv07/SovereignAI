# AI-WORKFLOW.md — How to build SWARAJ with Antigravity and skills

This project is built largely by prompting. That works — but only with discipline. This document is the discipline.

## The loop, per feature

```
1. GRILL      /grill-me            sharpen the spec until it's one-shottable
2. SCAFFOLD   /new-tool | /new-model | /new-screen | /protocol-change
3. BUILD      apex                 analyse → plan → execute → examine → screenshot
4. POLISH     impeccable, MIFB     ONLY inside our design tokens (see warning below)
5. AUDIT      thermo-nuclear       at each milestone close
6. GATE       /milestone-check + /sovereignty-audit
```

You will not use all six every time. **Grill Me plus APEX alone changes the output quality more than anything else on this list.**

---

## 1. Grill Me — before you write anything

The thing that prevents one-shotting is almost always a poorly defined need. Time spent clarifying up front returns tenfold during implementation.

Run it before each milestone, not each file. Good targets:

> "Grill me on milestone 2: the agent loop and tool registry."
> "Grill me on the approval gate — I want to be sure I've thought through the reject path."

**Feed it the constraints it cannot guess:** we are Ollama-only, air-gapped, roles-not-model-names, maker–checker is mandatory, no listening sockets. Otherwise it will ask good questions in the wrong direction.

Capture the answers into the PRD or an ADR. An interrogation whose results evaporate was wasted.

---

## 2. Workflows — scaffold correctly the first time

Use `/new-tool`, `/new-model`, `/new-screen`, `/protocol-change` rather than describing the same steps in prose. They encode ordering that matters — for example, generating protocol types before writing handlers, or confirming a tool's contract before implementing it.

---

## 3. APEX — build and verify

APEX's value here is the **examine** phase: it launches the app and returns a screenshot rather than claiming success. For a desktop Tauri app that means `pnpm tauri dev` must be running or launchable.

**Extend its acceptance criteria with ours.** When APEX asks what "done" means, give it the definition-of-done from `.agents/rules/60-testing.md` — wired to the real core, all five UI states, cancellable, appears in the run trace. Otherwise it will verify the happy path and stop.

Where screenshots are unreliable (terminal PTY behaviour, streaming, model swaps), ask for a recorded interaction or an explicit log excerpt instead.

---

## 4. Design skills — the important warning

**Impeccable and Make Interfaces Feel Better will fight this product's design.**

They are tuned to make apps look polished and friendly: rounder corners, larger type, more whitespace, softer colour, warmer copy. SWARAJ is deliberately the opposite — 13px base, 4px radii, dense 30px rows, monospaced machine values, zero emoji, control-room register. Run unguarded, `/impeccable` will "deslopify" our instrument aesthetic into precisely the generic SaaS look we are avoiding.

**How to use them safely:**

1. Run `npx impeccable init` once, then **overwrite the generated design file** with the contents of `.agents/rules/50-design-lock.md` plus `packages/design-tokens`. Impeccable is only as good as the design file it reasons from — give it ours.
2. Before invoking either skill, say: *"Our design tokens in `.agents/rules/50-design-lock.md` are authoritative and non-negotiable. Improve consistency within them. Do not change font sizes, corner radii, shadows, or copy tone."*
3. **Accept** from them: spacing and alignment consistency, focus states, tabular numerals, border precision, hover and transition states, contrast fixes, responsive behaviour.
4. **Reject** from them: larger type, bigger radii, added shadows or gradients, emoji, softened copy, extra whitespace, "friendlier" empty states, pill buttons.
5. After every design pass, re-check the three properties that carry the whole feel: **13px base, 4px radii, monospace on machine values.** These are the first three things any design pass undoes.

Where they genuinely help: our UI is *dense*, and dense UIs fail on alignment and rhythm. That is exactly what these skills are good at — once they are pointed at our system instead of a generic one.

---

## 5. Thermo-Nuclear — at milestone close

Run it when a milestone is feature-complete, before you move on. It catches the technical debt that fast AI-assisted building accumulates: tangled dependencies, files that ballooned, duplicated logic.

**Our file limit is 400 lines, not its default 1,000.** Say so when you invoke it.

Pair it with `/milestone-check`, which covers what Thermo-Nuclear does not: sovereignty, design tokens, PRD traceability, and whether features are actually wired to the real core.

---

## 6. Sovereignty audit — before every demo

`/sovereignty-audit`, every time. This is the product's central claim and the thing evaluators will probe. A regression here is worse than a missing feature.

---

## Practices that matter more than any skill

**Commit before every AI-driven change.** You need a clean rollback point. This is the cheapest insurance available.

**Never accept a large diff you have not read.** The failure mode of AI-assisted building is not bad code — it is *plausible* code that quietly violates an architectural boundary. Those pass tests and surface in month three.

**Re-anchor when the agent drifts.** One sentence usually does it:
> "This is a professional instrument for engineers in a refinery control-room environment — dense, calm, monospaced for machine facts, zero consumer-chat conventions."

**Watch for these five drift patterns specifically:**
1. Font sizes and radii creeping up
2. Model names appearing in application code
3. `try/except Exception` appearing "for robustness"
4. Mock data left behind a component
5. A new listening socket, or an external URL in a dependency

Each has a grep in `/sovereignty-audit` or `/milestone-check`. Run them.

**Keep AGENTS.md short.** It loads every session. When it grows past a couple of pages, move detail into a glob-scoped rule in `.agents/rules/` so it loads only when relevant. A constitution nobody reads because it costs 4,000 tokens per request is not a constitution.

**Update the rules when you catch a repeated mistake.** If you correct the same thing three times, that correction belongs in a rule file. That is how this system compounds rather than decays.
