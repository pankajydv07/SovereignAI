"""SWARAJ Agent Core Entry Point (stdio JSON-RPC)."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Ensure core package root is in sys.path when invoked directly as a script
core_root = Path(__file__).resolve().parent.parent
if str(core_root) not in sys.path:
    sys.path.insert(0, str(core_root))

from models.ollama import OllamaApiError, OllamaClient, OllamaUnreachableError  # noqa: E402
from models.registry import ModelNotInstalledError, ModelRegistry, NoModelForRoleError  # noqa: E402

SUPPORTED_PROTOCOL_VERSION = "2024-11-05"

# Global state managers
registry = ModelRegistry()
ollama_client = OllamaClient()
active_streams: dict[Any, asyncio.Task[None]] = {}


def log_stderr(message: str) -> None:
    """Write diagnostic messages exclusively to stderr."""
    sys.stderr.write(f"[core] {message}\n")
    sys.stderr.flush()


def send_rpc_response(response: dict[str, Any]) -> None:
    """Send a single newline-delimited JSON-RPC response over stdout."""
    line = json.dumps(response) + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()


def send_rpc_notification(method: str, params: dict[str, Any]) -> None:
    """Send a JSON-RPC notification object over stdout."""
    send_rpc_response({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
    })


async def handle_chat_stream(msg_id: Any, params: dict[str, Any]) -> None:
    """Stream chat response from Ollama for a requested role."""
    role_name = params.get("role", "writer")
    messages = params.get("messages", [])

    try:
        model_tag = registry.resolve(role_name)
    except NoModelForRoleError as exc:
        send_rpc_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32001, "message": str(exc)},
        })
        return

    overrides = registry.get_overrides(model_tag)
    keep_alive = overrides.get("keep_alive", "30m")
    options = {
        k: v for k, v in overrides.items() if k in ("num_ctx", "temperature")
    }

    log_stderr(f"Starting chat stream for role '{role_name}' resolved to tag '{model_tag}'")

    accumulated_content = ""
    accumulated_thinking = ""
    metrics: dict[str, Any] = {}

    try:
        async for chunk in ollama_client.stream_chat(
            model=model_tag,
            messages=messages,
            options=options if options else None,
            keep_alive=keep_alive,
        ):
            delta_content = ""
            delta_thinking = ""

            msg_obj = chunk.get("message", {})
            if isinstance(msg_obj, dict):
                delta_content = msg_obj.get("content", "")
                delta_thinking = msg_obj.get("thinking", "")

            accumulated_content += delta_content
            accumulated_thinking += delta_thinking

            # Collect timing stats on completion chunk
            if chunk.get("done"):
                metrics = {
                    "total_duration": chunk.get("total_duration", 0),
                    "load_duration": chunk.get("load_duration", 0),
                    "prompt_eval_count": chunk.get("prompt_eval_count", 0),
                    "eval_count": chunk.get("eval_count", 0),
                    "eval_duration": chunk.get("eval_duration", 0),
                }

            send_rpc_notification("chat/token", {
                "id": msg_id,
                "role": role_name,
                "model": model_tag,
                "delta": delta_content,
                "thinking_delta": delta_thinking,
                "content": accumulated_content,
                "thinking": accumulated_thinking,
            })

        send_rpc_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "status": "completed",
                "role": role_name,
                "model": model_tag,
                "content": accumulated_content,
                "thinking": accumulated_thinking,
                "metrics": metrics,
            },
        })

    except asyncio.CancelledError:
        log_stderr(f"Chat stream for request id={msg_id} cancelled.")
        send_rpc_notification("chat/interrupted", {
            "id": msg_id,
            "reason": "cancelled",
        })
        raise
    except (OllamaUnreachableError, OllamaApiError) as err:
        log_stderr(f"Chat stream error: {err}")
        send_rpc_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32002, "message": str(err)},
        })
    finally:
        active_streams.pop(msg_id, None)


async def handle_rpc_message(line: str) -> bool:
    """Process a single stdio JSON-RPC line.

    Returns True if execution should continue, False on shutdown.
    """
    try:
        data: dict[str, Any] = json.loads(line)
        method = data.get("method")
        msg_id = data.get("id")
        params = data.get("params", {})

        if method == "initialize":
            req_version = params.get("protocolVersion")
            log_stderr(f"Initialize received with protocolVersion={req_version}")

            # Pre-flight model validation
            status = "ready"
            try:
                installed = await ollama_client.get_installed_tags()
                registry.validate_models(installed)
                log_stderr("Pre-flight model validation succeeded.")
            except ModelNotInstalledError as exc:
                log_stderr(f"Pre-flight model validation failed: {exc}")
                send_rpc_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32003, "message": str(exc)},
                })
                return True
            except OllamaUnreachableError as exc:
                log_stderr(f"Ollama offline during initialize: {exc}")
                status = "degraded"

            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": SUPPORTED_PROTOCOL_VERSION,
                    "version": "0.1.0",
                    "status": status,
                    "capabilities": {
                        "agent_loop": False,
                        "tools": [],
                    },
                },
            })
            return True

        if method == "ping":
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"status": "pong"},
            })
            return True

        if method == "chat/stream":
            task = asyncio.create_task(handle_chat_stream(msg_id, params))
            active_streams[msg_id] = task
            return True

        if method == "chat/stop":
            target_id = params.get("id")
            if target_id in active_streams:
                active_streams[target_id].cancel()
                log_stderr(f"Cancelled active stream id={target_id}")
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"status": "stopped", "target_id": target_id},
            })
            return True

        if method == "shutdown":
            log_stderr("Received shutdown request from supervisor.")
            for task in active_streams.values():
                task.cancel()
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"status": "shutdown_acknowledged"},
            })
            return False

        if msg_id is not None:
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            })
            return True

    except Exception as err:
        log_stderr(f"Error processing RPC line: {err}")

    return True


async def main() -> None:
    """Main stdio loop reading JSON-RPC from stdin."""
    log_stderr("SWARAJ Agent Core starting on stdio...")

    loop = asyncio.get_running_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            log_stderr("Stdin EOF received, exiting core main loop.")
            break

        trimmed = line.strip()
        if trimmed:
            should_continue = await handle_rpc_message(trimmed)
            if not should_continue:
                break


if __name__ == "__main__":
    asyncio.run(main())
