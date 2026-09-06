---
description: Add a new agent tool to the SWARAJ core, correctly wired end to end.
---

# /new-tool

Add a tool to the agent's registry. Ask me for the tool's purpose if I haven't stated it.

## Steps

1. **Confirm the contract before writing code.** State back to me: the tool name, what it takes, what it returns, its side-effect class (`read` / `write` / `exec`), its timeout, and whether it needs approval. Wait for my confirmation.

2. Create `core/tools/<name>.py` with Pydantic input and output models:
   ```python
   class XxxInput(BaseModel):
       path: str = Field(description="Workspace-relative path")

   class XxxOutput(BaseModel):
       content: str
       truncated: bool
   ```

3. Implement and register:
   ```python
   @tool(
       name="xxx",
       kind=ToolKind.READ,
       side_effect="read",
       scopes=["workspace"],
       timeout_s=30,
       input_model=XxxInput,
       output_model=XxxOutput,
   )
   async def xxx(inp: XxxInput, ctx: RunContext) -> XxxOutput: ...
   ```

4. Register in `core/tools/__init__.py`. **Do not hand-write the Ollama tools JSON schema** — it is derived from the Pydantic model.

5. Tests in `core/tests/tools/test_<name>.py`: happy path, invalid input, timeout, cancellation. Plus a negative path-scoping test if it touches the filesystem.

6. If `side_effect` is `write` or `exec`: verify the approval prompt renders the **exact** command or diff, never a summary.

7. Only if the default tool card is insufficient, add a renderer in `apps/desktop/src/components/toolcards/`.

8. Run `make test` and report the result.

## Constraints

- Keep the total tool count exposed per task class near six — see `.agents/rules/70-local-models.md`
- Prefer one coarse tool over three fine-grained ones
- Every filesystem path goes through workspace scoping
- No tool may open a network connection
