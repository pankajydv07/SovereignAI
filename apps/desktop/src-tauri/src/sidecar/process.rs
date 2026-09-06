use std::path::PathBuf;
use tokio::process::{Child, Command};

pub fn resolve_python_venv() -> Result<PathBuf, String> {
    let workspace_root = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    
    #[cfg(windows)]
    let venv_python = workspace_root
        .join("core")
        .join(".venv")
        .join("Scripts")
        .join("python.exe");

    #[cfg(not(windows))]
    let venv_python = workspace_root
        .join("core")
        .join(".venv")
        .join("bin")
        .join("python");

    if venv_python.exists() {
        Ok(venv_python)
    } else {
        Err("core/.venv not found — run make setup".into())
    }
}

pub fn configure_platform_child_guard(command: &mut Command) {
    #[cfg(target_os = "linux")]
    unsafe {
        command.pre_exec(|| {
            libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL);
            Ok(())
        });
    }
    let _ = command;
}

#[cfg(windows)]
pub fn attach_windows_job_object(child: &Child) {
    use windows_sys::Win32::Foundation::HANDLE;
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectA, SetInformationJobObject,
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        JobObjectExtendedLimitInformation,
    };

    if let Some(raw_handle) = child.raw_handle() {
        unsafe {
            let job = CreateJobObjectA(std::ptr::null(), std::ptr::null());
            if job != std::ptr::null_mut() {
                let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                SetInformationJobObject(
                    job,
                    JobObjectExtendedLimitInformation,
                    &info as *const _ as *const _,
                    std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
                );
                AssignProcessToJobObject(job, raw_handle as HANDLE);
            }
        }
    }
}

#[cfg(not(windows))]
pub fn attach_windows_job_object(_child: &Child) {}
