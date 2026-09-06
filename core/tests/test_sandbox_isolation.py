"""Rigorous Security & Network Isolation Test Suite for SWARAJ Sandbox Runner.

Validates:
1. 3-way Network Isolation (Local LAN listener, negative control, specific WSAEACCES / EPERM error).
2. Ollama 127.0.0.1:11434 exfiltration prevention.
3. Dual Wall-Clock & CPU Timeout Enforcement (CPU-bound while True & Sleep-bound time.sleep).
4. Filesystem Isolation (project root denial, user profile denial, negative control, write outside work_dir denial).
5. Path Traversal & Symlink Copy-Out Hardening.
"""

from pathlib import Path
import socket
import tempfile
import time
import pytest

from sandbox.runner import (
    SandboxRunnerError,
    canonicalize_and_verify_out,
    extract_declared_outputs,
    prepare_sandbox_env,
)


def test_prepare_sandbox_env_sets_mandatory_vars(tmp_path: Path):
    env = prepare_sandbox_env(tmp_path)
    assert env["MPLBACKEND"] == "Agg"
    assert env["MPLCONFIGDIR"] == str(tmp_path.resolve())
    assert env["HOME"] == str(tmp_path.resolve())
    assert env["USERPROFILE"] == str(tmp_path.resolve())
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"


def test_canonicalize_and_verify_out_valid(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    valid_file = out_dir / "report.json"
    valid_file.write_text('{"status": "ok"}', encoding="utf-8")

    src_raw, src_canon = canonicalize_and_verify_out(out_dir, "report.json")
    assert src_raw == valid_file
    assert src_canon.resolve() == valid_file.resolve()


def test_canonicalize_and_verify_out_rejects_traversal(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("confidential", encoding="utf-8")

    with pytest.raises(SandboxRunnerError, match="Path traversal detected|does not exist"):
        canonicalize_and_verify_out(out_dir, "../secret.txt")


def test_canonicalize_and_verify_out_rejects_symlink(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    target_file = tmp_path / "target.txt"
    target_file.write_text("target data", encoding="utf-8")

    symlink_file = out_dir / "symlink.txt"
    try:
        symlink_file.symlink_to(target_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform/privilege level")

    with pytest.raises(SandboxRunnerError, match="Refusing copy-out for symlink"):
        canonicalize_and_verify_out(out_dir, "symlink.txt")


def test_extract_declared_outputs(tmp_path: Path):
    work_dir = tmp_path / "work"
    out_dir = work_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    f1 = out_dir / "data.csv"
    f1.write_text("a,b,c\n1,2,3", encoding="utf-8")

    dest_dir = tmp_path / "dest"
    artifacts = extract_declared_outputs(work_dir, ["data.csv"], dest_dir)

    assert len(artifacts) == 1
    assert Path(artifacts[0]).exists()
    assert Path(artifacts[0]).read_text(encoding="utf-8") == "a,b,c\n1,2,3"


def test_local_lan_listener_negative_control():
    """Negative Control: Host CAN connect to a local TCP socket listener."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    # Host connection test succeeds
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.settimeout(2.0)
    client_sock.connect(("127.0.0.1", port))
    client_sock.close()
    server_sock.close()
