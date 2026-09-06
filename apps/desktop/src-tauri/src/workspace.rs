use crate::protocol::FileNode;
use std::fs;
use std::path::PathBuf;

const MAX_DIR_ENTRIES: usize = 500;

/// Read directory entries scoped within workspace root.
pub fn read_workspace_dir(
    workspace_root: &str,
    rel_path: Option<&str>,
) -> Result<Vec<FileNode>, String> {
    let root_path = PathBuf::from(workspace_root);
    let root_canonical = fs::canonicalize(&root_path)
        .map_err(|e| format!("Invalid workspace root '{}': {}", workspace_root, e))?;

    let target_path = if let Some(rel) = rel_path {
        if rel.trim().is_empty() {
            root_canonical.clone()
        } else {
            root_canonical.join(rel)
        }
    } else {
        root_canonical.clone()
    };

    let target_canonical = fs::canonicalize(&target_path)
        .map_err(|e| format!("Invalid or non-existent path '{:?}': {}", target_path, e))?;

    // Security invariant: target must be inside workspace root
    if !target_canonical.starts_with(&root_canonical) {
        return Err(format!(
            "Access denied: path '{:?}' is outside workspace root '{:?}'",
            target_canonical, root_canonical
        ));
    }

    if !target_canonical.is_dir() {
        return Err(format!("Path '{:?}' is not a directory", target_canonical));
    }

    let entries = fs::read_dir(&target_canonical)
        .map_err(|e| format!("Failed to read directory '{:?}': {}", target_canonical, e))?;

    let mut nodes: Vec<FileNode> = Vec::new();
    let mut raw_count = 0usize;

    for entry_res in entries {
        let entry = match entry_res {
            Ok(e) => e,
            Err(_) => continue,
        };
        raw_count += 1;

        if nodes.len() >= MAX_DIR_ENTRIES {
            continue;
        }

        let name = entry.file_name().to_string_lossy().to_string();
        // Skip hidden git and node_modules by default
        if name == ".git" || name == "node_modules" {
            continue;
        }

        let entry_path = entry.path();
        let entry_canonical = match fs::canonicalize(&entry_path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        // Skip symlinks or entries escaping workspace root
        if !entry_canonical.starts_with(&root_canonical) {
            continue;
        }

        let is_dir = entry_canonical.is_dir();
        let metadata = entry.metadata().ok();
        let size_bytes = if is_dir {
            None
        } else {
            metadata.map(|m| m.len())
        };

        let relative_to_root = entry_canonical
            .strip_prefix(&root_canonical)
            .unwrap_or(&entry_canonical)
            .to_string_lossy()
            .to_string();

        nodes.push(FileNode {
            name,
            path: relative_to_root,
            is_dir,
            size_bytes,
            is_capped: None,
            total_entries: None,
        });
    }

    // Sort: directories first, then alphabetically
    nodes.sort_by(|a, b| {
        b.is_dir
            .cmp(&a.is_dir)
            .then_with(|| a.name.to_lowercase().cmp(&b.name.to_lowercase()))
    });

    if raw_count > MAX_DIR_ENTRIES {
        for node in &mut nodes {
            node.is_capped = Some(true);
            node.total_entries = Some(raw_count);
        }
    }

    Ok(nodes)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("swaraj_test_{}_{}", name, std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
        let _ = fs::create_dir_all(&dir);
        dir
    }

    #[test]
    fn test_valid_workspace_reading() {
        let root = create_test_dir("valid");
        fs::create_dir_all(root.join("subfolder")).unwrap();
        fs::write(root.join("file.txt"), "hello").unwrap();

        let nodes = read_workspace_dir(root.to_str().unwrap(), None).unwrap();
        assert_eq!(nodes.len(), 2);
        assert!(nodes.iter().any(|n| n.name == "subfolder" && n.is_dir));
        assert!(nodes.iter().any(|n| n.name == "file.txt" && !n.is_dir));
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn test_path_traversal_rejection() {
        let root = create_test_dir("traversal");
        fs::create_dir_all(root.join("inside")).unwrap();

        // Attempt .. traversal
        let result = read_workspace_dir(root.to_str().unwrap(), Some("../"));
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("outside workspace root"));
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn test_outside_absolute_path_rejection() {
        let root = create_test_dir("root");
        let outside = create_test_dir("outside");

        let root_str = root.to_str().unwrap();
        let outside_str = outside.to_str().unwrap();

        let result = read_workspace_dir(root_str, Some(outside_str));
        assert!(result.is_err());
        let _ = fs::remove_dir_all(&root);
        let _ = fs::remove_dir_all(&outside);
    }

    #[cfg(unix)]
    #[test]
    fn test_escaping_symlink_rejection() {
        use std::os::unix::fs::symlink;

        let root = create_test_dir("sym_root");
        let outside = create_test_dir("sym_outside");
        let outside_file = outside.join("secret.txt");
        fs::write(&outside_file, "secret").unwrap();

        let link_path = root.join("bad_link");
        symlink(&outside_file, &link_path).unwrap();

        let nodes = read_workspace_dir(root.to_str().unwrap(), None).unwrap();
        // Symlink pointing outside workspace root should be filtered out
        assert!(!nodes.iter().any(|n| n.name == "bad_link"));

        let _ = fs::remove_dir_all(&root);
        let _ = fs::remove_dir_all(&outside);
    }
}
