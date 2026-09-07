"""SWARAJ Agent Core Entry Point (stdio JSON-RPC)."""

import asyncio
import json
import logging
from pathlib import Path
import sys
from typing import Any
import uuid

# Ensure core package root is in sys.path when invoked directly as a script
core_root = Path(__file__).resolve().parent.parent
if str(core_root) not in sys.path:
    sys.path.insert(0, str(core_root))

import structlog

# Ensure ALL logging from standard logging and structlog goes strictly to stderr
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

from core.chat_handlers import ChatManager
from core.deliverable_handlers import handle_deliverable_rpc
from agent.policy import PolicyEngine
from models.discovery import ModelDiscoverer
from models.ollama import OllamaClient
from models.registry import ModelRegistry
from models.router import ModelRouter
from storage import SessionNotFoundError, SessionStore
from storage.deliverable_store import DeliverableStore
from tools.registry import create_default_tool_registry

SUPPORTED_PROTOCOL_VERSION = "2026-03-01"

log = logging.getLogger(__name__)

# Core state singletons
model_registry = ModelRegistry()
tool_registry = create_default_tool_registry()
ollama_client = OllamaClient()
router = ModelRouter(model_registry)
policy_engine = PolicyEngine()
session_stores: dict[str, SessionStore] = {}
deliverable_stores: dict[str, DeliverableStore] = {}


def sanitize_surrogates(obj: Any) -> Any:
    if isinstance(obj, str):
        return obj.encode("utf-8", "replace").decode("utf-8")
    if isinstance(obj, dict):
        return {k: sanitize_surrogates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_surrogates(v) for v in obj]
    return obj


def log_stderr(message: str) -> None:
    """Write diagnostic messages exclusively to stderr."""
    msg_clean = str(message).encode("utf-8", errors="replace").decode("utf-8")
    sys.stderr.buffer.write(f"[core] {msg_clean}\n".encode("utf-8", errors="replace"))
    sys.stderr.buffer.flush()


def send_rpc_response(response: dict[str, Any]) -> None:
    """Send a single newline-delimited JSON-RPC response over stdout."""
    clean_resp = sanitize_surrogates(response)
    line = json.dumps(clean_resp, ensure_ascii=False) + "\n"
    sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()


def send_rpc_notification(method: str, params: dict[str, Any]) -> None:
    """Send a JSON-RPC notification object over stdout."""
    send_rpc_response({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
    })


chat_manager = ChatManager(
    model_registry=model_registry,
    tool_registry=tool_registry,
    ollama_client=ollama_client,
    router=router,
    policy_engine=policy_engine,
    send_notification_fn=send_rpc_notification,
    send_response_fn=send_rpc_response,
    log_stderr_fn=log_stderr,
)


def get_session_store(
    project_path: str | Path | None = None,
    db_path: str | Path | None = None,
) -> SessionStore:
    """Resolve or cache SessionStore instance based on project path or db path."""
    if db_path:
        target = Path(db_path).resolve()
    elif project_path:
        target = Path(project_path).resolve() / ".swaraj" / "sessions.db"
    else:
        target = Path.home() / ".swaraj" / "sessions.db"

    target_str = str(target)
    if target_str not in session_stores:
        store = SessionStore(target)
        session_stores[target_str] = store
        policy_engine.session_store = store
    return session_stores[target_str]


def get_deliverable_store(
    project_path: str | Path | None = None,
    db_path: str | Path | None = None,
) -> DeliverableStore:
    """Resolve or cache DeliverableStore instance based on project path or db path."""
    if db_path:
        target = Path(db_path).resolve()
    elif project_path:
        target = Path(project_path).resolve() / ".swaraj" / "sessions.db"
    else:
        target = Path.home() / ".swaraj" / "sessions.db"

    target_str = str(target)
    if target_str not in deliverable_stores:
        target.parent.mkdir(parents=True, exist_ok=True)
        store = DeliverableStore(str(target))
        deliverable_stores[target_str] = store
    return deliverable_stores[target_str]


async def dispatch_rpc(data: dict[str, Any]) -> None:
    """Process an asynchronous stdio JSON-RPC request."""
    method = data.get("method", "")
    msg_id = data.get("id")
    params = data.get("params", {})

    try:
        if method == "session/new":
            p_id = params.get("projectId", "default-project")
            title = params.get("title")
            s_id = params.get("sessionId") or str(uuid.uuid4())
            store = get_session_store(params.get("projectPath"), params.get("dbPath"))
            res = await store.create_session(s_id, p_id, title)
            send_rpc_response({"jsonrpc": "2.0", "id": msg_id, "result": res})
            return

        if method == "session/load":
            s_id = params.get("sessionId")
            store = get_session_store(params.get("projectPath"), params.get("dbPath"))
            try:
                s_info = await store.get_session(s_id)
                events = await store.load_session_events(s_id)
                send_rpc_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"session": s_info, "events": events},
                })
            except SessionNotFoundError as err:
                send_rpc_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32004, "message": str(err)},
                })
            return

        if method == "session/list":
            store = get_session_store(params.get("projectPath"), params.get("dbPath"))
            sessions = await store.list_sessions(params.get("projectId"))
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"sessions": sessions},
            })
            return

        if method == "chat/stream":
            store = get_session_store(params.get("projectPath"), params.get("dbPath"))
            task = asyncio.create_task(
                chat_manager.handle_chat_stream(msg_id, params, store)
            )
            chat_manager.active_streams[msg_id] = task
            return

        if method == "chat/stop":
            target_id = str(params.get("id") or params.get("sessionId"))
            chat_manager.stop_chat(target_id)
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"status": "stopped", "target_id": target_id},
            })
            return

        if method == "permission/respond":
            req_id = params.get("requestId", "")
            opt = params.get("selectedOption", "")
            pat = params.get("resourcePattern")
            chat_manager.handle_permission_response(req_id, opt, pat)
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"status": "acknowledged", "requestId": req_id},
            })
            return

        if method == "plan/run":
            store = get_session_store(params.get("projectPath"), params.get("dbPath"))
            task = asyncio.create_task(
                chat_manager.handle_plan_run(msg_id, params, store)
            )
            chat_manager.active_streams[msg_id] = task
            return

        if method == "models/roster":
            discoverer = ModelDiscoverer(ollama_client)
            discovered = await discoverer.discover_all()
            running = await ollama_client.get_running_models()
            fulfilment = model_registry.get_role_fulfilment_status(
                {d.tag for d in discovered}, running
            )
            roster_models = [
                {
                    "tag": d.tag,
                    "digest": d.digest,
                    "parameterSize": d.parameter_size,
                    "quantization": d.quantization_level,
                    "contextLength": model_registry.get_num_ctx(
                        d.tag, d.context_length
                    ),
                    "discoveredMaxContext": d.context_length,
                    "supportsVision": d.supports_vision,
                    "supportsThinking": d.supports_thinking,
                    "supportsTools": d.supports_tools,
                    "isResident": any(
                        (m.get("name") or m.get("model")) == d.tag
                        for m in running
                        if isinstance(m, dict)
                    ),
                    "sizeVram": 0,
                    "sizeTotal": 0,
                }
                for d in discovered
            ]
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"fulfilment": fulfilment, "models": roster_models},
            })
            return

        if method.startswith("deliverable/"):
            dstore = get_deliverable_store(params.get("projectPath"), params.get("dbPath"))
            handled = await handle_deliverable_rpc(
                method, msg_id, params, dstore, send_rpc_response
            )
            if handled:
                return

        if msg_id is not None:
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })

    except Exception as err:
        log_stderr(f"Error handling RPC method {method}: {err}")
        if msg_id is not None:
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32000, "message": str(err)},
            })


def handle_rpc_message(line: str) -> bool:
    """Process a single stdio JSON-RPC line immediately or dispatch as task."""
    try:
        data: dict[str, Any] = json.loads(line)
        method = data.get("method")
        msg_id = data.get("id")

        if method == "initialize":
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": SUPPORTED_PROTOCOL_VERSION,
                    "version": "0.1.0",
                    "status": "ready",
                    "capabilities": {
                        "agent_loop": True,
                        "session_store": True,
                        "tools": [t.name for t in tool_registry.list_all()],
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

        if method == "shutdown":
            for task in chat_manager.active_streams.values():
                task.cancel()
            send_rpc_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"status": "shutdown_acknowledged"},
            })
            return False

        # Dispatch other methods as asynchronous tasks to prevent blocking stdio reading
        asyncio.create_task(dispatch_rpc(data))

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
            break
        trimmed = line.strip()
        if trimmed:
            should_continue = handle_rpc_message(trimmed)
            if not should_continue:
                break


if __name__ == "__main__":
    asyncio.run(main())
