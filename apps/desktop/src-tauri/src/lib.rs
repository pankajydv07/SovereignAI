pub mod protocol;
pub mod pty;
pub mod sidecar;
pub mod sovereignty;
pub mod workspace;

use protocol::{FileNode, ProjectInfo};
use pty::PtyManager;
use sidecar::{CoreState, CoreSupervisor};
use sovereignty::{EgressEvent, SovereigntyState, SovereigntyStatus};
use std::fs;
use std::path::PathBuf;
use std::sync::Arc;
use tauri::{Manager, State};

struct AppState {
    supervisor: Arc<CoreSupervisor>,
    pty_manager: PtyManager,
    sovereignty: SovereigntyState,
    app_data_dir: Option<PathBuf>,
}

fn get_settings_path(app_data_dir: &Option<PathBuf>) -> Option<PathBuf> {
    app_data_dir.as_ref().map(|p| p.join("settings.json"))
}

fn load_recent_projects_internal(app_data_dir: &Option<PathBuf>) -> Vec<ProjectInfo> {
    let path = match get_settings_path(app_data_dir) {
        Some(p) => p,
        None => return Vec::new(),
    };

    if !path.exists() {
        return Vec::new();
    }

    let content = match fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };

    let mut projects: Vec<ProjectInfo> = serde_json::from_str(&content).unwrap_or_default();
    for p in &mut projects {
        p.exists = std::path::Path::new(&p.path).exists();
    }
    projects
}

fn save_recent_projects_internal(app_data_dir: &Option<PathBuf>, projects: &[ProjectInfo]) {
    if let Some(path) = get_settings_path(app_data_dir) {
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(json) = serde_json::to_string_pretty(projects) {
            let _ = fs::write(path, json);
        }
    }
}

#[tauri::command]
async fn get_system_info() -> Result<String, String> {
    Ok("SWARAJ Core Shell v0.1.0".into())
}

#[tauri::command]
async fn get_core_status(state: State<'_, AppState>) -> Result<CoreState, String> {
    Ok(state.supervisor.get_state().await)
}

#[tauri::command]
async fn get_core_stderr_tail(state: State<'_, AppState>) -> Result<Vec<String>, String> {
    Ok(state.supervisor.get_stderr_tail().await)
}

#[tauri::command]
async fn send_chat_message(
    state: State<'_, AppState>,
    role: String,
    messages: serde_json::Value,
) -> Result<u64, String> {
    state
        .supervisor
        .send_chat_stream(role, messages)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn cancel_chat_stream(
    state: State<'_, AppState>,
    stream_id: u64,
) -> Result<(), String> {
    state
        .supervisor
        .stop_chat_stream(stream_id)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn invoke_core_rpc(
    state: State<'_, AppState>,
    method: String,
    params: serde_json::Value,
) -> Result<serde_json::Value, String> {
    state
        .supervisor
        .send_rpc_request(&method, params)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_recent_projects(state: State<'_, AppState>) -> Result<Vec<ProjectInfo>, String> {
    Ok(load_recent_projects_internal(&state.app_data_dir))
}

#[tauri::command]
async fn add_recent_project(
    state: State<'_, AppState>,
    project: ProjectInfo,
) -> Result<Vec<ProjectInfo>, String> {
    let mut projects = load_recent_projects_internal(&state.app_data_dir);
    projects.retain(|p| p.id != project.id && p.path != project.path);
    projects.insert(0, project);
    save_recent_projects_internal(&state.app_data_dir, &projects);
    Ok(projects)
}

#[tauri::command]
async fn remove_recent_project(
    state: State<'_, AppState>,
    id: String,
) -> Result<Vec<ProjectInfo>, String> {
    let mut projects = load_recent_projects_internal(&state.app_data_dir);
    projects.retain(|p| p.id != id);
    save_recent_projects_internal(&state.app_data_dir, &projects);
    Ok(projects)
}

#[tauri::command]
async fn read_workspace_dir(
    workspace_root: String,
    rel_path: Option<String>,
) -> Result<Vec<FileNode>, String> {
    workspace::read_workspace_dir(&workspace_root, rel_path.as_deref())
}

#[tauri::command]
async fn create_pty(
    app_handle: tauri::AppHandle,
    state: State<'_, AppState>,
    id: String,
    rows: u16,
    cols: u16,
    cwd: Option<String>,
) -> Result<(), String> {
    state
        .pty_manager
        .create_pty(&app_handle, id, rows, cols, cwd)
}

#[tauri::command]
async fn write_pty(
    state: State<'_, AppState>,
    id: String,
    data: Vec<u8>,
) -> Result<(), String> {
    state.pty_manager.write_pty(&id, &data)
}

#[tauri::command]
async fn resize_pty(
    state: State<'_, AppState>,
    id: String,
    rows: u16,
    cols: u16,
) -> Result<(), String> {
    state.pty_manager.resize_pty(&id, rows, cols)
}

#[tauri::command]
async fn close_pty(
    state: State<'_, AppState>,
    id: String,
) -> Result<(), String> {
    state.pty_manager.close_pty(&id)
}

#[tauri::command]
async fn get_sovereignty_status(
    state: State<'_, AppState>,
) -> Result<SovereigntyStatus, String> {
    Ok(state.sovereignty.get_status())
}

#[tauri::command]
async fn get_egress_events(
    state: State<'_, AppState>,
) -> Result<Vec<EgressEvent>, String> {
    Ok(state.sovereignty.get_events())
}

#[tauri::command]
async fn acknowledge_egress_event(
    state: State<'_, AppState>,
    id: String,
) -> Result<bool, String> {
    Ok(state.sovereignty.acknowledge_event(&id))
}

#[cfg(debug_assertions)]
#[tauri::command]
async fn kill_core_process(state: State<'_, AppState>) -> Result<(), String> {
    state.supervisor.kill_core_process().await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let pty_manager = PtyManager::new();
    let pty_manager_clone = pty_manager.clone();

    tauri::Builder::default()
        .setup(move |app| {
            let app_data_dir = app.path().app_data_dir().ok();
            let sovereignty = SovereigntyState::new(app_data_dir.clone());
            sovereignty.start_monitor_loop(app.handle().clone());

            let supervisor = Arc::new(CoreSupervisor::new(Some(app.handle().clone())));
            let supervisor_clone = supervisor.clone();

            app.manage(AppState {
                supervisor,
                pty_manager: pty_manager_clone,
                sovereignty,
                app_data_dir,
            });

            tauri::async_runtime::spawn(async move {
                supervisor_clone.start_supervision().await;
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_system_info,
            get_core_status,
            get_core_stderr_tail,
            send_chat_message,
            cancel_chat_stream,
            invoke_core_rpc,
            get_recent_projects,
            add_recent_project,
            remove_recent_project,
            read_workspace_dir,
            create_pty,
            write_pty,
            resize_pty,
            close_pty,
            get_sovereignty_status,
            get_egress_events,
            acknowledge_egress_event,
            #[cfg(debug_assertions)]
            kill_core_process
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(state) = app_handle.try_state::<AppState>() {
                    state.pty_manager.close_all();
                }
            }
        });
}
