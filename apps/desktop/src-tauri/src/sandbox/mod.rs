pub mod linux;
pub mod windows;

use async_trait::async_trait;
use crate::protocol::{SandboxExecParams, SandboxExecResult};
use tauri::AppHandle;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum SandboxError {
    #[error("Sandbox launcher initialization error: {0}")]
    InitError(String),
    #[error("Sandbox execution error: {0}")]
    ExecError(String),
    #[error("Path security / traversal error: {0}")]
    PathError(String),
    #[error("Execution timed out after {0}s")]
    Timeout(u32),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

#[async_trait]
pub trait SandboxLauncher: Send + Sync {
    async fn run(
        &self,
        params: SandboxExecParams,
        app_handle: Option<AppHandle>,
    ) -> Result<SandboxExecResult, SandboxError>;
}

pub fn create_launcher() -> Box<dyn SandboxLauncher> {
    #[cfg(target_os = "linux")]
    {
        Box::new(linux::BubblewrapLauncher::new())
    }
    #[cfg(windows)]
    {
        Box::new(windows::WindowsAppContainerLauncher::new())
    }
    #[cfg(not(any(target_os = "linux", windows)))]
    {
        panic!("Unsupported operating system for sandbox runner");
    }
}
