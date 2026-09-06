// GENERATED FILE — DO NOT EDIT MANUALLY
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
