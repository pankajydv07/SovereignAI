"""Integration test for process SIGKILL and session resumption in SWARAJ agent core."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_subprocess_kill_and_resume_session(tmp_path: Path) -> None:
    """Spawn core subprocess, write session events, SIGKILL it, respawn and verify recovery."""
    db_path = tmp_path / ".swaraj" / "sessions.db"
    core_root = Path(__file__).resolve().parent.parent

    # Step 1: Launch core subprocess 1
    proc1 = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        "-m",
        "core.main",
        cwd=str(core_root),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert proc1.stdin is not None
    assert proc1.stdout is not None

    # Helper to send RPC & receive response
    async def call_rpc(
        proc: asyncio.subprocess.Process, method: str, params: dict[str, Any], msg_id: int
    ) -> dict[str, Any]:
        assert proc.stdin is not None
        assert proc.stdout is not None
        payload = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        req = json.dumps(payload) + "\n"
        proc.stdin.write(req.encode("utf-8"))
        await proc.stdin.drain()

        line = await proc.stdout.readline()
        assert line, "Unexpected EOF from subprocess stdout"
        res: dict[str, Any] = json.loads(line.decode("utf-8"))
        return res

    # Initialize RPC
    init_res = await call_rpc(proc1, "initialize", {"protocolVersion": "2024-11-05"}, 1)
    assert init_res.get("result", {}).get("status") in ("ready", "degraded")

    # Create new session
    session_id = "sess-kill-123"
    new_res = await call_rpc(
        proc1,
        "session/new",
        {
            "sessionId": session_id,
            "projectId": "proj-kill",
            "title": "Subprocess Kill Test Session",
            "dbPath": str(db_path),
        },
        2,
    )
    assert new_res.get("result", {}).get("sessionId") == session_id

    # Step 2: Terminate core process forcefully via SIGKILL (proc1.kill())
    proc1.kill()
    await proc1.wait()

    # Step 3: Respawn core process 2
    proc2 = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        "-m",
        "core.main",
        cwd=str(core_root),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert proc2.stdin is not None
    assert proc2.stdout is not None

    # Initialize RPC on process 2
    init2 = await call_rpc(proc2, "initialize", {"protocolVersion": "2024-11-05"}, 10)
    assert init2.get("result", {}).get("status") in ("ready", "degraded")

    # Load session on process 2
    load_res = await call_rpc(
        proc2,
        "session/load",
        {"sessionId": session_id, "dbPath": str(db_path)},
        11,
    )

    result = load_res.get("result", {})
    assert result.get("session", {}).get("sessionId") == session_id
    assert result.get("session", {}).get("title") == "Subprocess Kill Test Session"

    events = result.get("events", [])
    assert len(events) >= 1
    assert events[0]["eventType"] == "session_created"

    # Clean shutdown
    shutdown_res = await call_rpc(proc2, "shutdown", {}, 99)
    assert shutdown_res.get("result", {}).get("status") == "shutdown_acknowledged"
    await proc2.wait()
