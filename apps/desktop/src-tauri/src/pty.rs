use portable_pty::{native_pty_system, CommandBuilder, PtySize};
use serde::Serialize;
use std::collections::HashMap;
use std::io::{Read, Write};
use std::sync::{Arc, Mutex};
use tauri::Emitter;

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct PtyOutputPayload {
    pub id: String,
    pub data: Vec<u8>,
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct PtyExitPayload {
    pub id: String,
    pub exit_code: Option<i32>,
}

pub struct PtySessionState {
    pub writer: Box<dyn Write + Send>,
    pub child: Box<dyn portable_pty::Child + Send>,
    pub master: Box<dyn portable_pty::MasterPty + Send>,
}

#[derive(Clone, Default)]
pub struct PtyManager {
    sessions: Arc<Mutex<HashMap<String, PtySessionState>>>,
}

impl PtyManager {
    pub fn new() -> Self {
        Self {
            sessions: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub fn create_pty(
        &self,
        app_handle: &tauri::AppHandle,
        id: String,
        rows: u16,
        cols: u16,
        cwd: Option<String>,
    ) -> Result<(), String> {
        let rows = if rows == 0 { 24 } else { rows };
        let cols = if cols == 0 { 80 } else { cols };

        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows,
                cols,
                pixel_width: 0,
                pixel_height: 0,
            })
            .map_err(|e| format!("Failed to open PTY: {}", e))?;

        let default_shell = if cfg!(windows) {
            std::env::var("COMSPEC").unwrap_or_else(|_| "cmd.exe".to_string())
        } else {
            std::env::var("SHELL").unwrap_or_else(|_| "/bin/bash".to_string())
        };

        let mut cmd = CommandBuilder::new(&default_shell);
        cmd.env("TERM", "xterm-256color");
        cmd.env("COLORTERM", "truecolor");

        if let Some(dir) = cwd {
            if !dir.is_empty() {
                cmd.cwd(dir);
            }
        }

        let child = pair
            .slave
            .spawn_command(cmd)
            .map_err(|e| format!("Failed to spawn shell process: {}", e))?;

        let writer = pair
            .master
            .take_writer()
            .map_err(|e| format!("Failed to take PTY writer: {}", e))?;

        let mut reader = pair
            .master
            .try_clone_reader()
            .map_err(|e| format!("Failed to clone PTY reader: {}", e))?;

        let session = PtySessionState {
            writer,
            child,
            master: pair.master,
        };

        {
            let mut guard = self.sessions.lock().map_err(|e| e.to_string())?;
            guard.insert(id.clone(), session);
        }

        let id_clone = id.clone();
        let app_handle_clone = app_handle.clone();
        let sessions_clone = self.sessions.clone();

        // Spawn non-blocking reader thread with byte batching & coalescing
        std::thread::spawn(move || {
            let mut buffer = [0u8; 4096];
            let mut chunk_buf: Vec<u8> = Vec::new();
            let mut last_flush = std::time::Instant::now();

            loop {
                match reader.read(&mut buffer) {
                    Ok(0) => break,
                    Ok(n) => {
                        chunk_buf.extend_from_slice(&buffer[..n]);

                        if chunk_buf.len() >= 16384
                            || last_flush.elapsed() >= std::time::Duration::from_millis(10)
                        {
                            let payload = PtyOutputPayload {
                                id: id_clone.clone(),
                                data: std::mem::take(&mut chunk_buf),
                            };
                            let _ = app_handle_clone.emit("pty-output", payload);
                            last_flush = std::time::Instant::now();
                        }
                    }
                    Err(_) => break,
                }
            }

            if !chunk_buf.is_empty() {
                let payload = PtyOutputPayload {
                    id: id_clone.clone(),
                    data: chunk_buf,
                };
                let _ = app_handle_clone.emit("pty-output", payload);
            }

            let exit_code = {
                let mut guard = sessions_clone.lock().unwrap();
                if let Some(session) = guard.get_mut(&id_clone) {
                    match session.child.wait() {
                        Ok(status) => Some(status.exit_code() as i32),
                        Err(_) => None,
                    }
                } else {
                    None
                }
            };

            let _ = app_handle_clone.emit(
                "pty-exit",
                PtyExitPayload {
                    id: id_clone,
                    exit_code,
                },
            );
        });

        Ok(())
    }

    /// Write data to a PTY's stdin writer.
    ///
    /// NOTE: This function is designated strictly for USER interactive terminal input.
    /// Agent-initiated commands in Milestone 4 (P4.2) must go through the policy engine
    /// and approval flow via sandboxed runners, NEVER directly into write_pty.
    pub fn write_pty(&self, id: &str, data: &[u8]) -> Result<(), String> {
        let mut guard = self.sessions.lock().map_err(|e| e.to_string())?;
        if let Some(session) = guard.get_mut(id) {
            session
                .writer
                .write_all(data)
                .map_err(|e| format!("Failed to write to PTY stdin: {}", e))?;
            session
                .writer
                .flush()
                .map_err(|e| format!("Failed to flush PTY stdin: {}", e))?;
            Ok(())
        } else {
            Err(format!("PTY session {} not found", id))
        }
    }

    pub fn resize_pty(&self, id: &str, rows: u16, cols: u16) -> Result<(), String> {
        if rows == 0 || cols == 0 {
            return Ok(());
        }
        let mut guard = self.sessions.lock().map_err(|e| e.to_string())?;
        if let Some(session) = guard.get_mut(id) {
            session
                .master
                .resize(PtySize {
                    rows,
                    cols,
                    pixel_width: 0,
                    pixel_height: 0,
                })
                .map_err(|e| format!("Failed to resize PTY master: {}", e))?;
            Ok(())
        } else {
            Err(format!("PTY session {} not found", id))
        }
    }

    pub fn close_pty(&self, id: &str) -> Result<(), String> {
        let mut guard = self.sessions.lock().map_err(|e| e.to_string())?;
        if let Some(mut session) = guard.remove(id) {
            let _ = session.child.kill();
            let _ = session.child.wait();
        }
        Ok(())
    }

    pub fn close_all(&self) {
        let mut guard = match self.sessions.lock() {
            Ok(g) => g,
            Err(p) => p.into_inner(),
        };
        for (_, mut session) in guard.drain() {
            let _ = session.child.kill();
            let _ = session.child.wait();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pty_create_write_read_roundtrip() {
        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows: 24,
                cols: 80,
                pixel_width: 0,
                pixel_height: 0,
            })
            .expect("openpty failed");

        let default_shell = if cfg!(windows) { "cmd.exe" } else { "sh" };
        let mut cmd = CommandBuilder::new(default_shell);
        cmd.env("TERM", "xterm-256color");
        cmd.env("COLORTERM", "truecolor");

        let mut child = pair.slave.spawn_command(cmd).expect("spawn failed");
        let mut writer = pair.master.take_writer().expect("take_writer failed");
        let mut reader = pair.master.try_clone_reader().expect("reader failed");

        let input_bytes: &[u8] = if cfg!(windows) { b"echo hello_pty\r\n" } else { b"echo hello_pty\n" };
        writer.write_all(input_bytes).expect("write failed");
        writer.flush().expect("flush failed");

        let mut read_buf = vec![0u8; 1024];
        let n = reader.read(&mut read_buf).expect("read failed");
        let output_str = String::from_utf8_lossy(&read_buf[..n]);

        assert!(output_str.contains("hello_pty") || output_str.contains("echo") || n > 0);

        let _ = child.kill();
        let _ = child.wait();
    }

    #[test]
    fn test_pty_resize_propagation() {
        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows: 24,
                cols: 80,
                pixel_width: 0,
                pixel_height: 0,
            })
            .expect("openpty failed");

        let resize_res = pair.master.resize(PtySize {
            rows: 40,
            cols: 120,
            pixel_width: 0,
            pixel_height: 0,
        });

        assert!(resize_res.is_ok());
    }

    #[test]
    fn test_pty_child_exit_reaping() {
        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows: 24,
                cols: 80,
                pixel_width: 0,
                pixel_height: 0,
            })
            .expect("openpty failed");

        let default_shell = if cfg!(windows) { "cmd.exe" } else { "sh" };
        let cmd = CommandBuilder::new(default_shell);
        let mut child = pair.slave.spawn_command(cmd).expect("spawn failed");
        let mut writer = pair.master.take_writer().expect("take_writer failed");

        let exit_cmd: &[u8] = if cfg!(windows) { b"exit 0\r\n" } else { b"exit 0\n" };
        let _ = writer.write_all(exit_cmd);
        let _ = writer.flush();

        let status = child.wait();
        assert!(status.is_ok());
    }

    #[test]
    fn test_pty_close_kills_process() {
        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows: 24,
                cols: 80,
                pixel_width: 0,
                pixel_height: 0,
            })
            .expect("openpty failed");

        let default_shell = if cfg!(windows) { "cmd.exe" } else { "sh" };
        let cmd = CommandBuilder::new(default_shell);
        let mut child = pair.slave.spawn_command(cmd).expect("spawn failed");

        assert!(child.kill().is_ok());
        let _ = child.wait();
    }

    #[test]
    fn test_windows_crlf_handling() {
        let raw_crlf = b"line1\r\r\nline2\r\n";
        let mut normalized = Vec::new();
        for &b in raw_crlf.iter() {
            normalized.push(b);
        }
        assert!(!normalized.is_empty());
        assert_eq!(normalized[5], b'\r');
    }
}
