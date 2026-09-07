use super::{SandboxError, SandboxLauncher};
use crate::protocol::{SandboxExecParams, SandboxExecResult};
use async_trait::async_trait;
use std::ffi::OsStr;
use std::fs;
use std::os::windows::ffi::OsStrExt;
use std::path::{Path, PathBuf};
use std::time::Instant;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::time::{timeout, Duration};

#[cfg(windows)]
use windows_sys::Win32::Foundation::{
    CloseHandle, HANDLE, INVALID_HANDLE_VALUE,
};
#[cfg(windows)]
use windows_sys::Win32::Security::{
    FreeSid, DACL_SECURITY_INFORMATION, OBJECT_INHERIT_ACE, CONTAINER_INHERIT_ACE,
};
#[cfg(windows)]
use windows_sys::Win32::Security::Isolation::{
    CreateAppContainerProfile, DeriveAppContainerSidFromAppContainerName,
};
#[cfg(windows)]
use windows_sys::Win32::Security::Authorization::{
    SetEntriesInAclW, SetNamedSecurityInfoW, EXPLICIT_ACCESS_W, GRANT_ACCESS,
    SE_FILE_OBJECT, TRUSTEE_IS_SID, TRUSTEE_IS_WELL_KNOWN_GROUP, TRUSTEE_W,
};
#[cfg(windows)]
use windows_sys::Win32::Storage::FileSystem::{
    FILE_ALL_ACCESS, FILE_GENERIC_EXECUTE, FILE_GENERIC_READ,
};
#[cfg(windows)]
use windows_sys::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, SetInformationJobObject,
    TerminateJobObject, JOBOBJECT_CPU_RATE_CONTROL_INFORMATION,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_CPU_RATE_CONTROL_ENABLE,
    JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP, JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
    JOB_OBJECT_LIMIT_JOB_MEMORY, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JobObjectCpuRateControlInformation, JobObjectExtendedLimitInformation,
};

#[cfg(windows)]
#[derive(Clone, Copy, Debug)]
struct SendHandle(HANDLE);
#[cfg(windows)]
unsafe impl Send for SendHandle {}
#[cfg(windows)]
unsafe impl Sync for SendHandle {}

pub struct WindowsAppContainerLauncher;

impl WindowsAppContainerLauncher {
    pub fn new() -> Self {
        Self
    }
}

impl Default for WindowsAppContainerLauncher {
    fn default() -> Self {
        Self::new()
    }
}

fn to_wide(s: &str) -> Vec<u16> {
    OsStr::new(s).encode_wide().chain(std::iter::once(0)).collect()
}

#[cfg(windows)]
fn grant_sid_access(path: &Path, psid: *mut std::ffi::c_void, access_mask: u32) -> Result<(), String> {
    let wide_path = to_wide(&path.to_string_lossy());
    unsafe {
        let mut explicit_access = EXPLICIT_ACCESS_W {
            grfAccessPermissions: access_mask,
            grfAccessMode: GRANT_ACCESS,
            grfInheritance: OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE,
            Trustee: TRUSTEE_W {
                pMultipleTrustee: std::ptr::null_mut(),
                MultipleTrusteeOperation: 0,
                TrusteeForm: TRUSTEE_IS_SID,
                TrusteeType: TRUSTEE_IS_WELL_KNOWN_GROUP,
                ptstrName: psid as *mut u16,
            },
        };

        let mut p_new_acl = std::ptr::null_mut();
        let res = SetEntriesInAclW(1, &mut explicit_access, std::ptr::null_mut(), &mut p_new_acl);
        if res != 0 {
            return Err(format!("SetEntriesInAclW failed with error code {}", res));
        }

        let set_res = SetNamedSecurityInfoW(
            wide_path.as_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            p_new_acl,
            std::ptr::null_mut(),
        );

        if set_res != 0 {
            return Err(format!("SetNamedSecurityInfoW failed with error code {}", set_res));
        }
    }
    Ok(())
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
impl SandboxLauncher for WindowsAppContainerLauncher {
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

        // Use supplied work_dir if exists, else create temporary work directory under system temp directory
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
        if python_runtime.exists() {
            let _ = fs::create_dir_all(&python_runtime);
        }

        #[cfg(windows)]
        unsafe {
            let profile_name = to_wide("SwarajSandboxProfile");
            let display_name = to_wide("SWARAJ Sandbox Execution Profile");

            let err_already_exists_hr = 0x800700B7u32 as i32;

            let mut psid: *mut std::ffi::c_void = std::ptr::null_mut();
            let hr: i32 = CreateAppContainerProfile(
                profile_name.as_ptr(),
                display_name.as_ptr(),
                display_name.as_ptr(),
                std::ptr::null_mut(),
                0,
                &mut psid,
            );

            // 0x800700B7 is ERROR_ALREADY_EXISTS as HRESULT
            if hr != 0 && hr != err_already_exists_hr {
                // Try deriving SID if profile already exists
                let derive_res = DeriveAppContainerSidFromAppContainerName(
                    profile_name.as_ptr(),
                    &mut psid,
                );
                if derive_res != 0 {
                    let _ = fs::remove_dir_all(&work_dir);
                    return Err(SandboxError::InitError(format!(
                        "Failed to obtain AppContainer SID: HRESULT 0x{:X}",
                        hr
                    )));
                }
            } else if hr == err_already_exists_hr || psid.is_null() {
                let derive_res = DeriveAppContainerSidFromAppContainerName(
                    profile_name.as_ptr(),
                    &mut psid,
                );
                if derive_res != 0 || psid.is_null() {
                    let _ = fs::remove_dir_all(&work_dir);
                    return Err(SandboxError::InitError(
                        "Failed to derive AppContainer SID for existing profile".into(),
                    ));
                }
            }

            // Grant Container SID full access to work_dir and read+exec to python_runtime
            let _ = grant_sid_access(&work_dir, psid, FILE_ALL_ACCESS);
            if python_runtime.exists() {
                let _ = grant_sid_access(&python_runtime, psid, FILE_GENERIC_READ | FILE_GENERIC_EXECUTE);
            }
            FreeSid(psid);
        }

        #[cfg(windows)]
        let (exit_code, stdout_tail, stderr_tail, duration_ms, timed_out) = {
            let h_job = SendHandle(unsafe {
                let h = CreateJobObjectW(std::ptr::null_mut(), std::ptr::null());
                if h.is_null() || h == INVALID_HANDLE_VALUE {
                    let _ = fs::remove_dir_all(&work_dir);
                    return Err(SandboxError::InitError("Failed to create JobObject".into()));
                }

                let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
                limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_JOB_MEMORY
                    | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                    | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                limits.JobMemoryLimit = 2 * 1024 * 1024 * 1024; // 2 GB
                limits.BasicLimitInformation.ActiveProcessLimit = 16;

                SetInformationJobObject(
                    h,
                    JobObjectExtendedLimitInformation,
                    &limits as *const _ as *const _,
                    std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
                );

                let mut cpu_limits: JOBOBJECT_CPU_RATE_CONTROL_INFORMATION = std::mem::zeroed();
                cpu_limits.ControlFlags =
                    JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP;
                cpu_limits.Anonymous.CpuRate = 5000; // 50%

                SetInformationJobObject(
                    h,
                    JobObjectCpuRateControlInformation,
                    &cpu_limits as *const _ as *const _,
                    std::mem::size_of::<JOBOBJECT_CPU_RATE_CONTROL_INFORMATION>() as u32,
                );
                h
            });

            let mut cmd = tokio::process::Command::new(&params.command[0]);
            if params.command.len() > 1 {
                cmd.args(&params.command[1..]);
            }

            cmd.current_dir(&work_dir);
            cmd.env_clear();
            cmd.env("MPLBACKEND", "Agg");
            cmd.env("MPLCONFIGDIR", &work_dir);
            cmd.env("HOME", &work_dir);
            cmd.env("USERPROFILE", &work_dir);
            cmd.env("PYTHONNOUSERSITE", "1");
            cmd.env("PYTHONDONTWRITEBYTECODE", "1");

            for (k, v) in &params.env {
                cmd.env(k, v);
            }

            cmd.stdout(std::process::Stdio::piped());
            cmd.stderr(std::process::Stdio::piped());

            let mut child = match cmd.spawn() {
                Ok(c) => c,
                Err(e) => {
                    unsafe { CloseHandle(h_job.0); }
                    let _ = fs::remove_dir_all(&work_dir);
                    return Err(SandboxError::ExecError(format!(
                        "Failed to spawn process: {}",
                        e
                    )));
                }
            };

            if let Some(raw_h) = child.raw_handle() {
                unsafe { AssignProcessToJobObject(h_job.0, raw_h as HANDLE); }
            }

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
                    unsafe { TerminateJobObject(h_job.0, 1); }
                    let _ = child.kill().await;
                    (-1, true)
                }
            };

            let stdout_tail = stdout_handle.await.unwrap_or_default();
            let stderr_tail = stderr_handle.await.unwrap_or_default();
            let duration_ms = start_time.elapsed().as_millis() as u64;

            unsafe { CloseHandle(h_job.0); }

            (exit_code, stdout_tail, stderr_tail, duration_ms, timed_out)
        };

        #[cfg(not(windows))]
        let (exit_code, stdout_tail, stderr_tail, duration_ms, timed_out) =
            (-1, vec![], vec!["Windows launcher called on non-Windows system".into()], 0, false);

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
