#!/usr/bin/env python3
"""Protocol Code Generator for SWARAJ.

Reads JSON Schema definitions from packages/protocol/schema and generates:
- core/protocol/models.py (Pydantic v2)
- apps/desktop/src-tauri/src/protocol.rs (serde Rust structs)
- apps/desktop/src/protocol.ts (TypeScript definitions)
"""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

PYTHON_TARGET = ROOT_DIR / "core" / "protocol" / "models.py"
RUST_TARGET = ROOT_DIR / "apps" / "desktop" / "src-tauri" / "src" / "protocol.rs"
TS_TARGET = ROOT_DIR / "apps" / "desktop" / "src" / "protocol.ts"

PYTHON_HEADER = '''# GENERATED FILE — DO NOT EDIT MANUALLY
# Source: packages/protocol/schema/*.json
# Run `make protocol` to regenerate.

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProtocolMessage(BaseModel):
    """Base ACP protocol message container."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
'''

RUST_HEADER = '''// GENERATED FILE — DO NOT EDIT MANUALLY
// Source: packages/protocol/schema/*.json
// Run `make protocol` to regenerate.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProtocolMessage {
    pub jsonrpc: String,
    pub id: Option<String>,
    pub method: String,
    pub params: serde_json::Value,
}
'''

TS_HEADER = '''// GENERATED FILE — DO NOT EDIT MANUALLY
// Source: packages/protocol/schema/*.json
// Run `make protocol` to regenerate.

export interface ProtocolMessage {
  jsonrpc: "2.0";
  id?: string;
  method: string;
  params: Record<string, unknown>;
}
'''


def main() -> None:
    PYTHON_TARGET.parent.mkdir(parents=True, exist_ok=True)
    RUST_TARGET.parent.mkdir(parents=True, exist_ok=True)
    TS_TARGET.parent.mkdir(parents=True, exist_ok=True)

    PYTHON_TARGET.write_text(PYTHON_HEADER, encoding="utf-8")
    RUST_TARGET.write_text(RUST_HEADER, encoding="utf-8")
    TS_TARGET.write_text(TS_HEADER, encoding="utf-8")

    print(f"Generated: {PYTHON_TARGET.relative_to(ROOT_DIR)}")
    print(f"Generated: {RUST_TARGET.relative_to(ROOT_DIR)}")
    print(f"Generated: {TS_TARGET.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
