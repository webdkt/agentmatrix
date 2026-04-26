use std::path::PathBuf;
use tauri::{AppHandle, Manager};
use crate::config::AppConfig;

/// 递归复制目录
fn copy_dir_recursive(src: &std::path::Path, dst: &std::path::Path) -> std::io::Result<()> {
    println!("Debug: copy_dir_recursive: src={:?}, dst={:?}", src, dst);
    // Ensure destination directory exists
    std::fs::create_dir_all(dst)?;
    
    #[cfg(unix)]
    {
        // Use cp -r src/. dst to copy contents, not the directory itself
        let src_with_dot = src.join(".");
        let status = std::process::Command::new("cp")
            .arg("-r")
            .arg(&src_with_dot)
            .arg(dst)
            .status()?;
        if status.success() {
            println!("Debug: cp command succeeded");
            return Ok(());
        } else {
            println!("Debug: cp command failed, falling back to recursive copy");
        }
    }
    
    #[cfg(windows)]
    {
        // Use robocopy for Windows (more reliable than xcopy)
        let src_str = src.to_string_lossy();
        let dst_str = dst.to_string_lossy();
        // robocopy source destination /E /COPY:DT /R:0 /W:0 /NP
        let status = std::process::Command::new("robocopy")
            .arg(&*src_str)
            .arg(&*dst_str)
            .arg("/E")          // copy subdirectories, including empty ones
            .arg("/COPY:DT")    // copy data and timestamps
            .arg("/R:0")        // no retries
            .arg("/W:0")        // no wait time
            .arg("/NP")         // no progress
            .status()?;
        // robocopy returns exit codes where 0-7 success, 8+ error
        let code = status.code().unwrap_or(8);
        if code < 8 {
            println!("Debug: robocopy succeeded with code {}", code);
            return Ok(());
        } else {
            println!("Debug: robocopy failed with code {}, falling back to recursive copy", code);
        }
    }
    
    // Recursive copy using Rust std::fs
    for entry in std::fs::read_dir(src)? {
        let entry = entry?;
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());
        if src_path.is_dir() {
            copy_dir_recursive(&src_path, &dst_path)?;
        } else {
            std::fs::copy(&src_path, &dst_path)?;
        }
    }
    
    Ok(())
}

/// 初始化 MatrixWorld 目录
#[tauri::command]
pub fn init_matrix_world(app: AppHandle, matrix_world_path: String, user_name: String) -> Result<(), String> {
    // In dev mode, use local resources directory (fixes worktree symlink issues)
    // In production, use resource_dir from the bundle
    let src = if cfg!(dev) {
        // Dev mode: use resources directory relative to CARGO_MANIFEST_DIR
        let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        manifest_dir.join("resources").join("matrix-template")
    } else {
        // Production: use bundled resources
        let resource_dir = app.path().resource_dir()
            .map_err(|e| format!("Failed to get resource dir: {}", e))?;
        resource_dir.join("resources").join("matrix-template")
    };

    println!("Debug: src = {:?}", src);
    // Expand ~ in path
    let dest = if matrix_world_path.starts_with("~/") {
        if let Ok(home) = std::env::var("HOME") {
            PathBuf::from(home).join(&matrix_world_path[2..])
        } else {
            PathBuf::from(matrix_world_path.clone())
        }
    } else {
        PathBuf::from(matrix_world_path.clone())
    };
    println!("Debug: dest = {:?}", dest);

    if !src.exists() {
        return Err(format!("Template directory not found: {:?}", src));
    }

    std::fs::create_dir_all(&dest)
        .map_err(|e| format!("Failed to create directory: {}", e))?;

    // Copy template recursively
    copy_dir_recursive(&src, &dest)
        .map_err(|e| format!("Failed to copy template: {}", e))?;

    // Replace {{USER_NAME}} in User.yml and system_config.yml
    for rel_path in &[".matrix/configs/agents/User.yml", ".matrix/configs/system_config.yml"] {
        let file_path = dest.join(rel_path);
        if file_path.exists() {
            let content = std::fs::read_to_string(&file_path)
                .map_err(|e| format!("Failed to read {}: {}", rel_path, e))?;
            let content = content.replace("{{USER_NAME}}", &user_name);
            std::fs::write(&file_path, content)
                .map_err(|e| format!("Failed to write {}: {}", rel_path, e))?;
        }
    }

    // Save the matrix world path to config
    let config_path = AppConfig::get_config_path().map_err(|e| format!("Failed to get config path: {}", e))?;
    println!("Debug: Saving config to {:?}", config_path);
    let mut config = AppConfig::load().map_err(|e| format!("Failed to load config: {}", e))?;
    config.matrix_world_path = matrix_world_path.clone();
    config.save().map_err(|e| format!("Failed to save config: {}", e))?;

    println!("✅ Matrix world initialized at {}", matrix_world_path);
    Ok(())
}
