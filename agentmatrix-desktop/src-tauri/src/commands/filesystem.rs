use std::path::Path;

/// 复制文件
#[tauri::command]
pub fn copy_file(src: String, dest: String) -> Result<(), String> {
    std::fs::copy(&src, &dest)
        .map(|_| ())
        .map_err(|e| format!("Failed to copy {} to {}: {}", src, dest, e))
}

/// 检查文件是否存在
#[tauri::command]
pub fn file_exists(path: String) -> bool {
    Path::new(&path).exists()
}

/// 打开文件夹（在系统文件管理器中打开）
#[tauri::command]
pub async fn open_folder(path: String) -> Result<(), String> {
    let path = std::path::Path::new(&path);
    if !path.exists() {
        return Err(format!("Path does not exist: {}", path.display()));
    }

    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(path)
            .spawn()
            .map_err(|e| format!("Failed to open folder: {}", e))?;
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .arg(path)
            .spawn()
            .map_err(|e| format!("Failed to open folder: {}", e))?;
    }

    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(path)
            .spawn()
            .map_err(|e| format!("Failed to open folder: {}", e))?;
    }

    println!("✅ Opened folder: {}", path.display());
    Ok(())
}

/// 在文件管理器中选中并显示文件
#[tauri::command]
pub async fn reveal_in_folder(path: String) -> Result<(), String> {
    let path = std::path::Path::new(&path);
    if !path.exists() {
        return Err(format!("Path does not exist: {}", path.display()));
    }

    #[cfg(target_os = "macos")]
    {
        // macOS: open -R 会在 Finder 中选中文件
        std::process::Command::new("open")
            .arg("-R")
            .arg(path)
            .spawn()
            .map_err(|e| format!("Failed to reveal in Finder: {}", e))?;
    }

    #[cfg(target_os = "windows")]
    {
        // Windows: explorer /select 会在资源管理器中选中文件
        let path_str = path.to_string_lossy().to_string();
        std::process::Command::new("explorer")
            .arg("/select,")
            .arg(&path_str)
            .spawn()
            .map_err(|e| format!("Failed to reveal in Explorer: {}", e))?;
    }

    #[cfg(target_os = "linux")]
    {
        // Linux: 尝试使用常见的文件管理器
        // 优先尝试 nautilus (GNOME), dolphin (KDE), thunar (XFCE)
        let managers = vec![
            ("nautilus", vec!["--select", path.to_str().unwrap()]),
            ("dolphin", vec!["--select", path.to_str().unwrap()]),
            ("thunar", vec!["--select", path.to_str().unwrap()]),
        ];

        let mut success = false;
        for (cmd, args) in managers {
            if std::process::Command::new(&cmd)
                .args(&args)
                .spawn()
                .is_ok()
            {
                success = true;
                println!("✅ Revealed with {} : {}", cmd, path.display());
                break;
            }
        }

        if !success {
            // 如果都失败了，回退到打开父目录
            if let Some(parent) = path.parent() {
                std::process::Command::new("xdg-open")
                    .arg(parent)
                    .spawn()
                    .map_err(|e| format!("Failed to open parent folder: {}", e))?;
            }
        }
    }

    println!("✅ Revealed in file manager: {}", path.display());
    Ok(())
}

/// 读取目录内容
#[tauri::command]
pub async fn read_directory(path: String) -> Result<Vec<serde_json::Value>, String> {
    let dir_path = std::path::Path::new(&path);
    if !dir_path.exists() {
        return Err(format!("Path does not exist: {}", path));
    }
    if !dir_path.is_dir() {
        return Err(format!("Path is not a directory: {}", path));
    }

    let mut entries = Vec::new();
    let dir_entries = std::fs::read_dir(dir_path)
        .map_err(|e| format!("Failed to read directory: {}", e))?;

    for entry in dir_entries {
        let entry = entry.map_err(|e| format!("Failed to read entry: {}", e))?;
        let file_name = entry.file_name().to_string_lossy().to_string();
        let entry_path = entry.path();
        let is_dir = entry.file_type().map(|ft| ft.is_dir()).unwrap_or(false);
        let size = if !is_dir {
            entry.metadata().ok().map(|m| m.len())
        } else {
            None
        };
        let modified = entry.metadata().ok()
            .and_then(|m| m.modified().ok())
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs_f64());

        entries.push(serde_json::json!({
            "name": file_name,
            "path": entry_path.to_string_lossy().to_string(),
            "is_dir": is_dir,
            "size": size,
            "modified": modified,
        }));
    }

    // Sort: directories first, then files, both alphabetically
    entries.sort_by(|a, b| {
        let a_is_dir = a["is_dir"].as_bool().unwrap_or(false);
        let b_is_dir = b["is_dir"].as_bool().unwrap_or(false);
        match (a_is_dir, b_is_dir) {
            (true, false) => std::cmp::Ordering::Less,
            (false, true) => std::cmp::Ordering::Greater,
            _ => a["name"].as_str().unwrap_or("").cmp(b["name"].as_str().unwrap_or("")),
        }
    });

    Ok(entries)
}
