---
trigger: always_on
description: The SWARAJ visual system is authoritative. Read before any UI work, and before running any design skill.
---

# Design lock

SWARAJ's UI is a **professional instrument** — plant control-room console, audit workstation. Dense, calm, precise. It is deliberately *not* a friendly consumer app, and the things that make it look "unpolished" to a general design heuristic are the things that make it correct for a refinery engineer working in it for six hours.

## The three properties that carry the entire feel

These are the first three things any design pass will "helpfully" undo. Restore them every time.

1. **13px base font.** Never 16px.
2. **4px corner radius.** Never `rounded-xl`, never pills except status chips.
3. **Every machine-produced value is monospaced** — model ids, latencies, confidences, equipment tags, hashes, run ids, token counts, coordinates, timestamps. Human prose is sans. This single rule creates the instrument feel.

## Locked tokens

- Row height 30px · 4px spacing grid · pane padding 16px
- Depth from **1px borders**, not shadows. One shadow level, popovers only
- Dark default `#0B0F14` / surface `#121821` / border `#263241` / text `#E6EDF3`
- Semantic colour used **only** for meaning: sovereign `#10B981`, verify `#F59E0B`, critical `#EF4444`, accent `#4C8DF6`
- Colour never carries meaning alone — always colour + icon + text label
- Motion: 120–150ms ease-out, only for pane resize, trace-step append, provenance highlight, counter tick, GPU-bar reallocation. Nothing else animates.

## Forbidden

Chat bubbles · avatars · emoji anywhere · sparkle or "AI" iconography · gradient heroes · glassmorphism · `rounded-3xl` · card shadows · centred narrow columns · shimmer skeletons · bare spinners · toast-only errors · onboarding carousels · exclamation marks in UI copy.

## Copy tone

Terse, factual, professional. The user is an engineer, not a consumer.

- ❌ "Oops! Something went wrong 😅 Let's try again!"
- ✅ "Model unavailable: qwen3-coder:30b is not loaded. 4.1 GB short of free VRAM."
- ❌ "Analyzing your document..." with a spinner
- ✅ "running glm-ocr on 3 regions… 4.2s"

**Loading states name their stage.** An unexplained six-second pause reads as a bug; "waking qwen3-coder… 4.2s" reads as a system managing VRAM deliberately. Same latency, opposite impression.

## When running design skills (`/impeccable`, make-interfaces-feel-better)

These skills are tuned to make apps look polished and friendly. Run unguarded, they will round our corners, enlarge our type, add whitespace and soften our colours — recreating exactly the generic SaaS look we are avoiding.

**Rules for using them here:**

1. This file and `packages/design-tokens` are **authoritative**. If a design skill's output conflicts with them, this file wins.
2. After `impeccable init`, overwrite the generated design file with our tokens and the forbidden list above.
3. Use them for what they are genuinely good at — spacing consistency, alignment, focus states, tabular numerals, border precision, micro-interactions — **within** our system.
4. Do not accept: font-size increases, radius increases, added shadows, added gradients, emoji, softened copy, extra whitespace, "friendlier" empty states.
5. After any design-skill pass, re-check the three properties at the top of this file.
