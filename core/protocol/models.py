# GENERATED FILE — DO NOT EDIT MANUALLY
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
