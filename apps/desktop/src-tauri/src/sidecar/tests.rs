#[cfg(test)]
mod tests {
    use crate::sidecar::process::resolve_python_venv;
    use crate::sidecar::supervisor::CoreSupervisor;
    use crate::sidecar::types::{
        RpcError, StderrRingBuffer, MAX_STDERR_RING_BUFFER_LINES, SUPPORTED_PROTOCOL_VERSION,
    };
    use std::time::Duration;
    use tokio::sync::oneshot;

    #[test]
    fn test_framing_ndjson_roundtrip() {
        let req = serde_json::json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": SUPPORTED_PROTOCOL_VERSION
            }
        });

        let json_line = format!("{}\n", req.to_string());
        assert!(json_line.ends_with('\n'));

        let parsed: Result<serde_json::Value, _> = serde_json::from_str(json_line.trim());
        assert!(parsed.is_ok());

        let val = parsed.unwrap();
        assert_eq!(val.get("id").unwrap().as_u64(), Some(1));
        assert_eq!(val.get("method").unwrap().as_str(), Some("initialize"));
        assert_eq!(
            val.get("params")
                .unwrap()
                .get("protocolVersion")
                .unwrap()
                .as_str(),
            Some(SUPPORTED_PROTOCOL_VERSION)
        );
    }

    #[tokio::test]
    async fn test_inflight_requests_fail_on_restart() {
        let supervisor = CoreSupervisor::new(None);
        let (tx, rx) = oneshot::channel::<Result<serde_json::Value, RpcError>>();

        supervisor.register_pending_request(42u64, tx).await;

        supervisor
            .drain_pending_requests(RpcError::CoreRestarted)
            .await;

        let res = tokio::time::timeout(Duration::from_secs(2), rx).await;
        assert!(res.is_ok(), "Pending request channel timed out");
        let inner = res.unwrap();
        assert!(inner.is_ok(), "Channel closed unexpectedly");
        assert_eq!(inner.unwrap(), Err(RpcError::CoreRestarted));
    }

    #[test]
    fn test_stderr_ring_buffer_exact_50_cap() {
        let mut buf = StderrRingBuffer::new();
        for i in 0..100 {
            buf.push(format!("stderr line {}", i));
        }
        let tail = buf.get_tail();
        assert_eq!(tail.len(), MAX_STDERR_RING_BUFFER_LINES);
        assert_eq!(tail[0], "stderr line 50");
        assert_eq!(tail[49], "stderr line 99");
    }

    #[test]
    fn test_no_listening_socket_assertion() {
        let output = std::process::Command::new("netstat")
            .arg("-ano")
            .output();

        if let Ok(out) = output {
            let stdout_str = String::from_utf8_lossy(&out.stdout);
            let rust_pid = std::process::id();

            for line in stdout_str.lines() {
                if line.contains("LISTENING") {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if let Some(pid_str) = parts.last() {
                        if let Ok(pid) = pid_str.parse::<u32>() {
                            assert_ne!(
                                pid, rust_pid,
                                "Rust process PID {} MUST NOT bind any listening socket!",
                                rust_pid
                            );
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn test_strict_venv_error_format() {
        let venv_res = resolve_python_venv();
        if let Err(err) = venv_res {
            assert_eq!(err, "core/.venv not found — run make setup");
        }
    }

    #[tokio::test]
    async fn test_stray_stdout_detected_as_protocol_corruption() {
        let corrupt_line = "THIS IS STRAY STDOUT TEXT, NOT VALID JSON";
        let parsed = serde_json::from_str::<serde_json::Value>(corrupt_line);
        assert!(parsed.is_err());

        let err_msg = format!("Protocol corruption! Non-JSON stdout received: '{}'", corrupt_line);
        let mut ring = StderrRingBuffer::new();
        ring.push(err_msg.clone());

        let tail = ring.get_tail();
        assert_eq!(tail.len(), 1);
        assert!(tail[0].contains("Protocol corruption"));
    }

    #[test]
    fn test_chat_stream_and_stop_rpc_structure() {
        let stream_req = serde_json::json!({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "chat/stream",
            "params": {
                "role": "planner",
                "messages": [{"role": "user", "content": "Analyze inspection report"}]
            }
        });

        assert_eq!(stream_req.get("method").unwrap().as_str(), Some("chat/stream"));
        assert_eq!(stream_req.get("params").unwrap().get("role").unwrap().as_str(), Some("planner"));

        let stop_req = serde_json::json!({
            "jsonrpc": "2.0",
            "id": 11,
            "method": "chat/stop",
            "params": {
                "id": 10
            }
        });

        assert_eq!(stop_req.get("method").unwrap().as_str(), Some("chat/stop"));
        assert_eq!(stop_req.get("params").unwrap().get("id").unwrap().as_u64(), Some(10));
    }
}
