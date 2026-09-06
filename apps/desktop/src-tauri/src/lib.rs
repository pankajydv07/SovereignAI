pub mod protocol;
pub mod pty;
pub mod sidecar;
pub mod sovereignty;

use pty::PtyManager;
use sidecar::{CoreState, CoreSupervisor};
use sovereignty::{EgressEvent, SovereigntyState, SovereigntyStatus};
use std::sync::Arc;
use tauri::{Manager, State};

struct AppState {
    supervisor: Arc<CoreSupervisor>,
    pty_manager: PtyManager,
    sovereignty: SovereigntyState,
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

/// Write bytes to PTY stdin.
/// NOTE: Reserved strictly for human USER interactive terminal input.
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
            let sovereignty = SovereigntyState::new(app_data_dir);
            sovereignty.start_monitor_loop(app.handle().clone());

            let supervisor = Arc::new(CoreSupervisor::new(Some(app.handle().clone())));
            let supervisor_clone = supervisor.clone();

            app.manage(AppState {
                supervisor,
                pty_manager: pty_manager_clone,
                sovereignty,
            });

            // Start supervision background loop
            tokio::spawn(async move {
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

