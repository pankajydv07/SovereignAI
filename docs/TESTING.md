# Testing Strategy

## Principle

The failure mode of AI-assisted building is not bad code — it is **plausible code that quietly violates an assumption**. Tests exist to catch exactly that, so they target the seams and the invariants, not line coverage.

## Layers

| Layer | Tool | Coverage target |
|---|---|---|
| Python core | pytest + pytest-asyncio | Every tool, router, context manager, renderer, audit chain |
| Rust core | cargo test | PTY lifecycle, path scoping, sandbox launch, sidecar supervision |
| Frontend | vitest | Reducers, stores, protocol parsing, formatting helpers |
| Journeys | Playwright | One per PRD user journey, marked slow, nightly |
| Property | hypothesis | Path scoping, context-budget arithmetic |
| Contract | pytest + generated types | Round-trip Python → Rust → TypeScript |

## Ollama is always mocked in unit tests

A test needing a GPU is not a unit test. Record real streaming responses once, replay them as fixtures.

Every streaming fixture must include `thinking`, `content` **and** `tool_calls` chunks — including a tool call **split across chunk boundaries**, because that is where the accumulation bug lives.

```python
async def test_tool_call_split_across_chunks_is_reassembled(fixtures):
    stream = fixtures.load("tool_call_split.jsonl")
    turn = await agent.consume(stream)
    assert turn.tool_calls[0].function.name == "fs_read"
    assert turn.thinking, "thinking must not be dropped"
```

## The tests that matter most

**Router accuracy is asserted, not eyeballed.**
```python
def test_router_accuracy(labelled_set):
    acc = sum(router.classify(i.prompt) == i.expected for i in labelled_set) / len(labelled_set)
    assert acc >= 0.95, f"router accuracy regressed to {acc:.2%}"
```

**Path scoping has negative tests.** `../../etc/passwd`, absolute paths, symlinks pointing outside the workspace, and Unicode normalisation tricks. This is a security control.

**Context budget is property-tested.** An off-by-one here OOMs the GPU under load, which surfaces as "the model is broken".

**Cancellation actually cancels.** For every tool that can run over two seconds: start it, cancel it, assert the underlying process is dead and no partial write landed.

**Tool-call repair converges.** Feed deliberately malformed arguments; assert repair succeeds within two attempts or fails cleanly with a useful message.

**Sovereignty is a test, not just a checklist.** A test that greps the built artefact for external URLs, and an integration test asserting the sandbox has zero network interfaces.

## Definition of done — every module

1. Generated types committed; `mypy --strict`, `clippy -D warnings`, `tsc --noEmit` clean
2. Unit tests: happy path, **every declared error path**, cancellation
3. Wired to the real core — no mock data behind it
4. Loading, empty, error and degraded states implemented
5. Cancellable if it can exceed two seconds
6. Appears in the run trace and audit record, if it is a tool
7. Module docstring states what it owns and what it must never do

## CI gates

```
ruff · mypy --strict · clippy -D warnings · tsc --noEmit
pytest · cargo test · vitest
make protocol && git diff --exit-code       # generated types not stale
sovereignty grep                             # no external URLs, no new sockets
model-name grep                              # no model tags outside models.yaml
file-length check                            # nothing over 400 lines
```

Nightly: Playwright journeys against a small real model.

**Never merge with a skipped test.** Delete it or fix it. A skipped test is a lie that compounds.
