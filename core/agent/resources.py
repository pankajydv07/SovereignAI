"""Resource extraction and pattern calculation helpers for SWARAJ Policy Engine."""

from typing import Any


def extract_resource_string(name: str, raw_args: dict[str, Any]) -> str:
    """Conservatively extract target resource path or identifier per tool.

    - fs_write / fs_read / fs_delete / fs_edit -> target file path
    - generate_document / render_deliverable -> output filename or path
    - calc_exec / code_exec / sandbox_exec / bash -> command line or script hash
    - kb_search / doc_summarise -> <unscoped> (conservative)
    - fallback -> <unscoped> (conservative, never matches generic path patterns)
    """
    if not isinstance(raw_args, dict):
        return "<unscoped>"

    if name in ("fs_write", "fs_read", "fs_delete", "fs_edit"):
        res = (
            raw_args.get("path")
            or raw_args.get("filePath")
            or raw_args.get("file_path")
            or raw_args.get("target_path")
            or raw_args.get("targetPath")
        )
        return str(res).strip() if res else "<unscoped>"

    if name in ("generate_document", "render_deliverable"):
        res = (
            raw_args.get("output_filename")
            or raw_args.get("outputFilename")
            or raw_args.get("output_path")
            or raw_args.get("outputPath")
            or raw_args.get("filename")
            or raw_args.get("path")
        )
        return str(res).strip() if res else "<unscoped>"

    if name in ("code_exec", "sandbox_exec", "calc_exec", "bash", "exec"):
        cmd = raw_args.get("command")
        if cmd:
            if isinstance(cmd, list):
                return " ".join(str(c) for c in cmd)
            return str(cmd).strip()
        script = raw_args.get("script") or raw_args.get("code")
        if script:
            return f"script:{hash(str(script)) & 0xFFFFFFFF:08x}"
        return "<inline_exec>"

    res = (
        raw_args.get("path")
        or raw_args.get("filePath")
        or raw_args.get("file_path")
        or raw_args.get("target_path")
        or raw_args.get("targetPath")
        or raw_args.get("output_filename")
        or raw_args.get("filename")
    )
    if res:
        return str(res).strip()

    return "<unscoped>"


def compute_default_resource_pattern(resource: str) -> str:
    """Compute default scoping pattern (parent directory or project glob)."""
    res_norm = resource.strip().replace("\\", "/")
    if not res_norm or res_norm.startswith("<") or "/" not in res_norm:
        return "**"
    parts = res_norm.rsplit("/", 1)
    parent = parts[0]
    return f"{parent}/**" if parent else "**"
