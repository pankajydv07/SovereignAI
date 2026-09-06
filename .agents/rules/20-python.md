---
trigger: glob
globs: core/**/*.py
description: Python standards for the agent core.
---

# Python — `core/`

Python 3.12, `asyncio`, Pydantic v2. `mypy --strict` and `ruff` must pass. Line length 100.

## Typing

Strict typing, no exceptions. No bare `Any`. Every `# type: ignore` carries a comment naming the reason.

❌ **Bad**
```python
async def run_tool(name, args):
    tool = REGISTRY.get(name)
    return await tool(args)
```

✅ **Good**
```python
async def run_tool(name: ToolName, args: dict[str, object], ctx: RunContext) -> ToolResult:
    tool = REGISTRY.get(name)
    if tool is None:
        raise UnknownToolError(name)
    validated = tool.input_model.model_validate(args)
    return await tool.run(validated, ctx)
```

## Errors

Typed exceptions in `core/errors.py`. Catch the specific exception at the specific line that raises it.

❌ **Bad** — hides the bug, keeps the demo limping
```python
try:
    result = await self.ollama.chat(model=model, messages=msgs, tools=tools)
    return parse(result)
except Exception:
    return None
```

✅ **Good** — the caller can act on this
```python
try:
    result = await self.ollama.chat(model=model, messages=msgs, tools=tools)
except httpx.ConnectError as exc:
    raise ModelUnavailableError(model, "Ollama is not reachable at 127.0.0.1:11434") from exc
except httpx.ReadTimeout as exc:
    raise ModelTimeoutError(model, timeout_s=self.timeout_s) from exc
return ChatTurn.model_validate(result)
```

## Never swallow an error to keep something running

❌ **Bad**
```python
except ValidationError:
    pass  # model returned bad JSON, just continue
```

✅ **Good**
```python
except ValidationError as exc:
    # Local models frequently emit near-miss JSON. Repair with the error in
    # context rather than discarding the turn.
    return await self._repair_tool_call(call, exc, attempt=attempt + 1)
```

## Dependency injection, not globals

❌ **Bad**
```python
ollama_client = OllamaClient()   # module-level global

class Router:
    def route(self, task): return ollama_client.chat(...)
```

✅ **Good** — testable without a GPU
```python
class Router:
    def __init__(self, registry: ModelRegistry, classifier: TaskClassifier) -> None:
        self._registry = registry
        self._classifier = classifier
```

## Async hygiene

Never block the event loop. CPU-bound work — OCR, rendering, embedding — goes to a process pool.

❌ `text = pytesseract.image_to_string(img)`
✅ `text = await loop.run_in_executor(self._pool, pytesseract.image_to_string, img)`

## Logging

`structlog` only. Never `print()`. Never log prompt bodies, document text or extracted values above DEBUG.

❌ `log.info("prompt", prompt=full_prompt)`
✅ `log.info("model_call", role="coder", model=model_id, prompt_tokens=n_tokens)`
