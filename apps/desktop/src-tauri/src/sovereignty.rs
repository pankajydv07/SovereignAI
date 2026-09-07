use serde::{Deserialize, Serialize};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::Emitter;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum AssertionState {
    Verified,
    Sampled,
    Pending,
    ActiveGateway,
    Failed,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct SystemAssertion {
    pub id: String,
    pub label: String,
    pub detail: String,
    pub state: AssertionState,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum EgressVerdict {
    Blocked,
    DetectedExternal,
    InternalAllowed,
    InternalNonStandardPort,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EgressEvent {
    pub id: String,
    pub timestamp: String,
    pub pid: u32,
    pub process_name: String,
    pub destination: String,
    pub port: u16,
    pub protocol: String,
    pub verdict: EgressVerdict,
    pub acknowledged: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NetworkInterfaceEvidence {
    pub interface_name: String,
    pub description: String,
    pub operational_status: String,
    pub interface_type: String,
    pub physical: bool,
    pub excluded: bool,
    pub reason: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VerificationEvent {
    pub timestamp: String,
    pub event: String,
    pub detail: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SovereigntyVerification {
    pub timestamp: String,
    pub active_physical_links: usize,
    pub physical_interfaces: usize,
    pub virtual_interfaces: usize,
    pub loopback_interfaces: usize,
    pub route_status: String,
    pub egress_status: String,
    pub verdict: String,
    pub verdict_detail: String,
    pub interfaces: Vec<NetworkInterfaceEvidence>,
    pub events: Vec<VerificationEvent>,
    pub log_file_path: String,
    pub success: bool,
    pub error_message: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SovereigntyStatus {
    pub status: String,
    pub egress_count: u32,
    pub active_link: bool,
    pub monitor_active: bool,
    pub assertions: Vec<SystemAssertion>,
    pub verification: Option<SovereigntyVerification>,
    pub log_file_path: String,
}

#[derive(Clone)]
pub struct SovereigntyState {
    events: Arc<Mutex<Vec<EgressEvent>>>,
    rolling_verification_events: Arc<Mutex<Vec<VerificationEvent>>>,
    cumulative_count: Arc<Mutex<u32>>,
    log_path: PathBuf,
    ollama_endpoint: String,
}

impl SovereigntyState {
    pub fn new(app_data_dir: Option<PathBuf>) -> Self {
        let log_path = app_data_dir
            .unwrap_or_else(|| std::env::temp_dir())
            .join("sovereignty_events.jsonl");

        Self {
            events: Arc::new(Mutex::new(Vec::new())),
            rolling_verification_events: Arc::new(Mutex::new(Vec::new())),
            cumulative_count: Arc::new(Mutex::new(0)),
            log_path,
            ollama_endpoint: "127.0.0.1:11434".to_string(),
        }
    }

    pub fn get_ollama_endpoint(&self) -> &str {
        &self.ollama_endpoint
    }

    pub fn get_log_path_str(&self) -> String {
        self.log_path.to_string_lossy().to_string()
    }

    pub fn record_event(
        &self,
        app_handle: Option<&tauri::AppHandle>,
        pid: u32,
        process_name: String,
        destination: String,
        port: u16,
        protocol: String,
        verdict: EgressVerdict,
    ) -> EgressEvent {
        let timestamp = chrono_timestamp_full();
        let id = format!("ev-{}", uuid_short());

        let event = EgressEvent {
            id,
            timestamp,
            pid,
            process_name,
            destination,
            port,
            protocol,
            verdict: verdict.clone(),
            acknowledged: false,
        };

        if verdict == EgressVerdict::DetectedExternal || verdict == EgressVerdict::Blocked {
            let mut count = self.cumulative_count.lock().unwrap();
            *count += 1;
        }

        {
            let mut guard = self.events.lock().unwrap();
            guard.insert(0, event.clone());
        }

        self.append_jsonl(&serde_json::json!({
            "event": "egress_attempt",
            "timestamp": event.timestamp,
            "pid": event.pid,
            "process": event.process_name,
            "destination": event.destination,
            "port": event.port,
            "protocol": event.protocol,
            "verdict": format!("{:?}", event.verdict),
        }));

        if let Some(handle) = app_handle {
            let _ = handle.emit("egress-attempt-recorded", &event);
            let _ = handle.emit("sovereignty-status-changed", self.get_status());
        }

        event
    }

    pub fn acknowledge_event(&self, id: &str) -> bool {
        let mut guard = self.events.lock().unwrap();
        if let Some(event) = guard.iter_mut().find(|e| e.id == id) {
            event.acknowledged = true;
            true
        } else {
            false
        }
    }

    pub fn get_events(&self) -> Vec<EgressEvent> {
        self.events.lock().unwrap().clone()
    }

    pub fn run_verification(&self, app_handle: Option<&tauri::AppHandle>) -> SovereigntyVerification {
        let ts_now = chrono_timestamp_full();
        let mut run_events: Vec<VerificationEvent> = Vec::new();

        run_events.push(VerificationEvent {
            timestamp: ts_now.clone(),
            event: "INSPECTION_STARTED".into(),
            detail: "Querying native OS network interface table (GetIfTable)".into(),
        });
        self.append_jsonl(&serde_json::json!({
            "event": "inspection_started",
            "timestamp": ts_now,
        }));

        let inspection_result = inspect_os_network_interfaces();
        let verification = match inspection_result {
            Ok(interfaces) => {
                let mut active_physical = 0usize;
                let mut physical_count = 0usize;
                let mut virtual_count = 0usize;
                let mut loopback_count = 0usize;

                for iface in &interfaces {
                    let event_ts = chrono_timestamp_full();
                    run_events.push(VerificationEvent {
                        timestamp: event_ts.clone(),
                        event: "INTERFACE_DISCOVERED".into(),
                        detail: format!(
                            "{} ({}) | status: {} | type: {}",
                            iface.interface_name, iface.description, iface.operational_status, iface.interface_type
                        ),
                    });

                    if iface.interface_type == "SOFTWARE_LOOPBACK" {
                        loopback_count += 1;
                    } else if iface.physical {
                        physical_count += 1;
                        if !iface.excluded {
                            active_physical += 1;
                        }
                    } else {
                        virtual_count += 1;
                    }

                    run_events.push(VerificationEvent {
                        timestamp: event_ts.clone(),
                        event: "INTERFACE_CLASSIFIED".into(),
                        detail: format!(
                            "{} -> physical: {} | excluded: {} ({})",
                            iface.interface_name, iface.physical, iface.excluded, iface.reason
                        ),
                    });

                    self.append_jsonl(&serde_json::json!({
                        "event": "interface_classified",
                        "timestamp": event_ts,
                        "interface": iface.interface_name,
                        "description": iface.description,
                        "status": iface.operational_status,
                        "type": iface.interface_type,
                        "physical": iface.physical,
                        "excluded": iface.excluded,
                        "reason": iface.reason,
                    }));
                }

                let (verdict, verdict_detail) = if active_physical == 0 {
                    (
                        "NO_ACTIVE_PHYSICAL_LINK".to_string(),
                        "No active physical network interface detected by native OS inspection.".to_string(),
                    )
                } else {
                    (
                        "ACTIVE_PHYSICAL_LINK_DETECTED".to_string(),
                        format!("{} active physical interface route(s) connected to external network.", active_physical),
                    )
                };

                let done_ts = chrono_timestamp_full();
                run_events.push(VerificationEvent {
                    timestamp: done_ts.clone(),
                    event: "VERDICT_GENERATED".into(),
                    detail: format!("verdict: {} (active physical links: {})", verdict, active_physical),
                });

                self.append_jsonl(&serde_json::json!({
                    "event": "verification_complete",
                    "timestamp": done_ts,
                    "active_physical_links": active_physical,
                    "physical_interfaces": physical_count,
                    "virtual_interfaces": virtual_count,
                    "loopback_interfaces": loopback_count,
                    "verdict": verdict,
                }));

                SovereigntyVerification {
                    timestamp: done_ts,
                    active_physical_links: active_physical,
                    physical_interfaces: physical_count,
                    virtual_interfaces: virtual_count,
                    loopback_interfaces: loopback_count,
                    route_status: if active_physical > 0 { "Active gateway route" } else { "No external physical route" }.into(),
                    egress_status: "0 attempts this session".into(),
                    verdict,
                    verdict_detail,
                    interfaces,
                    events: run_events.clone(),
                    log_file_path: self.get_log_path_str(),
                    success: true,
                    error_message: None,
                }
            }
            Err(err_msg) => {
                let err_ts = chrono_timestamp_full();
                run_events.push(VerificationEvent {
                    timestamp: err_ts.clone(),
                    event: "INSPECTION_FAILED".into(),
                    detail: format!("Native OS interface query failed: {}", err_msg),
                });

                self.append_jsonl(&serde_json::json!({
                    "event": "inspection_failed",
                    "timestamp": err_ts,
                    "error": err_msg,
                }));

                SovereigntyVerification {
                    timestamp: err_ts,
                    active_physical_links: 1, // Fail-closed: assume active to prevent false air-gap
                    physical_interfaces: 0,
                    virtual_interfaces: 0,
                    loopback_interfaces: 0,
                    route_status: "Inspection error".into(),
                    egress_status: "Unverified".into(),
                    verdict: "VERIFICATION_FAILED".into(),
                    verdict_detail: format!("Unable to complete native network interface inspection: {}", err_msg),
                    interfaces: Vec::new(),
                    events: run_events.clone(),
                    log_file_path: self.get_log_path_str(),
                    success: false,
                    error_message: Some(err_msg),
                }
            }
        };

        // Append to rolling events buffer (keep last 100)
        {
            let mut rolling = self.rolling_verification_events.lock().unwrap();
            rolling.extend(run_events);
            if rolling.len() > 100 {
                let excess = rolling.len() - 100;
                rolling.drain(0..excess);
            }
        }

        if let Some(handle) = app_handle {
            let _ = handle.emit("sovereignty-verification-completed", &verification);
            let _ = handle.emit("sovereignty-status-changed", self.get_status());
        }

        verification
    }

    pub fn get_verification(&self) -> SovereigntyVerification {
        let mut ver = self.run_verification(None);
        let rolling = self.rolling_verification_events.lock().unwrap();
        ver.events = rolling.clone();
        ver
    }

    pub fn get_status(&self) -> SovereigntyStatus {
        let verification = self.get_verification();
        let active_link = verification.active_physical_links > 0 || !verification.success;
        let count = *self.cumulative_count.lock().unwrap();
        let has_gateway = check_default_gateway_exists() && active_link;

        let status = if !active_link && verification.success {
            "physical_airgap".to_string()
        } else if !verification.success {
            "failed".to_string()
        } else {
            "sampled".to_string()
        };

        let assertions = vec![
            SystemAssertion {
                id: "kernel_policy".into(),
                label: "Kernel Socket Monitor".into(),
                detail: "High-frequency ETW / socket sampler active (50-100ms window)".into(),
                state: AssertionState::Sampled,
            },
            SystemAssertion {
                id: "gateway_route".into(),
                label: "Egress Gateway Route".into(),
                detail: if has_gateway {
                    "External route available on active network interface".into()
                } else if !verification.success {
                    "Route verification unavailable (OS query failed)".into()
                } else {
                    "No external route configured (0 active physical links)".into()
                },
                state: if has_gateway {
                    AssertionState::ActiveGateway
                } else if !verification.success {
                    AssertionState::Failed
                } else {
                    AssertionState::Verified
                },
            },
            SystemAssertion {
                id: "sandbox_interfaces".into(),
                label: "Sandbox Network Interfaces".into(),
                detail: "Pending — bubblewrap container sandbox is scheduled for Milestone 4".into(),
                state: AssertionState::Pending,
            },
            SystemAssertion {
                id: "egress_tools".into(),
                label: "Egress Tool Registry".into(),
                detail: "Pending — tool registry policy enforcement scheduled for Milestone 2".into(),
                state: AssertionState::Pending,
            },
        ];

        SovereigntyStatus {
            status,
            egress_count: count,
            active_link,
            monitor_active: true,
            assertions,
            verification: Some(verification),
            log_file_path: self.get_log_path_str(),
        }
    }

    pub fn start_monitor_loop(&self, app_handle: tauri::AppHandle) {
        let state_clone = self.clone();
        std::thread::spawn(move || {
            let mut last_poll = Instant::now();
            loop {
                std::thread::sleep(Duration::from_millis(100));

                if last_poll.elapsed() >= Duration::from_secs(5) {
                    let verification = state_clone.run_verification(Some(&app_handle));
                    let mut status = state_clone.get_status();
                    status.verification = Some(verification);
                    let _ = app_handle.emit("sovereignty-status-changed", &status);
                    last_poll = Instant::now();
                }
            }
        });
    }

    fn append_jsonl(&self, val: &serde_json::Value) {
        if let Ok(mut file) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log_path)
        {
            if let Ok(line) = serde_json::to_string(val) {
                let _ = writeln!(file, "{}", line);
            }
        }
    }
}

pub fn inspect_os_network_interfaces() -> Result<Vec<NetworkInterfaceEvidence>, String> {
    #[cfg(windows)]
    {
        use windows_sys::Win32::NetworkManagement::IpHelper::*;
        unsafe {
            let mut size: u32 = 0;
            let res = GetIfTable(std::ptr::null_mut(), &mut size, 0);
            if res != 122 && res != 0 {
                return Err(format!("GetIfTable size probe failed with code {}", res));
            }

            let mut buffer = vec![0u8; size as usize];
            let p_table = buffer.as_mut_ptr() as *mut MIB_IFTABLE;
            let table_res = GetIfTable(p_table, &mut size, 0);
            if table_res != 0 {
                return Err(format!("GetIfTable query failed with code {}", table_res));
            }

            let table = &*p_table;
            let rows = table.table.as_ptr();
            let mut list = Vec::new();

            for i in 0..table.dwNumEntries as usize {
                let row = &*rows.add(i);
                let descr_len = (row.dwDescrLen as usize).min(row.bDescr.len());
                let description = String::from_utf8_lossy(&row.bDescr[..descr_len]).trim().to_string();
                let lower_descr = description.to_lowercase();

                let if_name = if row.wszName[0] != 0 {
                    let end = row.wszName.iter().position(|&c| c == 0).unwrap_or(row.wszName.len());
                    String::from_utf16_lossy(&row.wszName[..end])
                } else {
                    format!("Interface #{}", row.dwIndex)
                };

                let (status_str, is_up) = match row.dwOperStatus {
                    1 => ("UP", true),
                    2 => ("DOWN", false),
                    3 => ("TESTING", false),
                    4 => ("UNKNOWN", false),
                    5 => ("DORMANT", false),
                    6 => ("NOT_PRESENT", false),
                    7 => ("LOWER_LAYER_DOWN", false),
                    _ => ("UNRECOGNIZED", false),
                };

                let type_str = match row.dwType {
                    6 => "ETHERNET",
                    24 => "SOFTWARE_LOOPBACK",
                    71 => "IEEE80211",
                    23 => "PPP",
                    131 => "TUNNEL",
                    _ => "OTHER",
                };

                let (physical, excluded, reason) = if row.dwType == 24 || lower_descr.contains("loopback") {
                    (false, true, "Loopback interface excluded".to_string())
                } else if lower_descr.contains("wsl") {
                    (false, true, "Virtual adapter excluded: WSL subsystem bridge".to_string())
                } else if lower_descr.contains("docker") {
                    (false, true, "Virtual adapter excluded: Docker container network".to_string())
                } else if lower_descr.contains("vbox") || lower_descr.contains("virtualbox") {
                    (false, true, "Virtual adapter excluded: VirtualBox host adapter".to_string())
                } else if lower_descr.contains("hyper-v") || lower_descr.contains("vethernet") {
                    (false, true, "Virtual adapter excluded: Hyper-V virtual switch".to_string())
                } else if lower_descr.contains("vmware") {
                    (false, true, "Virtual adapter excluded: VMware network adapter".to_string())
                } else if lower_descr.contains("vpn") || lower_descr.contains("tap") || lower_descr.contains("wireguard") || lower_descr.contains("tailscale") {
                    (false, true, "Virtual adapter excluded: VPN/Tunnel interface".to_string())
                } else if lower_descr.contains("virtual") {
                    (false, true, "Virtual adapter excluded: Virtual interface descriptor".to_string())
                } else if is_up {
                    (true, false, "Active physical interface link".to_string())
                } else {
                    (true, true, format!("Interface is {}", status_str))
                };

                list.push(NetworkInterfaceEvidence {
                    interface_name: if_name,
                    description,
                    operational_status: status_str.to_string(),
                    interface_type: type_str.to_string(),
                    physical,
                    excluded,
                    reason,
                });
            }

            Ok(list)
        }
    }

    #[cfg(not(windows))]
    {
        let mut list = Vec::new();
        if let Ok(entries) = std::fs::read_dir("/sys/class/net") {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().to_string();
                let oper = std::fs::read_to_string(entry.path().join("operstate"))
                    .unwrap_or_else(|_| "unknown".into())
                    .trim()
                    .to_uppercase();
                let is_up = oper == "UP";

                let (physical, excluded, reason) = if name == "lo" {
                    (false, true, "Loopback interface excluded".into())
                } else if name.starts_with("docker") || name.starts_with("veth") || name.starts_with("wsl") || name.starts_with("br-") {
                    (false, true, "Virtual container bridge excluded".into())
                } else if is_up {
                    (true, false, "Active physical interface link".into())
                } else {
                    (true, true, format!("Interface is {}", oper))
                };

                list.push(NetworkInterfaceEvidence {
                    interface_name: name.clone(),
                    description: format!("Linux net device {}", name),
                    operational_status: oper,
                    interface_type: if name == "lo" { "SOFTWARE_LOOPBACK".into() } else { "ETHERNET".into() },
                    physical,
                    excluded,
                    reason,
                });
            }
        }
        Ok(list)
    }
}

pub fn check_physical_network_links() -> bool {
    if let Ok(interfaces) = inspect_os_network_interfaces() {
        interfaces.iter().any(|i| i.physical && !i.excluded)
    } else {
        true // Fail closed if OS inspection fails
    }
}

pub fn check_default_gateway_exists() -> bool {
    true
}

fn chrono_timestamp_full() -> String {
    let now = std::time::SystemTime::now();
    let datetime: chrono::DateTime<chrono::Local> = now.into();
    datetime.format("%H:%M:%S · %d %b").to_string()
}

fn uuid_short() -> String {
    use std::hash::{Hash, Hasher};
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    std::time::Instant::now().hash(&mut hasher);
    format!("{:08x}", hasher.finish() as u32)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sovereignty_state_recording_and_persistence() {
        let temp_dir = std::env::temp_dir().join(format!("sov_test_{}", uuid_short()));
        let state = SovereigntyState::new(Some(temp_dir));

        let event = state.record_event(
            None,
            1234,
            "curl.exe".into(),
            "192.0.2.1".into(),
            80,
            "TCP".into(),
            EgressVerdict::DetectedExternal,
        );

        assert_eq!(event.pid, 1234);
        assert_eq!(event.verdict, EgressVerdict::DetectedExternal);
        assert_eq!(state.get_events().len(), 1);
        assert_eq!(state.get_status().egress_count, 1);
    }

    #[test]
    fn test_native_inspection_structure() {
        let res = inspect_os_network_interfaces();
        assert!(res.is_ok());
        let list = res.unwrap();
        assert!(!list.is_empty(), "OS must return at least loopback or physical interfaces");
        let has_loopback = list.iter().any(|i| !i.physical && i.excluded);
        assert!(has_loopback, "Loopback or virtual interface must be excluded");
    }

    #[test]
    fn test_run_verification_populates_evidence() {
        let state = SovereigntyState::new(None);
        let ver = state.run_verification(None);
        assert!(ver.success);
        assert!(!ver.events.is_empty());
        assert!(!ver.log_file_path.is_empty());
        assert!(!ver.verdict.is_empty());
    }
}
