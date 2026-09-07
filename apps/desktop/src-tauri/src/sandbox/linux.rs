use super::{SandboxError, SandboxLauncher};
use crate::protocol::{SandboxExecParams, SandboxExecResult};
use async_trait::async_trait;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Instant;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;
use tokio::time::{timeout, Duration};

pub struct BubblewrapLauncher;

impl BubblewrapLauncher {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BubblewrapLauncher {
    fn default() -> Self {
        Self::new()
    }
}

fn canonicalize_and_verify_out(
    base_out: &Path,
    declared_rel: &str,
) -> Result<(PathBuf, PathBuf), SandboxError> {
    let raw_target = base_out.join(declared_rel);
    if !raw_target.exists() {
        return Err(SandboxError::PathError(format!(
            "Declared output file does not exist: {}",
            declared_rel
        )));
    }

    let meta = fs::symlink_metadata(&raw_target)?;
    if meta.file_type().is_symlink() {
        return Err(SandboxError::PathError(format!(
            "Refusing copy-out for symlink: {}",
            declared_rel
        )));
    }

    let canonical = raw_target.canonicalize()?;
    let canonical_base = base_out.canonicalize()?;

    if !canonical.starts_with(&canonical_base) {
        return Err(SandboxError::PathError(format!(
            "Path traversal detected in declared output: {}",
            declared_rel
        )));
    }

    Ok((raw_target, canonical))
}

#[async_trait]
impl SandboxLauncher for BubblewrapLauncher {
    async fn run(
        &self,
        params: SandboxExecParams,
        app_handle: Option<AppHandle>,
    ) -> Result<SandboxExecResult, SandboxError> {
        let start_time = Instant::now();
        let timeout_s = if params.timeout_s == 0 {
            60
        } else {
            params.timeout_s
        };

        // Use supplied work_dir if exists, else create temporary work directory under system temp dir
        let work_dir = if let Some(ref wd) = params.work_dir {
            let p = PathBuf::from(wd);
            if p.exists() {
                p
            } else {
                std::env::temp_dir().join(format!("swaraj_sandbox_{}", params.run_id))
            }
        } else {
            std::env::temp_dir().join(format!("swaraj_sandbox_{}", params.run_id))
        };
        let out_dir = work_dir.join("out");
        fs::create_dir_all(&out_dir)?;

        let python_runtime = PathBuf::from("runtime").join("sandbox-python");

        // Build bwrap command
        let mut cmd_args: Vec<String> = vec![
            "--unshare-net".into(),
            "--unshare-pid".into(),
            "--unshare-ipc".into(),
            "--unshare-uts".into(),
            "--unshare-cgroup".into(),
            "--new-session".into(),
            "--clearenv".into(),
            "--cap-drop".into(),
            "ALL".into(),
            "--die-with-parent".into(),
            "--ro-bind".into(),
            "/usr".into(),
            "/usr".into(),
            "--ro-bind".into(),
            "/lib".into(),
            "/lib".into(),
            "--ro-bind-try".into(),
            "/lib64".into(),
            "/lib64".into(),
            "--ro-bind".into(),
            "/bin".into(),
            "/bin".into(),
            "--proc".into(),
            "/proc".into(),
            "--dev".into(),
            "/dev".into(),
        ];

        if python_runtime.exists() {
            if let Ok(canon) = python_runtime.canonicalize() {
                let canon_str = canon.to_string_lossy().to_string();
                cmd_args.push("--ro-bind".into());
                cmd_args.push(canon_str.clone());
                cmd_args.push(canon_str);
            }
        }

        let work_dir_str = work_dir.to_string_lossy().to_string();
        cmd_args.push("--bind".into());
        cmd_args.push(work_dir_str.clone());
        cmd_args.push("/work".into());

        // Environment variables via --setenv
        cmd_args.extend(vec![
            "--setenv".into(),
            "MPLBACKEND".into(),
            "Agg".into(),
            "--setenv".into(),
            "MPLCONFIGDIR".into(),
            "/work".into(),
            "--setenv".into(),
            "HOME".into(),
            "/work".into(),
            "--setenv".into(),
            "USERPROFILE".into(),
            "/work".into(),
            "--setenv".into(),
            "PYTHONNOUSERSITE".into(),
            "1".into(),
            "--setenv".into(),
            "PYTHONDONTWRITEBYTECODE".into(),
            "1".into(),
        ]);

        for (k, v) in &params.env {
            cmd_args.push("--setenv".into());
            cmd_args.push(k.clone());
            cmd_args.push(v.clone());
        }

        // Target executable & args
        cmd_args.extend(params.command.clone());

        // Wrap with systemd-run if available, or direct bwrap
        let mut final_cmd = if Path::new("/usr/bin/systemd-run").exists()
            || Path::new("/bin/systemd-run").exists()
        {
            let mut sys_cmd = Command::new("systemd-run");
            sys_cmd.args([
                "--user",
                "--scope",
                "-p",
                "MemoryMax=2G",
                "-p",
                "CPUQuota=50%",
                "--",
                "bwrap",
            ]);
            sys_cmd.args(cmd_args);
            sys_cmd
        } else {
            let mut bwrap_cmd = Command::new("bwrap");
            bwrap_cmd.args(cmd_args);
            bwrap_cmd
        };

        final_cmd.stdout(std::process::Stdio::piped());
        final_cmd.stderr(std::process::Stdio::piped());

        let mut child = match final_cmd.spawn() {
            Ok(c) => c,
            Err(e) => {
                let _ = fs::remove_dir_all(&work_dir);
                return Err(SandboxError::ExecError(format!(
                    "Failed to spawn bwrap sandbox process: {}",
                    e
                )));
            }
        };

        let stdout = child.stdout.take().expect("Failed to open stdout");
        let stderr = child.stderr.take().expect("Failed to open stderr");

        let run_id = params.run_id.clone();
        let event_name = format!("sandbox-output::{}", run_id);

        let app_handle_stdout = app_handle.clone();
        let event_name_stdout = event_name.clone();

        let stdout_handle = tokio::spawn(async move {
            let mut reader = BufReader::new(stdout).lines();
            let mut tail = Vec::new();
            while let Ok(Some(line)) = reader.next_line().await {
                if let Some(ref handle) = app_handle_stdout {
                    let _ = handle.emit(&event_name_stdout, line.clone());
                }
                tail.push(line);
                if tail.len() > 200 {
                    tail.remove(0);
                }
            }
            tail
        });

        let app_handle_stderr = app_handle.clone();
        let event_name_stderr = event_name.clone();

        let stderr_handle = tokio::spawn(async move {
            let mut reader = BufReader::new(stderr).lines();
            let mut tail = Vec::new();
            while let Ok(Some(line)) = reader.next_line().await {
                if let Some(ref handle) = app_handle_stderr {
                    let _ = handle.emit(&event_name_stderr, line.clone());
                }
                tail.push(line);
                if tail.len() > 200 {
                    tail.remove(0);
                }
            }
            tail
        });

        let exec_result = timeout(Duration::from_secs(timeout_s as u64), child.wait()).await;

        let (exit_code, timed_out) = match exec_result {
            Ok(Ok(status)) => (status.code().unwrap_or(-1), false),
            Ok(Err(_)) => (-1, false),
            Err(_) => {
                let _ = child.kill().await;
                (-1, true)
            }
        };

        let stdout_tail = stdout_handle.await.unwrap_or_default();
        let stderr_tail = stderr_handle.await.unwrap_or_default();
        let duration_ms = start_time.elapsed().as_millis() as u64;

        // POST-EXIT COPY-OUT HARDENING
        let mut output_artifacts = Vec::new();
        if exit_code == 0 && !timed_out {
            for declared in &params.declared_outputs {
                if let Ok((src_path, _)) = canonicalize_and_verify_out(&out_dir, declared) {
                    let dest_path = work_dir.join("extracted").join(declared);
                    if let Some(parent) = dest_path.parent() {
                        let _ = fs::create_dir_all(parent);
                    }
                    if fs::copy(&src_path, &dest_path).is_ok() {
                        output_artifacts.push(dest_path.to_string_lossy().to_string());
                    }
                }
            }
        }

        // Cleanup temporary work dir
        let _ = fs::remove_dir_all(&work_dir);

        Ok(SandboxExecResult {
            run_id: params.run_id,
            exit_code,
            stdout_tail,
            stderr_tail,
            duration_ms,
            timed_out,
            output_artifacts,
        })
    }
}
