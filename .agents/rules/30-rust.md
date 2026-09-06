---
trigger: glob
globs: apps/desktop/src-tauri/**/*.rs
description: Rust standards for the Tauri native core.
---

# Rust — `src-tauri/`

Edition 2021, `tokio`. `cargo clippy -- -D warnings` must pass.

## No `unwrap()` or `expect()` outside tests and `main()` startup

❌ **Bad** — panics take down the whole app window
```rust
#[tauri::command]
fn read_project_file(path: String) -> String {
    std::fs::read_to_string(path).unwrap()
}
```

✅ **Good**
```rust
#[tauri::command]
async fn read_project_file(
    state: tauri::State<'_, AppState>,
    path: String,
) -> Result<String, AppError> {
    let scoped = state.workspace.resolve_scoped(&path)?;
    tokio::fs::read_to_string(&scoped)
        .await
        .map_err(|e| AppError::Io { path: scoped, source: e })
}
```

Use `thiserror` for library errors, `anyhow` only at the top boundary. Every Tauri command returns `Result<T, AppError>` with a serialisable error.

## Path scoping is a security control, not a convenience

Every path from the frontend or the agent is resolved and verified to be inside the open project directory. Traversal is a security defect.

✅ **Good** — one implementation, used everywhere
```rust
impl Workspace {
    pub fn resolve_scoped(&self, candidate: &str) -> Result<PathBuf, AppError> {
        let joined = self.root.join(candidate);
        let canonical = joined.canonicalize()
            .map_err(|_| AppError::PathNotFound(candidate.to_owned()))?;
        if !canonical.starts_with(&self.root) {
            return Err(AppError::PathEscapesWorkspace(candidate.to_owned()));
        }
        Ok(canonical)
    }
}
```

Write negative tests for `../`, absolute paths, and symlinks that point outside the workspace.

## Never block the async runtime

A blocked runtime freezes the UI, and the user will blame the model.

❌ `let out = std::process::Command::new("bwrap").output()?;`
✅ `let out = tokio::task::spawn_blocking(move || cmd.output()).await??;`

## PTY

Use `portable-pty`. Do not write a custom terminal renderer — `xterm.js` handles ANSI escapes, alternate screen buffers, mouse reporting and Unicode widths, and reimplementing that is a bottomless pit.

Propagate resize events from the UI through to the PTY, or full-screen programs render wrongly. Test this explicitly; it is the most commonly missed PTY bug.

## Sandbox launch states its isolation explicitly

❌ `Command::new("python3").arg(script)`

✅
```rust
Command::new("bwrap")
    .args(["--unshare-net", "--unshare-pid", "--die-with-parent"])
    .args(["--ro-bind", "/usr", "/usr"])
    .args(["--bind", work_dir, "/work"])
    .args(["--chdir", "/work"])
    .arg("python3").arg(script)
```
