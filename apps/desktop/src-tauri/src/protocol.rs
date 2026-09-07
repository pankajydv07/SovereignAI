// GENERATED FILE — DO NOT EDIT MANUALLY
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
