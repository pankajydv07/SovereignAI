"""Python Sandbox Execution Client & Isolated Runtime Manager.

Interfaces with Rust SandboxLauncher (`sandbox/exec`) over JSON-RPC
and enforces post-exit output verification and path traversal bounds.
"""

from pathlib import Path
import os
import shutil
import tempfile
from typing import Any

from protocol.models import SandboxExecParams, SandboxExecResult


class SandboxRunnerError(Exception):
    """Raised when sandbox setup, execution, or output validation fails."""


def canonicalize_and_verify_out(base_out: Path, declared_rel: str) -> tuple[Path, Path]:
    """Verify that a declared output path resides strictly inside base_out without symlinks."""
    raw_target = (base_out / declared_rel).resolve()
    base_canonical = base_out.resolve()

    # Symlink / junction check
    target_unresolved = base_out / declared_rel
    if target_unresolved.is_symlink():
        raise SandboxRunnerError(f"Refusing copy-out for symlink: {declared_rel}")

    if not raw_target.exists():
        raise SandboxRunnerError(f"Declared output file does not exist: {declared_rel}")

    try:
        raw_target.relative_to(base_canonical)
    except ValueError as exc:
        raise SandboxRunnerError(f"Path traversal detected in declared output: {declared_rel}") from exc

    return target_unresolved, raw_target


def prepare_sandbox_env(work_dir: Path, custom_env: dict[str, str] | None = None) -> dict[str, str]:
    """Build sanitized environment dict for sandboxed Python execution."""
    work_str = str(work_dir.resolve())
    env = {
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": work_str,
        "HOME": work_str,
        "USERPROFILE": work_str,
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if custom_env:
        env.update(custom_env)
    return env


def extract_declared_outputs(
    work_dir: Path,
    declared_outputs: list[str],
    destination_dir: Path,
) -> list[str]:
    """Extract declared output files post-exit with traversal and symlink checks."""
    out_dir = work_dir / "out"
    if not out_dir.exists():
        return []

    copied_artifacts: list[str] = []
    destination_dir.mkdir(parents=True, exist_ok=True)

    for declared in declared_outputs:
        try:
            src_raw, src_canon = canonicalize_and_verify_out(out_dir, declared)
            dest_file = (destination_dir / declared).resolve()
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(src_canon, dest_file)
            copied_artifacts.append(str(dest_file))
        except SandboxRunnerError as e:
            print(f"[sandbox_copyout_warning] {e}")

    return copied_artifacts
