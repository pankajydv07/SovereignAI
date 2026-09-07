"""Tool execution, validation, policy evaluation and approval handling."""

import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from pathlib import Path
import time
from typing import Any

from pydantic import ValidationError

from agent.policy import PolicyDecision, PolicyEngine
from agent.resources import compute_default_resource_pattern, extract_resource_string
from tools.base import ToolContext, ToolResult
from tools.registry import ToolRegistry

log = logging.getLogger(__name__)


async def handle_tool_call(
    call: dict[str, Any],
    session_id: str,
    project_id: str,
    ctx: ToolContext,
    registry: ToolRegistry,
    policy_engine: PolicyEngine,
    permission_requester: Callable[[str, str, str, str, str], Awaitable[tuple[str, str | None]]] | None,
    session_store: Any | None,
    checkpoint_fn: Callable[[str, str, dict[str, Any]], Awaitable[None]] | None = None,
    on_wait_time: Callable[[float], None] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate, evaluate policy, request approval if needed, and execute a tool call."""
    fn = call.get("function", {})
    name = fn.get("name", "")
    raw_args = fn.get("arguments", {})
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON in tool arguments for '{name}': {exc}"

    tool_inst = registry.get(name)
    if not tool_inst:
        valid_tools = [t.name for t in registry.list_all()]
        return None, f"Unknown tool '{name}'. Valid tools: {valid_tools}"

    try:
        validated_args = tool_inst.input_model.model_validate(raw_args)
        res_str = extract_resource_string(name, raw_args)

        decision, matched_pat = await policy_engine.decide(
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
            if permission_requester is None:
                return {
                    "role": "tool",
                    "tool_name": name,
                    "content": f"Refusal: Tool '{name}' requires approval but permission requester is unavailable (fail-closed).",
                    "success": False,
                }, None

            if checkpoint_fn:
                await checkpoint_fn(
                    session_id,
                    "pending_approval",
                    {"tool": name, "resource": res_str, "args": raw_args},
                )

            t_before_approval = time.monotonic()
            try:
                async with asyncio.timeout(120.0):
                    choice, chosen_pat = await permission_requester(
                        name,
                        tool_inst.side_effect.value,
                        f"Execute {name} on {res_str}",
                        res_str,
                        project_id,
                    )
            except TimeoutError:
                if checkpoint_fn:
                    await checkpoint_fn(
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
                if on_wait_time:
                    on_wait_time(t_waited)

            if choice in ("allow_once", "allow_session", "always_allow"):
                pat_to_save = chosen_pat or compute_default_resource_pattern(res_str)
                if choice == "allow_session":
                    policy_engine.add_session_rule(project_id, name, pat_to_save)
                elif choice == "always_allow" and session_store and hasattr(session_store, "save_project_policy"):
                    await session_store.save_project_policy(project_id, name, pat_to_save, "always_allow")
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
