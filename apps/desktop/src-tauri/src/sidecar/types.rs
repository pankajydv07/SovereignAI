use std::collections::VecDeque;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use tokio::time::Duration;

pub const SUPPORTED_PROTOCOL_VERSION: &str = "2024-11-05";
pub const MAX_RESTART_ATTEMPTS: u32 = 5;
pub const MAX_STDERR_RING_BUFFER_LINES: usize = 50;

#[derive(Error, Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum RpcError {
    #[error("Core process restarted while request was in-flight")]
    CoreRestarted,
    #[error("Request timed out after {0:?}")]
    Timeout(Duration),
    #[error("Protocol corruption: non-JSON output on stdout: {0}")]
    ProtocolCorruption(String),
    #[error("RPC error response ({code}): {message}")]
    RemoteError { code: i64, message: String },
    #[error("Initialization error: {0}")]
    InitializationFailed(String),
    #[error("Core process not connected or ready")]
    NotReady,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoreCapabilities {
    pub agent_loop: bool,
    pub tools: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum CoreState {
    Disconnected,
    Connecting,
    Ready { version: String, protocol_version: String },
    Restarting { attempt: u32 },
    Failed { reason: String, stderr_tail: Vec<String> },
}

pub struct StderrRingBuffer {
    buffer: VecDeque<String>,
}

impl StderrRingBuffer {
    pub fn new() -> Self {
        Self {
            buffer: VecDeque::with_capacity(MAX_STDERR_RING_BUFFER_LINES),
        }
    }

    pub fn push(&mut self, line: String) {
        if self.buffer.len() >= MAX_STDERR_RING_BUFFER_LINES {
            self.buffer.pop_front();
        }
        self.buffer.push_back(line);
    }

    pub fn get_tail(&self) -> Vec<String> {
        self.buffer.iter().cloned().collect()
    }
}

impl Default for StderrRingBuffer {
    fn default() -> Self {
        Self::new()
    }
}

impl From<RpcError> for String {
    fn from(err: RpcError) -> Self {
        err.to_string()
    }
}
