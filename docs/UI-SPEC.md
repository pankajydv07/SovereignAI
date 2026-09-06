# UI Specification

The build reference for SWARAJ's interface. `.agents/rules/50-design-lock.md` is the enforced summary; this is the detail.

## Register

A **professional instrument** — plant DCS console, glass cockpit, audit workstation. Dense, calm, precise. The user is an inspection engineer or deputy manager working in this for six hours on confidential material.

**Not:** chatbot, Discord, consumer AI product, marketing page.

## The load-bearing principle

**Trust surfaces are the product, not chrome.** Four things most AI UIs bury in a debug drawer are primary UI here, with real estate and visual weight:

1. Which model handled this, and why it was chosen
2. Which pixel of which scanned page each extracted value came from
3. That zero packets have left the machine
4. Who is accountable for approving this output

In this domain an answer is worthless unless the user can see its provenance and ownership.

## Tokens

**Dark (default)**
```
--bg        #0B0F14      --text        #E6EDF3
--surface   #121821      --text-dim    #9AA7B4
--surface-2 #1A222E      --text-faint  #6B7A8A
--border    #263241      --accent      #4C8DF6
--hairline  #1B2430
```

**Light** (review mode — deliverables, printing, projectors)
```
--bg #FFFFFF · --surface #F6F8FA · --surface-2 #EEF1F4
--border #D0D7DE · --text #1F2328 · --text-dim #57606A · --accent #0B62D6
```

**Semantic** — used only for meaning, never decoration. Scarcity is what gives them force.
```
--sovereign #10B981   air-gap confirmed · verified · chain intact
--verify    #F59E0B   low confidence · human verification required
--critical  #EF4444   blocked egress · chain break · rejection
```

**Model tints** — one stable hue per role, used consistently in badges, trace and the GPU bar so users learn them.
```
planner #6366F1 · coder #8B5CF6 · vision #06B6D4 · ocr #14B8A6
```

**Type.** Inter (UI) + IBM Plex Mono (machine values), both self-hosted — a Google Fonts link would be a sovereignty defect. Scale 11/12/13/14/16/20/28. Base 13px. Line-height 1.45 body, 1.2 headings.

**The rule that creates the instrument feel:** every value the machine produced is monospaced with tabular numerals. Model ids, latencies, confidences, equipment tags, hashes, run ids, token counts, coordinates, timestamps. Human prose is Inter.

**Geometry.** 4px grid · 30px table rows · 16px pane padding · 4px radius (6px max on cards) · depth from 1px borders, one shadow level for popovers only.

**Motion.** 120–150ms ease-out. Only: pane resize, trace-step append, provenance highlight (exactly two pulses), counter tick, GPU-bar reallocation (400ms — the one exception). Honour `prefers-reduced-motion`.

## Shell

```
┌────────────────────────────────────────────────────────────────────────┐
│ SWARAJ │ dept ▾          │ user · ROLE │ 🛡 AIR-GAPPED  EGRESS 0  GPU 71% │ 44px
├──┬─────────────────────────────────────────────────────────────────────┤
│  │ FILE TREE          │  CONVERSATION            │  INSPECTOR          │
│56│ ───────────────    │  messages · tool cards   │  TRACE │ SOURCES │  │
│px│ SESSIONS           │  diffs · plans           │  DELIVERABLES       │
│  │ ───────────────    │  approval prompts        │                     │
│  │                    ├──────────────────────────┤                     │
│  │                    │  TERMINAL (tabbed, PTY)  │                     │
└──┴────────────────────┴──────────────────────────┴─────────────────────┘
```

The sovereignty rail is on **every** screen — permanently visible, therefore permanently on camera during a demo.

## Key components

### Routing badge
On every agent response, top-right. All monospace, 11px:
`● devstral-2-22b · code_generate · 0.98 · 28ms`

Click opens a 420px popover: feature vector, then a candidate table with one row per model considered — quality prior, VRAM fit, latency estimate, swap cost, total. Winner has a `--sovereign` left border; losers show a terse reason ("context too short", "capability missing: vision", "not resident, swap cost 6.1s").

This is a trust feature, not debug output. Style it as a first-class panel.

### Run trace
Vertical stepper in the inspector. Budget meter pinned at top: `STEP 7/25 · 12.4s · 8,240 tok`. One 30px row per step: status glyph, index, tool name, model tint dot, duration, expander. Expanded shows input/output JSON at 11px mono, with failed steps showing retry count and the critique text verbatim.

New steps slide in over 120ms, auto-scrolling unless the user scrolled up — then a "3 new steps ↓" pill.

**Model swaps get their own row:** `waking qwen3-coder-30b… 4.2s` with a live timer, and the GPU bar animating. Never hide swap latency behind a spinner.

### Approval prompt
Renders inline in the trace as a blocking card, 2px `--verify` left border. Shows the **exact** command or diff, never a summary. Options: Allow once · Allow this session · Always allow · Deny. The run visibly halts — the pause should feel deliberate, not like a stall.

### Provenance viewer
Split 50/50, synchronised. Left: page canvas with bbox overlays (accent = extracted, verify = low confidence, critical = unreadable, sovereign = human-verified). Right: field table or draft.

**The signature interaction:** click a field → canvas scrolls, zooms to the bbox with 40px padding, pulses exactly twice, holds a highlight. Click a bbox → the field scrolls into view and flashes. Both stay linked while selected. Pre-render adjacent pages so there is no loading state between click and highlight.

### Review & approve
Deliverable renders on a **white page with the org letterhead at true proportions**, in light mode regardless of app theme — the one place a shadow is permitted, because it should read as a physical document.

Action bar: maker/checker identity chips on the left; `Reject with reason` · `Edit & approve` · `Approve` on the right, with a 24px gap before Approve. Approve is the only filled `--sovereign` button on screen.

Blocking banner when preconditions fail: *"Cannot approve: 2 extracted fields unverified · 1 claim without citation"* with a jump link. The Approve button is disabled **and the banner explains why** — never a silently dead button.

### GPU allocation bar
28px stacked horizontal bar. Resident models solid in their tint; sleeping models at 35% opacity with a 45° hatch; free space bordered. Reallocates over 400ms during a swap with a brief glow on the waking segment. This one component communicates the entire multi-model story.

### Sovereignty monitor
Hero block: 96px mono `0` in sovereign green, labelled `EXTERNAL EGRESS ATTEMPTS · THIS SESSION`. Four verified assertions beside it (nftables policy, no default route, sandbox interfaces 0, egress-capable tools 0). Below: live event feed, monospace, newest first — internal rows dim and receding, blocked rows in critical with a 2px left border, **pinned to the top until acknowledged**.

**The inverted-convention moment:** when the physical link drops, show green, not red.

```
✓  AIR-GAPPED — no physical network link detected.
   All functions nominal. 4 models resident · 0 features degraded.
```

No reconnect button — there is nothing to reconnect to, and offering one would undercut the entire claim.

## Global behaviour

**Loading** — never a bare spinner. Name the stage and show elapsed time: `waking qwen3-coder… 4.2s`, `running glm-ocr on 3 regions…`, `executing in sandbox… 12s of 60s`. Anything that can exceed two seconds names its stage.

**Errors** — inline, persistent, actionable. Real error text, the consequence in plain language, and a button that performs the remedy: *"OOM loading devstral-2-22b: 4.1 GB short. [Sleep glm-4.7-flash] [Use qwen3-coder-8b]"*.

**Empty states** — left-aligned, terse, one primary action, no illustration. Where useful, 2–3 domain-specific example tasks rather than an abstract description.

**Degraded** — name the lost capability and the fallback precisely. Vague warnings train users to ignore banners.

**Numbers** — tabular, right-aligned in tables. Durations `840ms` / `4.2s` / `2m 14s`. Confidence always two decimals (`0.91`, never `91%`). Timestamps absolute (`14:22:09 · 05 Sep`), never relative — an audit context needs exact times.

**Keyboard** — ⌘K palette (complete: if it is in a menu it is in the palette), ⌘↵ run, ⌘⇧↵ approve with confirmation, `/` focus composer, `[` `]` toggle panes, `j`/`k` list navigation, `g` then letter to navigate, `?` for the shortcut sheet. Visible 2px focus rings throughout.

**Density and theme** — Comfortable (34px) / Compact (30px, default). Dark / Light / **Presenter** (light + 1.25× type + pinned sovereignty panel, for projectors). All persisted.

**Print** — deliverables and attestation reports must print correctly: light mode forced, chrome hidden, page breaks respected, footnotes rendered. People will print approval notes.

**Responsive** — desktop-first at 1440px, must work at 1280px. Below 1024px the inspector collapses to a drawer. No phone layout; pretending otherwise would compromise the density that makes this good.

## Accessibility

WCAG AA minimum 4.5:1 — verify the dim tokens actually pass. **Colour never carries meaning alone** — always colour + icon + text label, because industrial workforces have meaningful colour-blindness prevalence and this tool gates safety-adjacent documents. Approve/Reject targets minimum 40px tall with a visual gap between them. Full keyboard operability. Legible at 125% and 150% OS scaling.
