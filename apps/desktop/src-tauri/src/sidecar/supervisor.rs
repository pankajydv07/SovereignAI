use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tauri::Emitter;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::{mpsc, oneshot, Mutex};

use crate::sidecar::process::{
    attach_windows_job_object, configure_platform_child_guard, resolve_python_venv,
};
use crate::sidecar::types::{
    CoreState, RpcError, StderrRingBuffer, MAX_RESTART_ATTEMPTS, SUPPORTED_PROTOCOL_VERSION,
};

pub struct CoreSupervisor {
    state: Arc<Mutex<CoreState>>,
    child_handle: Arc<Mutex<Option<Child>>>,
    app_handle: Option<tauri::AppHandle>,
    request_id_counter: AtomicU64,
    stderr_ring_buffer: Arc<Mutex<StderrRingBuffer>>,
    pending_requests:
        Arc<Mutex<HashMap<u64, oneshot::Sender<Result<serde_json::Value, RpcError>>>>>,
    write_tx: Arc<Mutex<Option<mpsc::Sender<String>>>>,
}

impl CoreSupervisor {
    pub fn new(app_handle: Option<tauri::AppHandle>) -> Self {
        Self {
            state: Arc::new(Mutex::new(CoreState::Disconnected)),
            child_handle: Arc::new(Mutex::new(None)),
            app_handle,
            request_id_counter: AtomicU64::new(1),
            stderr_ring_buffer: Arc::new(Mutex::new(StderrRingBuffer::new())),
            pending_requests: Arc::new(Mutex::new(HashMap::new())),
            write_tx: Arc::new(Mutex::new(None)),
        }
    }

    pub async fn get_state(&self) -> CoreState {
        self.state.lock().await.clone()
    }

    pub async fn get_stderr_tail(&self) -> Vec<String> {
        self.stderr_ring_buffer.lock().await.get_tail()
    }

    fn emit_state_change(&self, state: &CoreState) {
        if let Some(ref app) = self.app_handle {
            let _ = app.emit("core-status-changed", state);
        }
    }

    pub async fn send_rpc(
        &self,
        method: &str,
        params: serde_json::Value,
    ) -> Result<u64, RpcError> {
        let id = self.request_id_counter.fetch_add(1, Ordering::SeqCst);
        let req = serde_json::json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        });

        let sender = {
            let guard = self.write_tx.lock().await;
            guard.clone().ok_or(RpcError::NotReady)?
        };

        sender
            .send(format!("{}\n", req.to_string()))
            .await
            .map_err(|_| RpcError::CoreRestarted)?;

        Ok(id)
    }

    pub async fn send_chat_stream(
        &self,
        role: String,
        messages: serde_json::Value,
    ) -> Result<u64, RpcError> {
        self.send_rpc(
            "chat/stream",
            serde_json::json!({ "role": role, "messages": messages }),
        )
        .await
    }

    pub async fn stop_chat_stream(&self, stream_id: u64) -> Result<(), RpcError> {
        self.send_rpc("chat/stop", serde_json::json!({ "id": stream_id }))
            .await?;
        Ok(())
    }

    pub async fn start_supervision(self: Arc<Self>) {
        tokio::spawn(async move {
            let mut attempt = 0;
            loop {
                attempt += 1;

                if attempt > MAX_RESTART_ATTEMPTS {
                    let stderr_tail = self.stderr_ring_buffer.lock().await.get_tail();
                    let failed_state = CoreState::Failed {
                        reason: format!(
                            "Agent Core supervisor reached max restart limit ({})",
                            MAX_RESTART_ATTEMPTS
                        ),
                        stderr_tail,
                    };
                    {
                        let mut s = self.state.lock().await;
                        *s = failed_state.clone();
                    }
                    self.emit_state_change(&failed_state);
                    eprintln!("[sidecar] Max restart limit reached. Halting supervision.");
                    break;
                }

                {
                    let mut s = self.state.lock().await;
                    *s = CoreState::Restarting { attempt };
                    self.emit_state_change(&*s);
                }

                match self.run_instance().await {
                    Ok(_) => {
                        eprintln!("[sidecar] Core process ended gracefully");
                        attempt = 0;
                    }
                    Err(err) => {
                        eprintln!(
                            "[sidecar] Core process instance error (attempt {}/{}): {}",
                            attempt, MAX_RESTART_ATTEMPTS, err
                        );
                        self.stderr_ring_buffer
                            .lock()
                            .await
                            .push(format!("[sidecar] Instance error: {}", err));
                    }
                }

                // Drain in-flight requests on process crash/exit
                self.drain_pending_requests(RpcError::CoreRestarted).await;

                // Restock/restart backoff delay (1s)
                tokio::time::sleep(Duration::from_millis(1000)).await;
            }
        });
    }

    pub async fn drain_pending_requests(&self, err: RpcError) {
        let mut pending = self.pending_requests.lock().await;
        for (_, sender) in pending.drain() {
            let _ = sender.send(Err(err.clone()));
        }
        if let Some(ref app) = self.app_handle {
            let _ = app.emit(
                "chat-stream-interrupted",
                serde_json::json!({ "reason": "core_restarted" }),
            );
        }
    }

    pub async fn register_pending_request(
        &self,
        id: u64,
        sender: oneshot::Sender<Result<serde_json::Value, RpcError>>,
    ) {
        self.pending_requests.lock().await.insert(id, sender);
    }

    #[cfg(debug_assertions)]
    pub async fn kill_core_process(&self) -> Result<(), String> {
        let mut guard = self.child_handle.lock().await;
        if let Some(ref mut child) = *guard {
            child.kill().await.map_err(|e| e.to_string())?;
            eprintln!("[sidecar] Core process forcibly killed for debug testing");
            Ok(())
        } else {
            Err("No active core process running".into())
        }
    }

    async fn run_instance(&self) -> Result<(), String> {
        let python_bin = resolve_python_venv()?;
        let workspace_root = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        let main_py = workspace_root.join("core").join("core").join("main.py");

        if !main_py.exists() {
            return Err(format!("Python entrypoint missing at {:?}", main_py));
        }

        eprintln!("[sidecar] Spawning core: {:?} {:?}", python_bin, main_py);

        let mut command = Command::new(&python_bin);
        command
            .arg(&main_py)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        configure_platform_child_guard(&mut command);

        let mut child = command.spawn().map_err(|e| format!("Spawn failed: {}", e))?;

        attach_windows_job_object(&child);

        let stdin = child.stdin.take().ok_or("Failed to open stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to open stdout")?;
        let stderr = child.stderr.take().ok_or("Failed to open stderr")?;

        {
            let mut guard = self.child_handle.lock().await;
            *guard = Some(child);
        }

        // Channel for writing commands to child stdin
        let (write_tx, mut write_rx) = mpsc::channel::<String>(32);
        {
            let mut guard = self.write_tx.lock().await;
            *guard = Some(write_tx.clone());
        }
        let mut stdin_writer = stdin;

        tokio::spawn(async move {
            while let Some(msg) = write_rx.recv().await {
                if stdin_writer.write_all(msg.as_bytes()).await.is_err() {
                    break;
                }
                if stdin_writer.flush().await.is_err() {
                    break;
                }
            }
        });

        // Stderr reader task & ring buffer logging
        let stderr_ring = self.stderr_ring_buffer.clone();
        tokio::spawn(async move {
            let mut reader = BufReader::new(stderr).lines();
            while let Ok(Some(line)) = reader.next_line().await {
                eprintln!("[core-stderr] {}", line);
                stderr_ring.lock().await.push(line);
            }
        });

        // Stdout reader task with request correlation & stray stdout corruption detection
        let pending_map = self.pending_requests.clone();
        let stderr_ring_corrupt = self.stderr_ring_buffer.clone();
        let app_handle_opt = self.app_handle.clone();
        tokio::spawn(async move {
            let mut reader = BufReader::new(stdout).lines();
            while let Ok(Some(line)) = reader.next_line().await {
                let trimmed = line.trim();
                if trimmed.is_empty() {
                    continue;
                }

                match serde_json::from_str::<serde_json::Value>(trimmed) {
                    Ok(json_val) => {
                        if let Some(method) = json_val.get("method").and_then(|m| m.as_str()) {
                            if let Some(ref app) = app_handle_opt {
                                if method == "chat/token" {
                                    let _ = app.emit("chat-token-received", json_val.get("params"));
                                } else if method == "chat/interrupted" {
                                    let _ = app.emit("chat-stream-interrupted", json_val.get("params"));
                                }
                            }
                        } else if let Some(id) = json_val.get("id").and_then(|i| i.as_u64()) {
                            let mut map = pending_map.lock().await;
                            if let Some(tx) = map.remove(&id) {
                                if let Some(err_obj) = json_val.get("error") {
                                    let code = err_obj
                                        .get("code")
                                        .and_then(|c| c.as_i64())
                                        .unwrap_or(-1);
                                    let msg = err_obj
                                        .get("message")
                                        .and_then(|m| m.as_str())
                                        .unwrap_or("RPC Error");
                                    let _ = tx.send(Err(RpcError::RemoteError {
                                        code,
                                        message: msg.to_string(),
                                    }));
                                } else if let Some(res) = json_val.get("result") {
                                    if let Some(ref app) = app_handle_opt {
                                        let _ = app.emit(
                                            "chat-stream-completed",
                                            serde_json::json!({ "id": id, "result": res }),
                                        );
                                    }
                                    let _ = tx.send(Ok(res.clone()));
                                }
                            } else if let Some(res) = json_val.get("result") {
                                if let Some(ref app) = app_handle_opt {
                                    let _ = app.emit(
                                        "chat-stream-completed",
                                        serde_json::json!({ "id": id, "result": res }),
                                    );
                                }
                            }
                        }
                    }
                    Err(_) => {
                        let err_msg = format!(
                            "Protocol corruption! Non-JSON stdout received: '{}'",
                            trimmed
                        );
                        eprintln!("[sidecar] {}", err_msg);
                        stderr_ring_corrupt.lock().await.push(err_msg);
                    }
                }
            }
        });

        // Step 1: Handshake with protocolVersion negotiation
        let init_id = self.request_id_counter.fetch_add(1, Ordering::SeqCst);
        let init_req = serde_json::json!({
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "protocolVersion": SUPPORTED_PROTOCOL_VERSION
            }
        });

        let (init_tx, init_rx) = oneshot::channel();
        {
            self.pending_requests.lock().await.insert(init_id, init_tx);
        }

        write_tx
            .send(format!("{}\n", init_req.to_string()))
            .await
            .map_err(|_| "Failed to write initialize to stdin stream")?;

        let init_result = tokio::time::timeout(Duration::from_secs(4), init_rx)
            .await
            .map_err(|_| "Initialize request timed out after 4s")?
            .map_err(|_| "Initialize response channel closed")??;

        let version = init_result
            .get("version")
            .and_then(|v| v.as_str())
            .ok_or_else(|| "Initialize response missing 'version'".to_string())?
            .to_string();

        let negotiated_proto = init_result
            .get("protocolVersion")
            .and_then(|v| v.as_str())
            .unwrap_or(SUPPORTED_PROTOCOL_VERSION)
            .to_string();

        let ready_state = CoreState::Ready {
            version,
            protocol_version: negotiated_proto,
        };
        {
            let mut s = self.state.lock().await;
            *s = ready_state.clone();
        }
        self.emit_state_change(&ready_state);

        // Step 2: Heartbeat loop (ping every 3s)
        let mut interval = tokio::time::interval(Duration::from_secs(3));
        loop {
            interval.tick().await;
            let ping_id = self.request_id_counter.fetch_add(1, Ordering::SeqCst);
            let ping_req = serde_json::json!({
                "jsonrpc": "2.0",
                "id": ping_id,
                "method": "ping"
            });

            let (ping_tx, ping_rx) = oneshot::channel();
            {
                self.pending_requests.lock().await.insert(ping_id, ping_tx);
            }

            if write_tx
                .send(format!("{}\n", ping_req.to_string()))
                .await
                .is_err()
            {
                break;
            }

            let ping_result = tokio::time::timeout(Duration::from_secs(2), ping_rx).await;
            if ping_result.is_err() || ping_result.unwrap().is_err() {
                eprintln!("[sidecar] Core ping heartbeat lost or timed out");
                break;
            }
        }

        // Multi-Stage Graceful Shutdown: send shutdown RPC -> wait up to 2s -> SIGTERM -> SIGKILL
        let shutdown_id = self.request_id_counter.fetch_add(1, Ordering::SeqCst);
        let shutdown_req = serde_json::json!({
            "jsonrpc": "2.0",
            "id": shutdown_id,
            "method": "shutdown"
        });
        let (sht_tx, sht_rx) = oneshot::channel();
        {
            self.pending_requests.lock().await.insert(shutdown_id, sht_tx);
        }

        let _ = write_tx.send(format!("{}\n", shutdown_req.to_string())).await;
        let _ = tokio::time::timeout(Duration::from_secs(2), sht_rx).await;

        {
            let mut guard = self.child_handle.lock().await;
            if let Some(mut child) = guard.take() {
                let _ = child.kill().await;
            }
        }

        Err("Sidecar session terminated".into())
    }
}
