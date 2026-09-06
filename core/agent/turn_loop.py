"""SWARAJ Agent Turn Loop, Argument Repair, Budget Tracking, and Cancellation."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agent.budget import RunBudgetTracker, StopReason
from models.ollama import OllamaClient
from tools.base import ToolContext, ToolResult
from tools.registry import ToolRegistry

log = logging.getLogger(__name__)


class TurnLoopError(Exception):
    """Base exception for turn loop failures."""


class RunBudgetExhausted(TurnLoopError):  # noqa: N818
    """Raised when run budget (steps, tokens, wall clock) is exhausted."""

    def __init__(self, stop_reason: StopReason, partial_results: list[dict[str, Any]]) -> None:
        super().__init__(f"Run budget exhausted: {stop_reason.value}")
        self.stop_reason = stop_reason
        self.partial_results = partial_results


class TurnCancelledError(TurnLoopError):
    """Raised when turn execution is cancelled mid-stream by HTTP abort."""

    def __init__(self, partial_results: list[dict[str, Any]]) -> None:
        super().__init__("Turn execution cancelled")
        self.partial_results = partial_results


class TurnLoop:
    """Core turn execution loop managing model stream accumulation, repair, and budgeting."""

    MAX_REPAIR_ATTEMPTS: int = 2

    def __init__(
        self,
        ollama_client: OllamaClient,
        tool_registry: ToolRegistry,
        budget_tracker: RunBudgetTracker,
        session_store: Any | None = None,
    ) -> None:
        self.ollama = ollama_client
        self.registry = tool_registry
        self.tracker = budget_tracker
        self.session_store = session_store
        self.active_task: asyncio.Task[Any] | None = None
        self._cancelled: bool = False

    def cancel(self) -> None:
        """Abort in-flight HTTP stream request or tool execution immediately."""
        self._cancelled = True
        if self.active_task and not self.active_task.done():
            self.active_task.cancel()

    async def checkpoint_partial_state(
        self, session_id: str, state: str, details: dict[str, Any]
    ) -> None:
        """Write checkpoint to session store before returning a terminal state."""
        if self.session_store and hasattr(self.session_store, "append_event"):
            try:
                await self.session_store.append_event(
                    session_id=session_id,
                    event_type="checkpoint",
                    data={"state": state, "details": details},
                )
            except Exception as exc:
                log.warning(f"failed_to_write_checkpoint: {exc}")

    async def run_step(
        self,
        session_id: str,
        model_tag: str,
        messages: list[dict[str, Any]],
        task_class: str = "default",
        required_tool: str | None = None,
        supports_native_tools: bool = True,
        tool_context: ToolContext | None = None,
    ) -> tuple[StopReason, list[dict[str, Any]]]:
        """Execute a single turn step with streaming, validation, repair, and budgeting."""
        if self._cancelled:
            await self.checkpoint_partial_state(
                session_id, "cancelled", {"messages": messages}
            )
            return StopReason.CANCELLED, messages

        # Check step ceiling budget
        stop_reason = self.tracker.get_stop_reason()
        if stop_reason:
            await self.checkpoint_partial_state(
                session_id, stop_reason.value, {"messages": messages}
            )
            raise RunBudgetExhausted(stop_reason, messages)

        # Check remaining wall clock time
        rem_time = self.tracker.remaining_time_s()
        if rem_time <= 0.0:
            stop_reason = StopReason.MAX_TOKENS  # Wall-clock timeout mapped to max_tokens
            await self.checkpoint_partial_state(
                session_id, stop_reason.value, {"messages": messages}
            )
            raise RunBudgetExhausted(stop_reason, messages)

        self.tracker.record_step()
        all_tools = self.registry.list_all()
        fallback_path = Path(all_tools[0].name) if all_tools else Path(".")
        ctx = tool_context or ToolContext(workspace_root=fallback_path)

        # Prepared tool options
        tools_schema = (
            self.registry.to_ollama_tools(task_class) if supports_native_tools else None
        )
        format_param = None
        options = None

        if not supports_native_tools and required_tool:
            tool_obj = self.registry.get(required_tool)
            if tool_obj:
                format_param = tool_obj.input_model.model_json_schema()
                options = {"temperature": 0.0}

        shared_repair_attempts = 0
        repair_checkpoint_index = len(messages)

        while True:
            if self._cancelled:
                await self.checkpoint_partial_state(
                    session_id, "cancelled", {"messages": messages}
                )
                return StopReason.CANCELLED, messages

            rem_time = self.tracker.remaining_time_s()
            if rem_time <= 0.0:
                stop_reason = StopReason.MAX_TOKENS
                await self.checkpoint_partial_state(
                    session_id, stop_reason.value, {"messages": messages}
                )
                raise RunBudgetExhausted(stop_reason, messages)

            try:
                # Wrap model stream in asyncio.timeout for stream-level wall-clock safety
                async with asyncio.timeout(rem_time):
                    thinking = ""
                    content = ""
                    tool_calls: list[dict[str, Any]] = []

                    async for chunk in self.ollama.stream_chat(
                        model=model_tag,
                        messages=messages,
                        tools=tools_schema,
                        format=format_param,
                        options=options,
                    ):
                        if self._cancelled:
                            await self.checkpoint_partial_state(
                                session_id, "cancelled", {"messages": messages}
                            )
                            return StopReason.CANCELLED, messages

                        msg = chunk.get("message", {})
                        thinking += msg.get("thinking", "")
                        content += msg.get("content", "")

                        if "tool_calls" in msg and msg["tool_calls"]:
                            tool_calls.extend(msg["tool_calls"])

                        # Record tokens from Ollama done chunk
                        if chunk.get("done", False):
                            p_eval = chunk.get("prompt_eval_count", 0)
                            eval_c = chunk.get("eval_count", 0)
                            self.tracker.record_tokens(p_eval, eval_c)

            except asyncio.CancelledError:
                self._cancelled = True
                await self.checkpoint_partial_state(
                    session_id, "cancelled", {"messages": messages}
                )
                return StopReason.CANCELLED, messages
            except TimeoutError as exc:
                stop_reason = StopReason.MAX_TOKENS
                await self.checkpoint_partial_state(
                    session_id, stop_reason.value, {"messages": messages}
                )
                raise RunBudgetExhausted(stop_reason, messages) from exc

            # Append complete assistant message turn
            assistant_turn: dict[str, Any] = {
                "role": "assistant",
                "content": content,
            }
            if thinking:
                assistant_turn["thinking"] = thinking
            if tool_calls:
                assistant_turn["tool_calls"] = tool_calls

            messages.append(assistant_turn)

            # Check missing tool call requirement repair case
            if required_tool and not tool_calls and not format_param:
                if shared_repair_attempts < self.MAX_REPAIR_ATTEMPTS:
                    shared_repair_attempts += 1
                    err_msg = (
                        f"Step requirement error: Required tool '{required_tool}' "
                        "was not called. Please invoke the tool."
                    )
                    messages.append({"role": "user", "content": err_msg})
                    continue
                else:
                    break

            # Handle case with no tool calls (natural text end of turn)
            if not tool_calls:
                break

            # Process tool calls with pre-execution validation & repair
            tool_errors: list[str] = []
            executed_tools: list[dict[str, Any]] = []

            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments", {})

                tool_inst = self.registry.get(name)
                if not tool_inst:
                    valid_tools = [t.name for t in self.registry.list_all()]
                    tool_errors.append(
                        f"Unknown tool '{name}'. Valid tools: {valid_tools}"
                    )
                    continue

                try:
                    # Pre-execution Pydantic validation
                    validated_args = tool_inst.input_model.model_validate(raw_args)
                    result: ToolResult = await tool_inst.run(validated_args, ctx)

                    tool_obs = {
                        "role": "tool",
                        "tool_name": name,
                        "content": str(result.output if result.success else result.error),
                        "success": result.success,
                    }
                    executed_tools.append(tool_obs)

                except ValidationError as val_exc:
                    tool_errors.append(
                        f"Argument validation error for tool '{name}': {val_exc}"
                    )
                except Exception as run_exc:
                    tool_errors.append(f"Tool execution failed for '{name}': {run_exc}")

            if tool_errors:
                if shared_repair_attempts < self.MAX_REPAIR_ATTEMPTS:
                    shared_repair_attempts += 1
                    error_feedback = "\n".join(tool_errors)
                    err_feedback_msg = (
                        f"Tool call error feedback: {error_feedback}. "
                        "Please repair tool arguments and try again."
                    )
                    messages.append({"role": "user", "content": err_feedback_msg})
                    continue

            # Successful tool execution / repair finished
            # Prune failed intermediate repair attempts from history to save VRAM
            if shared_repair_attempts > 0:
                # Keep messages before repair attempts plus the final successful assistant turn
                successful_assistant_turn = messages[-1]
                del messages[repair_checkpoint_index:]
                messages.append(successful_assistant_turn)

            messages.extend(executed_tools)
            break

        return StopReason.END_TURN, messages
