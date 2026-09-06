# GEMINI.md — Antigravity-specific rules for SWARAJ

`AGENTS.md` is the constitution — read it first. This file adds Antigravity-specific behaviour and **takes precedence where the two conflict**.

## Working style in this repo

**Plan before coding, always.** Show the plan as an artifact and wait for my confirmation on anything touching more than one file. This codebase has hard architectural boundaries; a plan that crosses one wrongly is cheaper to fix before implementation than after.

**Small steps, verified.** Implement one thing, run the relevant check, show me the result. Do not batch five changes and declare success.

**Report honestly.** If something does not work, say so and show the error. Never describe a partially-working feature as complete. If you disabled or skipped a test to make something pass, say that explicitly and prominently.

## Turbo commands

`// turbo` is permitted for read-only and verification commands — `make lint`, `make typecheck`, `make test`, `cargo clippy`, `ollama list`, `git status`, `git diff`, `grep`, the checks in `/sovereignty-audit`.

**Never mark these turbo:** anything writing outside the workspace, `git push`, `git reset --hard`, package installs, `ollama pull`, `rm`, anything with `sudo`, or any command touching `~/.gemini/`.

## Permission mode

Use `proceed-in-sandbox` while building. Switch to `strict` when working on the sovereignty, sandbox or audit code — those paths deserve line-by-line review.

## Screenshots

For any UI work, launch the app and show me a screenshot. Then check it against `.agents/rules/50-design-lock.md`:

- Is the base font 13px, not 16px?
- Are corners 4px, not rounded-xl?
- Are all machine-produced values monospaced?
- Any emoji, gradients, card shadows or pill buttons that crept in?

Report those four answers with the screenshot. Do not just say "looks good".

## Workflows available

`/new-tool` · `/new-model` · `/new-screen` · `/protocol-change` · `/milestone-check` · `/sovereignty-audit`

Use them rather than improvising the equivalent steps — they encode ordering that matters.

## Skills

- **`swaraj-domain`** (in this repo) — read it before generating or parsing any refinery or PSU document. You do not natively know this domain and invention here produces documents that look right to you and are obviously wrong to an engineer.
- **`grill-me`** — run before starting any milestone, to sharpen the spec until the work is one-shottable.
- **`apex`** — use for feature implementation. Its examine-and-screenshot loop is how UI work gets verified here.
- **`impeccable`, `make-interfaces-feel-better`** — **constrained**. See `.agents/rules/50-design-lock.md`. Our tokens are authoritative; these skills polish within the system, never replace it. Reject any output that enlarges type, rounds corners, adds shadows or softens copy.
- **`thermo-nuclear-code-quality-review`** — run at every milestone close. Note our file-size limit is 400 lines, stricter than its default 1,000.

## Context discipline

Prefer reading specific files over globbing the repo. When you need a file's content, read the relevant range rather than the whole file. This project's own agent has to manage a context budget carefully — so should you while building it.

## Do not

- Do not add a dependency without telling me its licence and size.
- Do not create a file over 400 lines.
- Do not edit anything under a `// GENERATED` header — run `make protocol` instead.
- Do not "helpfully" add features I did not ask for. Scope creep is the highest-severity risk on this project.
