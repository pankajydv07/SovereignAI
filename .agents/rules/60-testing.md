---
trigger: model_decision
description: Apply when writing, changing or reviewing tests, or when deciding whether a module is complete.
---

# Testing and definition of done

Tests are written with the code, not afterwards.

## What gets tested where

| Layer | Tool | Must cover |
|---|---|---|
| `core/` | pytest | Every tool, the router, the context manager, every renderer |
| Ollama calls | pytest + fixtures | **Always mocked.** A test needing a GPU is not a unit test |
| `src-tauri/` | cargo test | PTY lifecycle, path scoping (with negative cases), sandbox launch |
| `apps/desktop/` | vitest | Reducers, stores, protocol parsing |
| Journeys | Playwright | One per PRD user journey, marked slow, nightly |
| Property tests | hypothesis | Path scoping and context-budget arithmetic |

## Mocking Ollama

Record real streaming responses once and replay them. A streaming turn must include `thinking`, `content` and `tool_calls` chunks, because the accumulation logic is where bugs hide.

```python
async def test_agent_accumulates_streaming_tool_call(ollama_fixture):
    stream = ollama_fixture.load("qwen3_coder_tool_call_split_across_chunks.jsonl")
    turn = await agent.run_turn(stream=stream)
    assert turn.tool_calls[0].function.name == "fs_read"
    assert turn.thinking != ""          # thinking must not be dropped
    assert turn.content is not None     # nor content
```

## Router accuracy is an assertion, not a vibe

```python
def test_router_accuracy_meets_threshold(labelled_set):
    correct = sum(router.classify(item.prompt) == item.expected for item in labelled_set)
    accuracy = correct / len(labelled_set)
    assert accuracy >= 0.95, f"router accuracy regressed to {accuracy:.2%}"
```

## Definition of done — every module

1. Generated types committed; `mypy --strict`, `clippy -D warnings`, `tsc --noEmit` all clean
2. Unit tests for the happy path, **every declared error path**, and cancellation
3. Wired to the real core — no mock data behind it
4. Loading, empty, error and degraded states implemented
5. Cancellable if it can run longer than two seconds
6. Appears in the run trace and the audit record, if it is a tool
7. Module docstring states what it owns and what it must never do

## Never merge with a skipped test

Delete it or fix it. A skipped test is a lie that compounds.
