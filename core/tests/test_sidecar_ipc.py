"""Unit tests for SWARAJ Agent Core stdio JSON-RPC protocol handling."""

import asyncio
import json
import os
import subprocess
import sys

import pytest


@pytest.mark.asyncio
async def test_initialize_and_ping_handshake() -> None:
    """Test initialize protocolVersion negotiation and ping response over stdio."""
    main_py = os.path.join(os.path.dirname(__file__), "..", "core", "main.py")
    proc = subprocess.Popen(
        [sys.executable, main_py],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert proc.stdin is not None
    assert proc.stdout is not None

    # 1. Initialize
    init_req = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2026-03-01"},
    }) + "\n"
    proc.stdin.write(init_req)
    proc.stdin.flush()

    init_resp_line = proc.stdout.readline()
    init_resp = json.loads(init_resp_line.strip())
    assert init_resp.get("id") == 1
    assert init_resp["result"]["protocolVersion"] == "2026-03-01"
    assert init_resp["result"]["version"] == "0.1.0"

    # 2. Ping
    ping_req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}) + "\n"
    proc.stdin.write(ping_req)
    proc.stdin.flush()

    ping_resp_line = proc.stdout.readline()
    ping_resp = json.loads(ping_resp_line.strip())
    assert ping_resp.get("id") == 2
    assert ping_resp["result"]["status"] == "pong"

    # 3. Shutdown
    shutdown_req = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "shutdown"}) + "\n"
    proc.stdin.write(shutdown_req)
    proc.stdin.flush()

    sht_resp_line = proc.stdout.readline()
    sht_resp = json.loads(sht_resp_line.strip())
    assert sht_resp["result"]["status"] == "shutdown_acknowledged"

    proc.wait(timeout=2)
    assert proc.returncode == 0


if __name__ == "__main__":
    asyncio.run(test_initialize_and_ping_handshake())
    print("ALL PYTHON SIDECAR IPC TESTS PASSED!")
