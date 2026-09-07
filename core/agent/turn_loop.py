"""SWARAJ Agent Turn Loop, Argument Repair, Budget Tracking, and Policy Approval."""

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from pathlib import Path
import time
from typing import Any

from pydantic import ValidationError

from agent.budget import RunBudgetTracker, StopReason
from agent.policy import PolicyDecision, PolicyEngine
from agent.resources import compute_default_resource_pattern, extract_resource_string
from models.ollama import OllamaApiError, OllamaClient
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
        self, ollama_client: OllamaClient, tool_registry: ToolRegistry,
        budget_tracker: RunBudgetTracker, policy_engine: PolicyEngine | None = None,
        permission_requester: Callable[[str, str, str, str, str], Awaitable[tuple[str, str | None]]] | None = None,
        session_store: Any | None = None,
    ) -> None:
        self.ollama, self.registry, self.tracker = ollama_client, tool_registry, budget_tracker
        self.policy_engine = policy_engine or PolicyEngine(session_store=session_store)
        self.permission_requester, self.session_store = permission_requester, session_store
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
                    session_id=session_id, event_type="checkpoint", payload={"state": state, "details": details}
                )
            except Exception as exc:
                log.warning(f"failed_to_write_checkpoint: {exc}")

    async def _handle_tool_call(
        self,
        call: dict[str, Any],
        session_id: str,
        project_id: str,
        ctx: ToolContext,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Validate, evaluate policy, and execute a single tool call."""
        fn = call.get("function", {})
        name = fn.get("name", "")
        raw_args = fn.get("arguments", {})
        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args)
            except Exception:
                pass

        tool_inst = self.registry.get(name)
        if not tool_inst:
            valid_tools = [t.name for t in self.registry.list_all()]
            return None, f"Unknown tool '{name}'. Valid tools: {valid_tools}"

        try:
            validated_args = tool_inst.input_model.model_validate(raw_args)
            res_str = extract_resource_string(name, raw_args)

            decision, matched_pat = await self.policy_engine.decide(
                subject=None,
                tool=name,
                resource=res_str,
                side_effect=tool_inst.side_effect,
                project_id=project_id,
            )

            if decision == PolicyDecision.DENY:
                return {
                    "role": "tool",
                    "tool_name": name,
                    "content": f"Refusal: Execution of '{name}' on '{res_str}' is denied by rule '{matched_pat}'.",
                    "success": False,
                }, None

            if decision == PolicyDecision.ASK:
                if self.permission_requester is None:
                    return {
                        "role": "tool",
                        "tool_name": name,
                        "content": f"Refusal: Tool '{name}' requires approval but permission requester is unavailable (fail-closed).",
                        "success": False,
                    }, None

                await self.checkpoint_partial_state(
                    session_id,
                    "pending_approval",
                    {"tool": name, "resource": res_str, "args": raw_args},
                )

                t_before_approval = time.monotonic()
                try:
                    async with asyncio.timeout(120.0):
                        choice, chosen_pat = await self.permission_requester(
                            name,
                            tool_inst.side_effect.value,
                            f"Execute {name} on {res_str}",
                            res_str,
                            project_id,
                        )
                except TimeoutError:
                    await self.checkpoint_partial_state(
                        session_id, "approval_timed_out", {"tool": name, "resource": res_str}
                    )
                    return {
                        "role": "tool",
                        "tool_name": name,
                        "content": f"Refusal: Approval request for '{name}' timed out after 120s.",
                        "success": False,
                    }, None
                finally:
                    t_waited = time.monotonic() - t_before_approval
                    self.tracker.start_time += t_waited

                if choice in ("allow_once", "allow_session", "always_allow"):
                    pat_to_save = chosen_pat or compute_default_resource_pattern(res_str)
                    if choice == "allow_session":
                        self.policy_engine.add_session_rule(project_id, name, pat_to_save)
                    elif (
                        choice == "always_allow"
                        and self.session_store
                        and hasattr(self.session_store, "save_project_policy")
                    ):
                        await self.session_store.save_project_policy(
                            project_id, name, pat_to_save, "always_allow"
                        )
                else:
                    return {
                        "role": "tool",
                        "tool_name": name,
                        "content": f"Refusal: Permission denied by user for '{name}'.",
                        "success": False,
                    }, None

            result: ToolResult = await tool_inst.run(validated_args, ctx)
            return {
                "role": "tool",
                "tool_name": name,
                "content": str(result.output if result.success else result.error),
                "success": result.success,
            }, None

        except ValidationError as val_exc:
            return None, f"Argument validation error for tool '{name}': {val_exc}"
        except Exception as run_exc:
            return None, f"Tool execution failed for '{name}': {run_exc}"

    async def run_step(
        self,
        session_id: str,
        model_tag: str,
        messages: list[dict[str, Any]],
        task_class: str = "default",
        required_tool: str | None = None,
        supports_native_tools: bool = True,
        tool_context: ToolContext | None = None,
        project_id: str = "default-project",
        on_token: Callable[[str, str], Awaitable[None]] | None = None,
        on_tool_call: Callable[[dict[str, Any], dict[str, Any] | None], Awaitable[None]]
        | None = None,
    ) -> tuple[StopReason, list[dict[str, Any]]]:
        """Execute a single turn step with streaming, validation, repair, and budgeting."""
        if self._cancelled:
            await self.checkpoint_partial_state(
                session_id, "cancelled", {"messages": messages}
            )
            return StopReason.CANCELLED, messages

        stop_reason = self.tracker.get_stop_reason()
        if stop_reason:
            await self.checkpoint_partial_state(
                session_id, stop_reason.value, {"messages": messages}
            )
            raise RunBudgetExhausted(stop_reason, messages)

        all_tools = self.registry.list_all()
        fallback_path = Path(all_tools[0].name) if all_tools else Path(".")
        ctx = tool_context or ToolContext(workspace_root=fallback_path)

        is_vision = task_class in ("vision_ocr", "vision")
        tools_schema = (
            self.registry.to_ollama_tools(task_class)
            if (supports_native_tools and not is_vision)
            else None
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

            self.tracker.record_step()
            rem_time = self.tracker.remaining_time_s()
            if rem_time <= 0.0:
                stop_reason = StopReason.MAX_TOKENS
                await self.checkpoint_partial_state(
                    session_id, stop_reason.value, {"messages": messages}
                )
                raise RunBudgetExhausted(stop_reason, messages)

            try:
                async with asyncio.timeout(rem_time):
                    thinking = ""
                    content = ""
                    tool_calls: list[dict[str, Any]] = []

                    try:
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
                            raw_think = msg.get("thinking") or ""
                            raw_cont = msg.get("content") or ""
                            d_think = raw_think.encode("utf-8", "replace").decode("utf-8")
                            d_cont = raw_cont.encode("utf-8", "replace").decode("utf-8")
                            thinking += d_think
                            content += d_cont

                            if on_token and (d_cont or d_think):
                                await on_token(d_cont, d_think)

                            if "tool_calls" in msg and msg["tool_calls"]:
                                tool_calls.extend(msg["tool_calls"])

                            if chunk.get("done", False):
                                p_eval = chunk.get("prompt_eval_count", 0)
                                eval_c = chunk.get("eval_count", 0)
                                self.tracker.record_tokens(p_eval, eval_c)

                    except OllamaApiError as api_err:
                        if "does not support tools" in str(api_err).lower() and tools_schema:
                            tools_schema = None
                            thinking, content, tool_calls = "", "", []
                            async for chunk in self.ollama.stream_chat(
                                model=model_tag,
                                messages=messages,
                                tools=None,
                                format=format_param,
                                options=options,
                            ):
                                msg = chunk.get("message", {})
                                raw_think = msg.get("thinking") or ""
                                raw_cont = msg.get("content") or ""
                                d_think = raw_think.encode("utf-8", "replace").decode("utf-8")
                                d_cont = raw_cont.encode("utf-8", "replace").decode("utf-8")
                                thinking += d_think
                                content += d_cont
                                if on_token and (d_cont or d_think):
                                    await on_token(d_cont, d_think)
                                if chunk.get("done", False):
                                    self.tracker.record_tokens(chunk.get("prompt_eval_count", 0), chunk.get("eval_count", 0))
                        else:
                            raise

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

            assistant_turn: dict[str, Any] = {
                "role": "assistant",
                "content": content,
            }
            if thinking:
                assistant_turn["thinking"] = thinking
            if tool_calls:
                assistant_turn["tool_calls"] = tool_calls

            messages.append(assistant_turn)

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

            if not tool_calls:
                break

            tool_errors: list[str] = []
            executed_tools: list[dict[str, Any]] = []

            for call in tool_calls:
                obs, err = await self._handle_tool_call(
                    call, session_id, project_id, ctx
                )
                if on_tool_call:
                    await on_tool_call(call, obs)
                if err:
                    tool_errors.append(err)
                elif obs:
                    executed_tools.append(obs)

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

            if shared_repair_attempts > 0:
                successful_assistant_turn = messages[-1]
                del messages[repair_checkpoint_index:]
                messages.append(successful_assistant_turn)

            messages.extend(executed_tools)
            shared_repair_attempts = 0
            repair_checkpoint_index = len(messages)
            continue

        return StopReason.END_TURN, messages
