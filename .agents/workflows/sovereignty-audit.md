---
description: Verify SWARAJ's air-gap guarantees still hold. Run before every milestone close and before any demo.
---

# /sovereignty-audit

The product's entire claim rests on this. A regression here is the most damaging defect we can ship.

## Static checks

Any outbound host other than loopback Ollama:
```bash
// turbo
grep -rnE "https?://" --include=*.py --include=*.ts --include=*.tsx --include=*.rs --include=*.html --include=*.css --include=*.toml core/ apps/ packages/ | grep -v "127.0.0.1:11434" | grep -v "localhost:11434" || echo "PASS: no external URLs"
```

CDN references in the frontend:
```bash
// turbo
grep -rnE "<link[^>]+href=\"https|<script[^>]+src=\"https|@import url\(https" apps/desktop/ || echo "PASS: no CDN references"
```

Sockets bound by the agent core:
```bash
// turbo
grep -rnE "uvicorn\.run|\.listen\(|bind\(\(|socket\.socket|FastAPI\(" core/ || echo "PASS: core opens no sockets"
```

Telemetry-ish dependencies:
```bash
// turbo
grep -rniE "sentry|posthog|analytics|telemetry|mixpanel|amplitude|datadog" core/ apps/ packages/ --include=*.py --include=*.ts --include=*.toml --include=*.json | grep -v node_modules || echo "PASS: no telemetry packages"
```

MCP transports:
```bash
// turbo
cat .agents/mcp_config.json
```
Confirm every entry is stdio. Any `http` or `sse` transport is a failure.

## Runtime checks (app must be running)

```bash
// turbo
ss -lntp 2>/dev/null | grep -v "11434" || echo "PASS: nothing listening besides Ollama"
```

```bash
// turbo
ss -tnp state established 2>/dev/null | grep -vE "127\.0\.0\.1|::1" || echo "PASS: no non-loopback connections"
```

Sandbox network isolation — should show loopback only:
```bash
// turbo
bwrap --unshare-net --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 --proc /proc --dev /dev /usr/sbin/ip addr 2>/dev/null || echo "check bwrap availability"
```

## Deliberate-attempt test

From inside the sandbox, attempt an external call and confirm it fails **and is logged**:
```bash
// turbo
timeout 5 curl -s https://api.anthropic.com >/dev/null 2>&1 && echo "FAIL: egress succeeded" || echo "PASS: egress blocked"
```
Then confirm the attempt appears in the egress monitor with process name and destination. Detection matters as much as blocking — an undetected block is not evidence.

## Report

State PASS or FAIL per check. On any failure, stop and tell me — do not attempt a workaround.
