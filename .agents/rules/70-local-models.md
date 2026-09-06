---
trigger: manual
description: Apply when working on the model registry, router, agent loop, prompts, or anything calling Ollama.
---

# Working with local models on Ollama

Local open-weight models behave differently from frontier cloud models in three ways that break naive agent code. Design for all three.

## 1. Never name a model in code

Code asks for a **role**; `models.yaml` maps roles to ordered candidate models. `models.yaml` is the only file in the repo permitted to contain a model tag.

❌ `response = await ollama.chat(model="qwen3-coder:30b", ...)`
✅ `response = await self.models.chat(role=Role.CODER, messages=msgs, tools=tools)`

Roles: `planner`, `coder`, `writer`, `vision`, `embedder`, `classifier`.

Adding a model is `ollama pull` plus at most one YAML line. If you had to touch application code to add a model, the abstraction is broken — fix the abstraction.

## 2. Tool calls will be malformed — repair, don't fail

This is the single most common reason a local agent "doesn't work". It is an engineering problem, not a model limitation.

```python
async def _invoke_tool(self, call: ToolCall, attempt: int = 0) -> ToolResult:
    tool = self.registry[call.name]
    try:
        args = tool.input_model.model_validate(call.arguments)
    except ValidationError as exc:
        if attempt >= 2:
            return ToolResult.failed(f"invalid arguments after 2 repairs: {exc}")
        # Feed the exact validation error back. Most failures are a wrong field
        # name or a stringified number, and one repair round fixes them.
        repaired = await self._ask_model_to_repair(call, exc)
        return await self._invoke_tool(repaired, attempt + 1)
    return await tool.run(args, self.ctx)
```

Also:
- **Check capability first.** `/api/show` reports whether a model supports tool calling. For models that don't, fall back to structured output: pass a JSON Schema in `format` with `temperature: 0`, and restate the schema in the prompt to ground it.
- **Expose few tools.** Only the tools relevant to the current task class — around six. A 25-tool menu measurably degrades selection accuracy on small models.
- **Prefer coarse tools.** One `fs_edit` taking a diff beats `insert_line` + `delete_line` + `replace_range`.
- **Tell the model it is in a loop** and may call tools repeatedly. This is Ollama's own guidance and it helps.

## 3. Context is VRAM, not just a token budget

`num_ctx` × `OLLAMA_NUM_PARALLEL` is physical memory. Exceeding it either OOMs or silently evicts a model you wanted resident.

- Budget per model from the registry, minus a response reserve
- File reads take line ranges; whole-file reads over threshold are refused with a hint to narrow
- Tool outputs clamped, with an explicit marker naming what was dropped
- Compact at ~70% of budget: summarise oldest turns, keep recent user messages verbatim, keep all pending plan state
- Leave `OLLAMA_NUM_PARALLEL` at 1 on constrained hardware

## Streaming accumulation

When streaming with tools, accumulate `thinking`, `content` **and** `tool_calls` across chunks, then append them together as one assistant message before appending `role: "tool"` messages with `tool_name`. Dropping any of the three produces a malformed follow-up request that fails in a way that looks like a model problem.

## Residency

`keep_alive` per request is the residency manager: hot role → `30m`, one-shot classification → `0`. Surface model loading in the UI with a named stage and elapsed time — never a bare spinner.