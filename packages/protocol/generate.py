#!/usr/bin/env python3
"""Protocol Code Generator for SWARAJ.

Reads JSON Schema definitions from packages/protocol/schema and generates:
- core/protocol/models.py (Pydantic v2)
- apps/desktop/src-tauri/src/protocol.rs (serde Rust structs)
- apps/desktop/src/protocol.ts (TypeScript definitions + Zod schemas)
"""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

PYTHON_TARGET = ROOT_DIR / "core" / "protocol" / "models.py"
RUST_TARGET = ROOT_DIR / "apps" / "desktop" / "src-tauri" / "src" / "protocol.rs"
TS_TARGET = ROOT_DIR / "apps" / "desktop" / "src" / "protocol.ts"

PYTHON_CONTENT = '''# GENERATED FILE — DO NOT EDIT MANUALLY
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


class ProjectInfo(ProtocolBaseModel):
    id: str
    name: str
    path: str
    created_at_ms: int = Field(alias="createdAtMs")
    updated_at_ms: int = Field(alias="updatedAtMs")
    exists: bool = True


class SessionInfo(ProtocolBaseModel):
    session_id: str = Field(alias="sessionId")
    project_id: str = Field(alias="projectId")
    title: str
    status: str
    created_at_ms: int = Field(alias="createdAtMs")
    updated_at_ms: int = Field(alias="updatedAtMs")


class SessionEvent(ProtocolBaseModel):
    session_id: str = Field(alias="sessionId")
    seq: int
    event_type: str = Field(alias="eventType")
    payload: dict[str, Any]
    payload_version: int = Field(default=1, alias="payloadVersion")
    created_at_ms: int = Field(alias="createdAtMs")


class FileNode(ProtocolBaseModel):
    name: str
    path: str
    is_dir: bool = Field(alias="isDir")
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    is_capped: bool | None = Field(default=None, alias="isCapped")
    total_entries: int | None = Field(default=None, alias="totalEntries")


class SandboxExecParams(ProtocolBaseModel):
    run_id: str = Field(alias="runId")
    command: list[str]
    work_dir: str | None = Field(default=None, alias="workDir")
    timeout_s: int = Field(default=60, alias="timeoutS")
    env: dict[str, str] = Field(default_factory=dict)
    declared_outputs: list[str] = Field(default_factory=list, alias="declaredOutputs")


class SandboxExecResult(ProtocolBaseModel):
    run_id: str = Field(alias="runId")
    exit_code: int = Field(alias="exitCode")
    stdout_tail: list[str] = Field(default_factory=list, alias="stdoutTail")
    stderr_tail: list[str] = Field(default_factory=list, alias="stderrTail")
    duration_ms: int = Field(alias="durationMs")
    timed_out: bool = Field(alias="timedOut")
    output_artifacts: list[str] = Field(default_factory=list, alias="outputArtifacts")


PermissionOption = Literal["allow_once", "allow_session", "always_allow", "deny"]


class PermissionRequestParams(ProtocolBaseModel):
    request_id: str = Field(alias="requestId")
    tool: str
    side_effect: str = Field(alias="sideEffect")
    description: str
    resource: str | None = None
    resource_pattern: str | None = Field(default=None, alias="resourcePattern")
    options: list[PermissionOption] = Field(default_factory=list)
    diff: DiffContent | None = None


class PermissionResponseParams(ProtocolBaseModel):
    request_id: str = Field(alias="requestId")
    selected_option: PermissionOption = Field(alias="selectedOption")
    resource_pattern: str | None = Field(default=None, alias="resourcePattern")


class ChatRoutingParams(ProtocolBaseModel):
    session_id: str = Field(alias="sessionId")
    project_id: str = Field(alias="projectId")
    prompt: str
    task_class: str = Field(alias="taskClass")
    model_tag: str = Field(alias="modelTag")
    confidence: float
    reasoning: str | None = None


class PlanRunParams(ProtocolBaseModel):
    session_id: str = Field(alias="sessionId")
    project_id: str = Field(alias="projectId")
    project_path: str | None = Field(default=None, alias="projectPath")
    db_path: str | None = Field(default=None, alias="dbPath")
    steps: list[PlanStep] = Field(default_factory=list)
'''

RUST_CONTENT = '''// GENERATED FILE — DO NOT EDIT MANUALLY
// Source: packages/protocol/schema/*.json
// Run `make protocol` to regenerate.

use serde::{Deserialize, Serialize};

pub const PROTOCOL_VERSION: &str = "2026-03-01";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProtocolMessage {
    pub jsonrpc: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
    pub method: String,
    pub params: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum CoreState {
    Connecting,
    Ready {
        version: String,
        protocol_version: String,
    },
    Restarting {
        attempt: u32,
    },
    Error {
        message: String,
    },
    Failed {
        reason: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        stderr_tail: Option<Vec<String>>,
    },
    Disconnected,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InitializeParams {
    pub protocol_version: String,
    pub capabilities: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InitializeResult {
    pub protocol_version: String,
    pub capabilities: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ToolCallStatus {
    Pending,
    InProgress,
    Completed,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ToolKind {
    Read,
    Edit,
    Delete,
    Move,
    Search,
    Execute,
    Think,
    Fetch,
    Other,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum StopReason {
    EndTurn,
    MaxTokens,
    MaxTurnRequests,
    Refusal,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolCallUpdate {
    pub tool_call_id: String,
    pub name: String,
    pub kind: ToolKind,
    pub status: ToolCallStatus,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PermissionOption {
    AllowOnce,
    AllowSession,
    AlwaysAllow,
    Deny,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiffContent {
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub old_text: Option<String>,
    pub new_text: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TerminalContent {
    pub terminal_id: String,
    pub data: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PermissionRequestParams {
    pub request_id: String,
    pub tool: String,
    pub side_effect: String,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resource: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resource_pattern: Option<String>,
    pub options: Vec<PermissionOption>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub diff: Option<DiffContent>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PermissionResponseParams {
    pub request_id: String,
    pub selected_option: PermissionOption,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resource_pattern: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProvenanceMeta {
    pub field: String,
    pub confidence: f64,
    pub page: i64,
    pub bbox: (f64, f64, f64, f64),
    pub extractor: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MakerCheckerMeta {
    pub maker: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub checker: Option<String>,
    pub status: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeliverableMeta {
    pub r#type: String,
    pub draft: bool,
    pub parameters: serde_json::Value,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub citations: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SwarajMeta {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provenance: Option<ProvenanceMeta>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub maker_checker: Option<MakerCheckerMeta>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deliverable: Option<DeliverableMeta>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlanStep {
    pub step_index: i64,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub side_effect: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub requires_approval: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum SessionUpdatePayload {
    ToolCall {
        #[serde(rename = "toolCall")]
        tool_call: ToolCallUpdate,
    },
    Plan {
        steps: Vec<PlanStep>,
    },
    Diff {
        diff: DiffContent,
    },
    Terminal {
        terminal: TerminalContent,
    },
    StateChange {
        state: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionUpdateNotification {
    pub session_id: String,
    pub update: SessionUpdatePayload,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub meta: Option<SwarajMeta>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectInfo {
    pub id: String,
    pub name: String,
    pub path: String,
    pub created_at_ms: i64,
    pub updated_at_ms: i64,
    #[serde(default = "default_true")]
    pub exists: bool,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionInfo {
    pub session_id: String,
    pub project_id: String,
    pub title: String,
    pub status: String,
    pub created_at_ms: i64,
    pub updated_at_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionEvent {
    pub session_id: String,
    pub seq: i64,
    pub event_type: String,
    pub payload: serde_json::Value,
    pub payload_version: i64,
    pub created_at_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FileNode {
    pub name: String,
    pub path: String,
    pub is_dir: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_capped: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total_entries: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SandboxExecParams {
    pub run_id: String,
    pub command: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub work_dir: Option<String>,
    #[serde(default = "default_timeout")]
    pub timeout_s: u32,
    #[serde(default, skip_serializing_if = "std::collections::HashMap::is_empty")]
    pub env: std::collections::HashMap<String, String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub declared_outputs: Vec<String>,
}

fn default_timeout() -> u32 {
    60
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SandboxExecResult {
    pub run_id: String,
    pub exit_code: i32,
    pub stdout_tail: Vec<String>,
    pub stderr_tail: Vec<String>,
    pub duration_ms: u64,
    pub timed_out: bool,
    pub output_artifacts: Vec<String>,
}



#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatRoutingParams {
    pub session_id: String,
    pub project_id: String,
    pub prompt: String,
    pub task_class: String,
    pub model_tag: String,
    pub confidence: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reasoning: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlanRunParams {
    pub session_id: String,
    pub project_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub project_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub db_path: Option<String>,
    pub steps: Vec<PlanStep>,
}
'''

TS_CONTENT = '''// GENERATED FILE — DO NOT EDIT MANUALLY
// Source: packages/protocol/schema/*.json
// Run `make protocol` to regenerate.

import { z } from "zod";

export const PROTOCOL_VERSION = "2026-03-01";

export const ProtocolMessageSchema = z.object({
  jsonrpc: z.literal("2.0"),
  id: z.string().optional(),
  method: z.string(),
  params: z.record(z.string(), z.unknown()).default({}),
});
export type ProtocolMessage = z.infer<typeof ProtocolMessageSchema>;

export const CoreStateSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("connecting") }),
  z.object({
    type: z.literal("ready"),
    version: z.string(),
    protocol_version: z.string(),
  }),
  z.object({ type: z.literal("restarting"), attempt: z.number().int() }),
  z.object({ type: z.literal("error"), message: z.string() }),
  z.object({
    type: z.literal("failed"),
    reason: z.string(),
    stderr_tail: z.array(z.string()).optional(),
  }),
  z.object({ type: z.literal("disconnected") }),
]);
export type CoreState = z.infer<typeof CoreStateSchema>;

export const InitializeParamsSchema = z.object({
  protocolVersion: z.string(),
  capabilities: z.array(z.string()),
});
export type InitializeParams = z.infer<typeof InitializeParamsSchema>;

export const InitializeResultSchema = z.object({
  protocolVersion: z.string(),
  capabilities: z.array(z.string()),
});
export type InitializeResult = z.infer<typeof InitializeResultSchema>;

export const ToolCallStatusSchema = z.enum(["pending", "in_progress", "completed", "failed"]);
export type ToolCallStatus = z.infer<typeof ToolCallStatusSchema>;

export const ToolKindSchema = z.enum([
  "read",
  "edit",
  "delete",
  "move",
  "search",
  "execute",
  "think",
  "fetch",
  "other",
]);
export type ToolKind = z.infer<typeof ToolKindSchema>;

export const StopReasonSchema = z.enum([
  "end_turn",
  "max_tokens",
  "max_turn_requests",
  "refusal",
  "cancelled",
]);
export type StopReason = z.infer<typeof StopReasonSchema>;

export const ToolCallUpdateSchema = z.object({
  toolCallId: z.string(),
  name: z.string(),
  kind: ToolKindSchema,
  status: ToolCallStatusSchema,
  input: z.record(z.string(), z.unknown()).optional(),
  output: z.record(z.string(), z.unknown()).optional(),
  error: z.string().optional(),
});
export type ToolCallUpdate = z.infer<typeof ToolCallUpdateSchema>;

export const PermissionOptionSchema = z.enum([
  "allow_once",
  "allow_session",
  "always_allow",
  "deny",
]);
export type PermissionOption = z.infer<typeof PermissionOptionSchema>;

export const DiffContentSchema = z.object({
  path: z.string(),
  oldText: z.string().optional(),
  newText: z.string(),
});
export type DiffContent = z.infer<typeof DiffContentSchema>;

export const TerminalContentSchema = z.object({
  terminalId: z.string(),
  data: z.string(),
});
export type TerminalContent = z.infer<typeof TerminalContentSchema>;

export const PermissionRequestParamsSchema = z.object({
  requestId: z.string(),
  tool: z.string(),
  sideEffect: z.string(),
  description: z.string(),
  resource: z.string().optional(),
  resourcePattern: z.string().optional(),
  options: z.array(PermissionOptionSchema),
  diff: DiffContentSchema.optional(),
});
export type PermissionRequestParams = z.infer<typeof PermissionRequestParamsSchema>;

export const PermissionResponseParamsSchema = z.object({
  requestId: z.string(),
  selectedOption: PermissionOptionSchema,
  resourcePattern: z.string().optional(),
});
export type PermissionResponseParams = z.infer<typeof PermissionResponseParamsSchema>;

export const ProvenanceMetaSchema = z.object({
  field: z.string(),
  confidence: z.number(),
  page: z.number().int(),
  bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  extractor: z.string(),
});
export type ProvenanceMeta = z.infer<typeof ProvenanceMetaSchema>;

export const MakerCheckerMetaSchema = z.object({
  maker: z.string(),
  checker: z.string().optional(),
  status: z.enum(["pending", "approved", "rejected"]),
  timestamp: z.string(),
});
export type MakerCheckerMeta = z.infer<typeof MakerCheckerMetaSchema>;

export const DeliverableMetaSchema = z.object({
  type: z.enum([
    "approval_note",
    "inspection_summary",
    "review_deck",
    "cost_sheet",
    "engineering_calculation",
  ]),
  draft: z.boolean(),
  parameters: z.record(z.string(), z.unknown()),
  citations: z.array(z.string()).default([]),
});
export type DeliverableMeta = z.infer<typeof DeliverableMetaSchema>;

export const SwarajMetaSchema = z.object({
  provenance: ProvenanceMetaSchema.optional(),
  makerChecker: MakerCheckerMetaSchema.optional(),
  deliverable: DeliverableMetaSchema.optional(),
});
export type SwarajMeta = z.infer<typeof SwarajMetaSchema>;

export const PlanStepSchema = z.object({
  stepIndex: z.number().int(),
  description: z.string(),
  tool: z.string().optional(),
  sideEffect: z.string().optional(),
  requiresApproval: z.boolean().optional(),
});
export type PlanStep = z.infer<typeof PlanStepSchema>;

export const ToolCallUpdatePayloadSchema = z.object({
  type: z.literal("tool_call"),
  toolCall: ToolCallUpdateSchema,
});

export const PlanUpdatePayloadSchema = z.object({
  type: z.literal("plan"),
  steps: z.array(PlanStepSchema),
});

export const DiffUpdatePayloadSchema = z.object({
  type: z.literal("diff"),
  diff: DiffContentSchema,
});

export const TerminalUpdatePayloadSchema = z.object({
  type: z.literal("terminal"),
  terminal: TerminalContentSchema,
});

export const StateChangeUpdatePayloadSchema = z.object({
  type: z.literal("state_change"),
  state: z.string(),
});

export const SessionUpdatePayloadSchema = z.discriminatedUnion("type", [
  ToolCallUpdatePayloadSchema,
  PlanUpdatePayloadSchema,
  DiffUpdatePayloadSchema,
  TerminalUpdatePayloadSchema,
  StateChangeUpdatePayloadSchema,
]);
export type SessionUpdatePayload = z.infer<typeof SessionUpdatePayloadSchema>;

export const SessionUpdateNotificationSchema = z.object({
  sessionId: z.string(),
  update: SessionUpdatePayloadSchema,
  meta: SwarajMetaSchema.optional(),
});
export type SessionUpdateNotification = z.infer<typeof SessionUpdateNotificationSchema>;

export const ProjectInfoSchema = z.object({
  id: z.string(),
  name: z.string(),
  path: z.string(),
  createdAtMs: z.number(),
  updatedAtMs: z.number(),
  exists: z.boolean().default(true),
});
export type ProjectInfo = z.infer<typeof ProjectInfoSchema>;

export const SessionInfoSchema = z.object({
  sessionId: z.string(),
  projectId: z.string(),
  title: z.string(),
  status: z.string(),
  createdAtMs: z.number(),
  updatedAtMs: z.number(),
});
export type SessionInfo = z.infer<typeof SessionInfoSchema>;

export const SessionEventSchema = z.object({
  sessionId: z.string(),
  seq: z.number().int(),
  eventType: z.string(),
  payload: z.record(z.string(), z.unknown()),
  payloadVersion: z.number().int(),
  createdAtMs: z.number(),
});
export type SessionEvent = z.infer<typeof SessionEventSchema>;

export const FileNodeSchema = z.object({
  name: z.string(),
  path: z.string(),
  isDir: z.boolean(),
  sizeBytes: z.number().optional(),
  isCapped: z.boolean().optional(),
  totalEntries: z.number().optional(),
});
export type FileNode = z.infer<typeof FileNodeSchema>;

export const SandboxExecParamsSchema = z.object({
  runId: z.string(),
  command: z.array(z.string()),
  workDir: z.string().optional(),
  timeoutS: z.number().int().default(60),
  env: z.record(z.string(), z.string()).default({}),
  declaredOutputs: z.array(z.string()).default([]),
});
export type SandboxExecParams = z.infer<typeof SandboxExecParamsSchema>;

export const SandboxExecResultSchema = z.object({
  runId: z.string(),
  exitCode: z.number().int(),
  stdoutTail: z.array(z.string()),
  stderrTail: z.array(z.string()),
  durationMs: z.number().int(),
  timedOut: z.boolean(),
  outputArtifacts: z.array(z.string()),
});
export type SandboxExecResult = z.infer<typeof SandboxExecResultSchema>;

export const ChatRoutingParamsSchema = z.object({
  sessionId: z.string(),
  projectId: z.string(),
  prompt: z.string(),
  taskClass: z.string(),
  modelTag: z.string(),
  confidence: z.number(),
  reasoning: z.string().optional(),
});
export type ChatRoutingParams = z.infer<typeof ChatRoutingParamsSchema>;

export const PlanRunParamsSchema = z.object({
  sessionId: z.string(),
  projectId: z.string(),
  projectPath: z.string().optional(),
  dbPath: z.string().optional(),
  steps: z.array(PlanStepSchema),
});
export type PlanRunParams = z.infer<typeof PlanRunParamsSchema>;
'''


def main() -> None:
    PYTHON_TARGET.parent.mkdir(parents=True, exist_ok=True)
    RUST_TARGET.parent.mkdir(parents=True, exist_ok=True)
    TS_TARGET.parent.mkdir(parents=True, exist_ok=True)

    PYTHON_TARGET.write_text(PYTHON_CONTENT, encoding="utf-8")
    RUST_TARGET.write_text(RUST_CONTENT, encoding="utf-8")
    TS_TARGET.write_text(TS_CONTENT, encoding="utf-8")

    print(f"Generated: {PYTHON_TARGET.relative_to(ROOT_DIR)}")
    print(f"Generated: {RUST_TARGET.relative_to(ROOT_DIR)}")
    print(f"Generated: {TS_TARGET.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
