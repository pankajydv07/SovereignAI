// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

pub mod protocol;
pub mod sidecar;

fn main() {
    swaraj_desktop::run();
}
