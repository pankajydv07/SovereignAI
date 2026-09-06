# GENERATED FILE — DO NOT EDIT MANUALLY
# Source: packages/protocol/schema/*.json
# Run `make protocol` to regenerate.

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PROTOCOL_VERSION = "2026-03-01"


class ProtocolBaseModel(BaseModel):
    """Base model with camelCase alias generation and populate_by_name."""

    model_config = ConfigDict(
        populate_by_name=True,
    )


class ProtocolMessage(ProtocolBaseModel):
    """Base ACP protocol message container."""

    jsonrpc: Literal["2.0"] = "2.0"
    id: str | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class CoreStateConnecting(ProtocolBaseModel):
    type: Literal["connecting"] = "connecting"


class CoreStateReady(ProtocolBaseModel):
    type: Literal["ready"] = "ready"
    version: str
    protocol_version: str = Field(alias="protocol_version")


class CoreStateRestarting(ProtocolBaseModel):
    type: Literal["restarting"] = "restarting"
    attempt: int


class CoreStateError(ProtocolBaseModel):
    type: Literal["error"] = "error"
    message: str


class CoreStateFailed(ProtocolBaseModel):
    type: Literal["failed"] = "failed"
    reason: str
    stderr_tail: list[str] | None = Field(default=None, alias="stderr_tail")


class CoreStateDisconnected(ProtocolBaseModel):
    type: Literal["disconnected"] = "disconnected"


CoreState = Annotated[
    CoreStateConnecting
    | CoreStateReady
    | CoreStateRestarting
    | CoreStateError
    | CoreStateFailed
    | CoreStateDisconnected,
    Field(discriminator="type"),
]


class InitializeParams(ProtocolBaseModel):
    protocol_version: str = Field(alias="protocolVersion")
    capabilities: list[str] = Field(default_factory=list)


class InitializeResult(ProtocolBaseModel):
    protocol_version: str = Field(alias="protocolVersion")
    capabilities: list[str] = Field(default_factory=list)


ToolCallStatus = Literal["pending", "in_progress", "completed", "failed"]
ToolKind = Literal["read", "edit", "delete", "move", "search", "execute", "think", "fetch", "other"]
StopReason = Literal["end_turn", "max_tokens", "max_turn_requests", "refusal", "cancelled"]


class ToolCallUpdate(ProtocolBaseModel):
    tool_call_id: str = Field(alias="toolCallId")
    name: str
    kind: ToolKind
    status: ToolCallStatus
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: str | None = None


PermissionOption = Literal["allow_once", "allow_session", "always_allow", "deny"]


class DiffContent(ProtocolBaseModel):
    path: str
    old_text: str | None = Field(default=None, alias="oldText")
    new_text: str = Field(alias="newText")


class TerminalContent(ProtocolBaseModel):
    terminal_id: str = Field(alias="terminalId")
    data: str


class PermissionRequestParams(ProtocolBaseModel):
    request_id: str = Field(alias="requestId")
    tool: str
    side_effect: str = Field(alias="sideEffect")
    description: str
    options: list[PermissionOption]
    diff: DiffContent | None = None


class PermissionResponseParams(ProtocolBaseModel):
    request_id: str = Field(alias="requestId")
    selected_option: PermissionOption = Field(alias="selectedOption")


class ProvenanceMeta(ProtocolBaseModel):
    field: str
    confidence: float
    page: int
    bbox: list[float]
    extractor: str


class MakerCheckerMeta(ProtocolBaseModel):
    maker: str
    checker: str | None = None
    status: Literal["pending", "approved", "rejected"]
    timestamp: str


DeliverableType = Literal[
    "approval_note",
    "inspection_summary",
    "review_deck",
    "cost_sheet",
    "engineering_calculation",
]


class DeliverableMeta(ProtocolBaseModel):
    type: DeliverableType
    draft: bool
    parameters: dict[str, Any]
    citations: list[str] = Field(default_factory=list)


class SwarajMeta(ProtocolBaseModel):
    provenance: ProvenanceMeta | None = None
    maker_checker: MakerCheckerMeta | None = Field(default=None, alias="makerChecker")
    deliverable: DeliverableMeta | None = None


class PlanStep(ProtocolBaseModel):
    step_index: int = Field(alias="stepIndex")
    description: str
    tool: str | None = None
    side_effect: str | None = Field(default=None, alias="sideEffect")
    requires_approval: bool | None = Field(default=None, alias="requiresApproval")


class ToolCallUpdatePayload(ProtocolBaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call: ToolCallUpdate = Field(alias="toolCall")


class PlanUpdatePayload(ProtocolBaseModel):
    type: Literal["plan"] = "plan"
    steps: list[PlanStep]


class DiffUpdatePayload(ProtocolBaseModel):
    type: Literal["diff"] = "diff"
    diff: DiffContent


class TerminalUpdatePayload(ProtocolBaseModel):
    type: Literal["terminal"] = "terminal"
    terminal: TerminalContent


class StateChangeUpdatePayload(ProtocolBaseModel):
    type: Literal["state_change"] = "state_change"
    state: str


SessionUpdatePayload = Annotated[
    ToolCallUpdatePayload
    | PlanUpdatePayload
    | DiffUpdatePayload
    | TerminalUpdatePayload
    | StateChangeUpdatePayload,
    Field(discriminator="type"),
]


class SessionUpdateNotification(ProtocolBaseModel):
    session_id: str = Field(alias="sessionId")
    update: SessionUpdatePayload
    meta: SwarajMeta | None = None


class SessionNewParams(ProtocolBaseModel):
    project_id: str = Field(alias="projectId")
    title: str | None = None


class SessionLoadParams(ProtocolBaseModel):
    session_id: str = Field(alias="sessionId")


class SessionResumeParams(ProtocolBaseModel):
    session_id: str = Field(alias="sessionId")


class SessionCloseParams(ProtocolBaseModel):
    session_id: str = Field(alias="sessionId")


class SessionListParams(ProtocolBaseModel):
    project_id: str | None = Field(default=None, alias="projectId")
