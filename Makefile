.DEFAULT_GOAL := help
SHELL := /bin/bash

# ---------------------------------------------------------------------------
# SWARAJ — every target must work with no internet connection.
# If a target needs the network, it is wrong. See .agents/rules/00-sovereignty.md
# ---------------------------------------------------------------------------

.PHONY: help setup protocol dev build test lint typecheck fmt bench demo \
        sovereignty check clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install all dependencies (offline-capable from local mirrors)
	cd apps/desktop && pnpm install --offline || cd apps/desktop && pnpm install
	cd core && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
	cd apps/desktop/src-tauri && cargo fetch

protocol: ## Regenerate cross-language types from packages/protocol/schema
	python3 packages/protocol/generate.py
	@echo "Generated: core/protocol/models.py, src-tauri/src/protocol.rs, apps/desktop/src/protocol.ts"

dev: ## Run the desktop app in development
	cd apps/desktop && pnpm tauri dev

build: ## Build production installers
	cd apps/desktop && pnpm tauri build

test: ## Run the full test suite
	cd core && .venv/bin/pytest -q
	cd apps/desktop/src-tauri && cargo test --quiet
	cd apps/desktop && pnpm vitest run

lint: ## Lint all three languages
	cd core && .venv/bin/ruff check .
	cd apps/desktop/src-tauri && cargo clippy --all-targets -- -D warnings
	cd apps/desktop && pnpm eslint .

typecheck: ## Type-check all three languages
	cd core && .venv/bin/mypy --strict .
	cd apps/desktop && pnpm tsc --noEmit

fmt: ## Format all three languages
	cd core && .venv/bin/ruff format .
	cd apps/desktop/src-tauri && cargo fmt
	cd apps/desktop && pnpm prettier --write .

bench: ## Benchmark models and populate routing priors. Usage: make bench [MODEL=tag]
	cd core && .venv/bin/python -m eval.bench $(if $(MODEL),--model $(MODEL),)

check: lint typecheck test protocol-fresh file-length model-names ## All CI gates
	@echo "All gates passed."

protocol-fresh: ## Fail if generated protocol files are stale
	@$(MAKE) -s protocol
	@git diff --exit-code --stat -- core/protocol apps/desktop/src/protocol.ts \
	  apps/desktop/src-tauri/src/protocol.rs \
	  || (echo "FAIL: generated protocol files are stale — commit them"; exit 1)

file-length: ## Fail on any source file over 400 lines
	@find core apps/desktop/src apps/desktop/src-tauri/src -type f \
	  \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.rs' \) \
	  ! -path '*/node_modules/*' -exec awk 'END{if(NR>400) print FILENAME": "NR" lines"}' {} \; \
	  | tee /tmp/swaraj-long-files
	@test ! -s /tmp/swaraj-long-files || (echo "FAIL: files exceed 400 lines"; exit 1)

model-names: ## Fail if a model tag appears outside models.yaml
	@! grep -rnE '(qwen|llama|gemma|mistral|deepseek|phi)[-a-z0-9.]*:[0-9]+b' \
	    core/ apps/ packages/ --include='*.py' --include='*.ts' --include='*.tsx' --include='*.rs' \
	  || (echo "FAIL: model tag found in source — use a role, see ADR-009"; exit 1)
	@echo "PASS: no model names in source"

sovereignty: ## Static air-gap audit
	@echo "== external URLs =="
	@! grep -rnE "https?://" core/ apps/ packages/ \
	    --include='*.py' --include='*.ts' --include='*.tsx' --include='*.rs' \
	    --include='*.html' --include='*.css' \
	  | grep -v "127.0.0.1:11434" | grep -v "localhost:11434" \
	  || (echo "FAIL: external URL found"; exit 1)
	@echo "== sockets in core =="
	@! grep -rnE "uvicorn\.run|\.listen\(|socket\.socket|FastAPI\(" core/ \
	  || (echo "FAIL: core opens a socket"; exit 1)
	@echo "== telemetry packages =="
	@! grep -rniE "sentry|posthog|analytics|telemetry|mixpanel" \
	    core/ apps/ packages/ --include='*.py' --include='*.ts' --include='*.toml' --include='*.json' \
	  | grep -v node_modules \
	  || (echo "FAIL: telemetry dependency found"; exit 1)
	@echo "PASS: static sovereignty checks clean"

demo: ## One-command bring-up on a clean machine
	@command -v ollama >/dev/null || (echo "Ollama not found — install it first"; exit 1)
	@curl -sf http://127.0.0.1:11434/api/tags >/dev/null || (echo "Ollama is not running"; exit 1)
	@$(MAKE) -s protocol
	cd apps/desktop && pnpm tauri dev

clean: ## Remove build artefacts
	rm -rf apps/desktop/dist apps/desktop/src-tauri/target core/.venv core/.pytest_cache
