---
trigger: always_on
description: Non-negotiable air-gap invariants. Violating any of these is a build-breaking defect.
---

# Sovereignty — the rules that cannot be broken

This product's entire claim is that confidential refinery data never leaves the machine. A regression here is the most damaging defect we can ship, and it is verified live in front of evaluators.

## Hard rules

1. **The only permitted outbound destination in this codebase is `127.0.0.1:11434` (Ollama).**
   No other host, URL, domain or IP may appear in any HTTP client, config, or dependency call.
2. **No CDN references.** Fonts, stylesheets, scripts and icons are vendored into the repo. A `<link href="https://fonts.googleapis.com/...">` is a functional bug, not a convenience.
3. **No listening sockets.** The Python agent core talks to Rust over **stdio JSON-RPC**. If you are writing `uvicorn.run()`, `app.listen()`, or binding a port in the core, stop — you have taken a wrong turn.
4. **No telemetry, analytics, crash reporting, update checks, or license phone-home.** Adding a dependency that does any of these is a security defect.
5. **Sandboxed execution has no network interface.** Not "firewalled" — no interface exists.
6. **Confidential content is never logged above DEBUG.** Prompts, document text, extracted values and file contents are the material we are protecting.
7. **MCP servers are stdio transport only, and allowlisted.** No HTTP or SSE MCP transports.

## Before you finish any task, verify

- [ ] No new outbound host, URL or domain anywhere in the diff
- [ ] No CDN link in HTML, CSS or JS
- [ ] No new port bound
- [ ] No dependency added that checks for updates or sends telemetry
- [ ] Any new subprocess specifies its network isolation explicitly
- [ ] No confidential content logged at INFO or above

## If you think you need an exception

You do not. Stop and ask the user. There is no task in this product that requires reaching the internet, and a plausible-sounding reason to add one is a sign you have misunderstood the requirement.
