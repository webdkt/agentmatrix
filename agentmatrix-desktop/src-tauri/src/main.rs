// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Child};
use std::sync::Mutex;
use std::sync::atomic::{AtomicU16, Ordering};
use std::path::PathBuf;
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use tauri::{State, Manager, menu::{Menu, MenuItem}, tray::TrayIconBuilder, WindowEvent};
use serde_json::Value as JsonValue;

#[cfg(unix)]
fn kill_process_group(child: &mut Child) {
    let pid = child.id() as i32;
    // First send SIGTERM to allow graceful shutdown
    unsafe {
        libc::killpg(pid, libc::SIGTERM);
    }
    // Wait up to 30 seconds for the process to exit, then force kill
    for _ in 0..300 {
        std::thread::sleep(std::time::Duration::from_millis(100));
        match child.try_wait() {
            Ok(Some(status)) => {
                println!("Backend exited gracefully: {}", status);
                return;
            }
            _ => continue,
        }
    }
    println!("Backend did not exit in time, force killing...");
    unsafe {
        libc::killpg(pid, libc::SIGKILL);
    }
    let _ = child.wait();
}

#[cfg(windows)]
fn kill_process_group(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

fn read_port_from_file(matrix_world: &std::path::Path) -> Option<u16> {
    let port_file = matrix_world.join(".matrix").join("backend_port");
    if let Ok(content) = std::fs::read_to_string(&port_file) {
        if let Ok(port) = content.trim().parse::<u16>() {
            if port > 0 {
                return Some(port);
            }
        }
    }
    None
}

mod config;
use config::AppConfig;

// ─── Matrix World Initialization ───

fn expand_path(path: &str) -> PathBuf {
    if path.starts_with("~/") {
        if let Ok(home) = std::env::var("HOME") {
            PathBuf::from(home).join(&path[2..])
        } else {
            PathBuf::from(path)
        }
    } else {
        PathBuf::from(path)
    }
}

#[tauri::command]
fn init_matrix_world(app: tauri::AppHandle, matrix_world_path: String, user_name: String) -> Result<(), String> {
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

#[tauri::command]
fn save_llm_config(matrix_world_path: String, llm_config: JsonValue) -> Result<(), String> {
    let config_path = expand_path(&matrix_world_path)
        .join(".matrix/configs/llm_config.json");

    if let Some(parent) = config_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create directory: {}", e))?;
    }

    let json_str = serde_json::to_string_pretty(&llm_config)
        .map_err(|e| format!("Failed to serialize JSON: {}", e))?;

    std::fs::write(&config_path, json_str)
        .map_err(|e| format!("Failed to write llm_config.json: {}", e))?;

    println!("✅ Saved LLM config to {:?}", config_path);
    Ok(())
}

#[tauri::command]
fn save_email_proxy_config_cmd(matrix_world_path: String, email_proxy: JsonValue) -> Result<(), String> {
    let config_path = expand_path(&matrix_world_path)
        .join(".matrix/configs/email_proxy_config.yml");

    if let Some(parent) = config_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create directory: {}", e))?;
    }

    let yaml_str = serde_yaml::to_string(&email_proxy)
        .map_err(|e| format!("Failed to serialize YAML: {}", e))?;

    std::fs::write(&config_path, yaml_str)
        .map_err(|e| format!("Failed to write email_proxy_config.yml: {}", e))?;

    println!("✅ Saved email proxy config to {:?}", config_path);
    Ok(())
}

#[tauri::command]
fn save_env_file(matrix_world_path: String, env_vars: JsonValue) -> Result<(), String> {
    let env_path = expand_path(&matrix_world_path)
        .join(".matrix/configs/.env");

    if let Some(parent) = env_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create directory: {}", e))?;
    }

    let mut content = String::new();
    if let Some(obj) = env_vars.as_object() {
        for (key, value) in obj {
            if let Some(val_str) = value.as_str() {
                content.push_str(&format!("{}={}\n", key, val_str));
            }
        }
    }

    std::fs::write(&env_path, content)
        .map_err(|e| format!("Failed to write .env: {}", e))?;

    println!("✅ Saved .env to {:?}", env_path);
    Ok(())
}

fn copy_dir_recursive(src: &std::path::Path, dst: &std::path::Path) -> std::io::Result<()> {
    println!("Debug: copy_dir_recursive: src={:?}, dst={:?}", src, dst);
    // Ensure destination directory exists
    std::fs::create_dir_all(dst)?;
    
    #[cfg(unix)]
    {
        // Use cp -r src/. dst to copy contents, not the directory itself
        let src_with_dot = src.join(".");
        let status = Command::new("cp")
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
        let status = Command::new("robocopy")
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
    println!("Debug: Using recursive copy");
    let mut file_count = 0;
    for entry in std::fs::read_dir(src)? {
        let entry = entry?;
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());
        if src_path.is_dir() {
            copy_dir_recursive(&src_path, &dst_path)?;
        } else {
            std::fs::copy(&src_path, &dst_path)?;
            file_count += 1;
            println!("Debug:   copied file: {:?}", src_path);
        }
    }
    println!("Debug: Recursive copy finished, copied {} files", file_count);
    Ok(())
}

// Backend state management
struct BackendState {
    child: Mutex<Option<Child>>,
    port: AtomicU16,
}

/// Get the path to the server executable from Python distribution
/// In production, the Python distribution (onedir mode) MUST exist in resources.
/// If not found, it's a build error - not a runtime fallback situation.
fn get_server_path(app: &tauri::AppHandle) -> Result<(String, Vec<String>), String> {
    // Dev mode: use python server.py
    if cfg!(dev) {
        println!("Dev mode: using python server.py");
        return Ok(("python".to_string(), vec!["server.py".to_string()]));
    }

    // Production: use Python executable from resources
    let resource_dir = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;

    // Python distribution is in resources/python_dist/
    let python_dist_dir = resource_dir.join("resources").join("python_dist");

    println!("🔍 Looking for Python distribution at: {:?}", python_dist_dir);

    if !python_dist_dir.exists() {
        return Err(format!(
            "❌ Python distribution not found!\n\n\
             Expected: {:?}\n\
             This is a BUILD ERROR - the app was not packaged correctly.\n\n\
             Please check:\n\
             1. PyInstaller onedir build succeeded\n\
             2. build_all.sh copied python_dist to resources/",
            python_dist_dir
        ));
    }

    // Executable name varies by platform
    let exe_name = if cfg!(target_os = "windows") {
        "server.exe"
    } else {
        "server"
    };

    let server_exe = python_dist_dir.join(exe_name);

    if !server_exe.exists() {
        return Err(format!(
            "❌ Server executable not found in Python distribution!\n\n\
             Expected: {:?}\n\
             Please check PyInstaller build.",
            server_exe
        ));
    }

    println!("✅ Found Python server: {:?}", server_exe);

    // Set working directory to Python dist dir for library loading
    // This is critical for onedir mode to find .so/.dylib/.dll files
    std::env::set_current_dir(&python_dist_dir)
        .map_err(|e| format!("Failed to set working directory to {:?}: {}", python_dist_dir, e))?;

    println!("📂 Working directory set to: {:?}", std::env::current_dir());

    Ok((server_exe.to_string_lossy().to_string(), vec![]))
}

/// Core backend startup logic, reusable by both setup() and tray/commands.
/// Returns the port number on success.
async fn start_backend_logic(app: &tauri::AppHandle, state: &BackendState) -> Result<u16, String> {
    // Check if backend is already running (in-memory child handle)
    if let Some(ref child) = *state.child.lock().unwrap() {
        if child.id() > 0 {
            println!("Backend already running (PID {}), skipping start", child.id());
            let port = state.port.load(Ordering::SeqCst);
            if port > 0 {
                return Ok(port);
            }
        }
    }

    // Also check if a backend from a previous session is already running
    let app_config_check = AppConfig::load()
        .map_err(|e| format!("Failed to load config: {}", e))?;
    let matrix_world_check = app_config_check.get_matrix_world_path();
    if let Some(existing_port) = read_port_from_file(&matrix_world_check) {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(2))
            .build()
            .map_err(|e| format!("Failed to create HTTP client: {}", e))?;
        let response = client.get(format!("http://localhost:{}/", existing_port))
            .send().await;
        if response.is_ok() {
            println!("Backend already running on port {} (from port file), skipping start", existing_port);
            state.port.store(existing_port, Ordering::SeqCst);
            return Ok(existing_port);
        }
    }

    println!("Starting Python backend...");

    // Load configuration
    let app_config = AppConfig::load()
        .map_err(|e| format!("Failed to load config: {}", e))?;

    // Get matrix world path from config
    let matrix_world = app_config.get_matrix_world_path();
    println!("Using MatrixWorld path: {:?}", matrix_world);

    // Verify matrix world exists
    if !matrix_world.exists() {
        println!("⚠️  Warning: MatrixWorld directory does not exist: {:?}", matrix_world);
        println!("It will be created automatically.");
    }

    // Get server path (sidecar or python fallback)
    let (server_bin, server_args) = get_server_path(app)?;

    let mut cmd = Command::new(&server_bin);

    // Add server.py if using python fallback
    for arg in &server_args {
        cmd.arg(arg);
    }

    // Add common arguments
    cmd.arg("--matrix-world")
       .arg(matrix_world.to_string_lossy().to_string());

    // In production, use dynamic port to avoid conflicts; in dev, keep 8000 for Vite proxy
    if cfg!(dev) {
        cmd.arg("--port").arg("8000");
    } else {
        cmd.arg("--port").arg("0");
    }

    // Set working directory only if using python (for server.py to find src/)
    if !server_args.is_empty() {
        let project_root = if cfg!(dev) {
            // Dev mode: use CARGO_MANIFEST_DIR to find project root
            // This works correctly in Git worktrees because it's not affected by symlinks
            let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));

            // CARGO_MANIFEST_DIR is src-tauri/, go up 2 levels to reach project root
            let project_root = manifest_dir.parent()
                .and_then(|p| p.parent())
                .unwrap_or(&manifest_dir);

            // Verify server.py exists at expected location
            if !project_root.join("server.py").exists() {
                eprintln!("Warning: server.py not found at {:?}", project_root.join("server.py"));
                eprintln!("Searching from parent directories...");

                // Fallback: search from parent directories
                let mut dir = manifest_dir.as_path();
                let mut found = None;
                for _ in 0..10 {
                    if dir.join("server.py").exists() {
                        found = Some(dir.to_path_buf());
                        break;
                    }
                    match dir.parent() {
                        Some(p) => dir = p,
                        None => break,
                    }
                }
                found.unwrap_or_else(|| project_root.to_path_buf())
            } else {
                project_root.to_path_buf()
            }
        } else {
            // Production: use resource_dir (requires resources to be packaged)
            if let Some(resource_dir) = app.path().resource_dir().ok() {
                resource_dir.parent()
                    .and_then(|p| p.parent())
                    .map(|p| p.to_path_buf())
                    .unwrap_or_else(|| resource_dir.clone())
            } else {
                // Fallback if resource_dir is not available
                eprintln!("Warning: resource_dir not available in production mode");
                std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."))
            }
        };
        cmd.current_dir(&project_root);
        println!("Working directory: {:?}", project_root);
    }

    // Put sidecar in its own process group so we can kill the entire tree
    #[cfg(unix)]
    cmd.process_group(0);
    let child = cmd.spawn()
        .map_err(|e| {
            eprintln!("Failed to start backend: {}", e);
            format!("Failed to start backend: {}", e)
        })?;

    {
        *state.child.lock().unwrap() = Some(child);
    }

    // Poll for port file written by the server
    let port_file = matrix_world.join(".matrix").join("backend_port");
    // Remove stale port file from previous runs before waiting
    let _ = std::fs::remove_file(&port_file);
    println!("Waiting for port file: {:?}", port_file);
    let mut attempt = 0u32;
    let port = loop {
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        attempt += 1;
        if port_file.exists() {
            if let Ok(content) = std::fs::read_to_string(&port_file) {
                if let Ok(port) = content.trim().parse::<u16>() {
                    println!("Port file found after {} attempts, port={}", attempt, port);
                    break port;
                }
            }
        }
        if attempt % 20 == 0 {
            println!("Still waiting for port file ({}s)...", attempt / 2);
        }
    };

    println!("Port file ready, waiting for HTTP health check on port {}...", port);

    // Wait for server to actually accept HTTP connections
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(2))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;
    attempt = 0;
    loop {
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        attempt += 1;
        let response = client.get(format!("http://localhost:{}/", port))
            .send().await;
        if response.is_ok() {
            println!("Backend healthy on port {} after {} health checks", port, attempt);
            state.port.store(port, Ordering::SeqCst);
            return Ok(port);
        }
        if attempt % 20 == 0 {
            println!("Still waiting for backend health check on port {} ({}s)...", port, attempt / 2);
        }
    }
}

#[tauri::command]
async fn start_backend(app: tauri::AppHandle, state: State<'_, BackendState>) -> Result<String, String> {
    let port = start_backend_logic(&app, &state).await?;
    Ok(format!("Backend started on port {}", port))
}

#[tauri::command]
async fn stop_backend(state: State<'_, BackendState>) -> Result<String, String> {
    println!("Stopping Python backend...");

    if let Some(mut child) = state.child.lock().unwrap().take() {
        kill_process_group(&mut child);
        println!("Backend stopped successfully");
    } else {
        println!("No backend running");
    }

    // Clear port state and port file
    state.port.store(0, Ordering::SeqCst);
    if let Ok(app_config) = AppConfig::load() {
        let port_file = expand_path(&app_config.matrix_world_path).join(".matrix").join("backend_port");
        let _ = std::fs::remove_file(&port_file);
    }

    Ok("Backend stopped".to_string())
}

#[tauri::command]
async fn check_backend(state: State<'_, BackendState>) -> Result<bool, String> {
    use std::time::Duration;

    let port = state.port.load(Ordering::SeqCst);
    let port = if port > 0 {
        port
    } else {
        // Fallback: read port file (backend might have been started externally)
        let app_config = AppConfig::load()
            .map_err(|e| format!("Failed to load config: {}", e))?;
        let matrix_world = expand_path(&app_config.matrix_world_path);
        match read_port_from_file(&matrix_world) {
            Some(p) => {
                // Store it so future calls don't need to read file
                state.port.store(p, Ordering::SeqCst);
                p
            }
            None => return Ok(false),
        }
    };

    // Try to connect to the backend
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let response = client.get(format!("http://localhost:{}/", port))
        .send()
        .await;

    Ok(response.is_ok())
}

#[tauri::command]
async fn get_backend_port(state: State<'_, BackendState>) -> Result<Option<u16>, String> {
    let port = state.port.load(Ordering::SeqCst);
    if port > 0 {
        return Ok(Some(port));
    }
    // Fallback: read port file
    let app_config = AppConfig::load()
        .map_err(|e| format!("Failed to load config: {}", e))?;
    let matrix_world = expand_path(&app_config.matrix_world_path);
    match read_port_from_file(&matrix_world) {
        Some(p) => {
            state.port.store(p, Ordering::SeqCst);
            Ok(Some(p))
        }
        None => Ok(None),
    }
}

#[tauri::command]
async fn get_config() -> Result<AppConfig, String> {
    let config = AppConfig::load()?;
    Ok(config)
}

#[tauri::command]
async fn update_config(matrix_world_path: Option<String>, auto_start_backend: Option<bool>, enable_notifications: Option<bool>) -> Result<AppConfig, String> {
    let mut config = AppConfig::load()?;
    
    if let Some(path) = matrix_world_path {
        config.matrix_world_path = path;
    }
    if let Some(auto_start) = auto_start_backend {
        config.auto_start_backend = auto_start;
    }
    if let Some(notifications) = enable_notifications {
        config.enable_notifications = notifications;
    }
    
    config.save()?;
    Ok(config)
}

#[tauri::command]
async fn is_first_run() -> Result<bool, String> {
    let config = AppConfig::load()?;
    Ok(config.is_first_run())
}

#[tauri::command]
async fn mark_configured(matrix_world_path: String) -> Result<(), String> {
    let mut config = AppConfig::load()?;
    config.matrix_world_path = matrix_world_path;
    config.save()?;
    println!("✅ Config saved");
    Ok(())
}

#[tauri::command]
async fn select_directory(app: tauri::AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;

    let (tx, rx) = std::sync::mpsc::channel();

    app.dialog()
        .file()
        .set_title("Select MatrixWorld Directory")
        .pick_folder(move |path| {
            let _ = tx.send(path.map(|p| p.to_string()));
        });

    match rx.recv() {
        Ok(Some(path)) => Ok(Some(path)),
        Ok(None) => Ok(None),
        Err(_) => Err("Dialog closed".to_string()),
    }
}

#[tauri::command]
async fn show_notification(title: String, body: String) -> Result<(), String> {
    println!("Notification: {} - {}", title, body);
    Ok(())
}

#[tauri::command]
async fn is_window_focused(app: tauri::AppHandle) -> Result<bool, String> {
    if let Some(window) = app.get_webview_window("main") {
        return window.is_focused().map_err(|e| e.to_string());
    }
    Ok(false)
}

#[tauri::command]
async fn show_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
async fn open_attachment_path(path: String) -> Result<(), String> {
    // 展开 ~ 为用户主目录
    let expanded_path = if path.starts_with("~/") {
        if let Some(home_dir) = dirs::home_dir() {
            path.replacen("~", &home_dir.to_string_lossy(), 1)
        } else {
            return Err("Failed to determine home directory".to_string());
        }
    } else {
        path
    };

    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&expanded_path)
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/c", "start", "", &expanded_path])
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
    }

    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(&expanded_path)
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
    }

    println!("✅ Opened: {}", expanded_path);
    Ok(())
}

#[tauri::command]
async fn open_folder(path: String) -> Result<(), String> {
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

#[tauri::command]
async fn open_browser_with_profile(profile_path: String) -> Result<(), String> {
    // Chrome paths by platform
    #[cfg(target_os = "macos")]
    let chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

    #[cfg(target_os = "windows")]
    let chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe";

    #[cfg(target_os = "linux")]
    let chrome_path = "google-chrome";

    let chrome = std::path::Path::new(chrome_path);

    #[cfg(target_os = "macos")]
    {
        if !chrome.exists() {
            // Fallback: try to open with `open -a`
            std::process::Command::new("open")
                .args(["-a", "Google Chrome", "--args", &format!("--user-data-dir={}", profile_path)])
                .spawn()
                .map_err(|e| format!("Failed to open Chrome: {}", e))?;
        } else {
            std::process::Command::new(chrome)
                .arg(&format!("--user-data-dir={}", profile_path))
                .spawn()
                .map_err(|e| format!("Failed to open Chrome: {}", e))?;
        }
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new(chrome)
            .arg(&format!("--user-data-dir={}", profile_path))
            .spawn()
            .map_err(|e| format!("Failed to open Chrome: {}", e))?;
    }

    #[cfg(target_os = "linux")]
    {
        std::process::Command::new(chrome)
            .arg(&format!("--user-data-dir={}", profile_path))
            .spawn()
            .map_err(|e| format!("Failed to open Chrome: {}", e))?;
    }

    println!("✅ Opened Chrome with profile: {}", profile_path);
    Ok(())
}

// ─── Container Runtime Detection ───

use std::process::Command as StdCommand;

#[derive(serde::Serialize)]
struct RuntimeInfo {
    runtime: String,  // "docker", "podman", or "none"
    version: Option<String>,
    install_guide: Option<String>,
}

/// Find an executable by trying direct lookup first, then common install paths,
/// and finally a login shell which inherits the user's full PATH.
fn find_executable(name: &str) -> Option<String> {
    // 1. Direct lookup (works if the binary is already in the process PATH)
    if let Ok(output) = StdCommand::new(name).arg("--version").output() {
        if output.status.success() {
            return Some(String::from_utf8_lossy(&output.stdout).trim().to_string());
        }
    }

    // 2. Try common install locations (macOS GUI apps don't inherit shell PATH)
    #[cfg(target_os = "macos")]
    {
        let paths = [
            format!("/opt/homebrew/bin/{}", name),
            format!("/usr/local/bin/{}", name),
            format!("/opt/podman/bin/{}", name),
        ];
        for p in &paths {
            if let Ok(output) = StdCommand::new(p).arg("--version").output() {
                if output.status.success() {
                    return Some(String::from_utf8_lossy(&output.stdout).trim().to_string());
                }
            }
        }
        // 3. Last resort: query the user's login shell for the full PATH
        if let Ok(output) = StdCommand::new("zsh")
            .args(["-l", "-c", &format!("{} --version", name)])
            .output()
        {
            if output.status.success() {
                return Some(String::from_utf8_lossy(&output.stdout).trim().to_string());
            }
        }
    }

    None
}

#[tauri::command]
async fn check_container_runtime() -> Result<RuntimeInfo, String> {
    // Check Podman first (preferred)
    if let Some(version) = find_executable("podman") {
        println!("✅ Found Podman: {}", version);
        return Ok(RuntimeInfo {
            runtime: "podman".to_string(),
            version: Some(version),
            install_guide: None,
        });
    }

    // Check Docker as fallback
    if let Some(version) = find_executable("docker") {
        println!("✅ Found Docker: {}", version);
        return Ok(RuntimeInfo {
            runtime: "docker".to_string(),
            version: Some(version),
            install_guide: None,
        });
    }
    
    println!("⚠️ No container runtime found");
    
    // Determine platform-specific install guide
    #[cfg(target_os = "macos")]
    let install_guide = Some("Podman Desktop installer is included. Click 'Install' to proceed.".to_string());
    
    #[cfg(target_os = "windows")]
    let install_guide = Some("Podman installer is included. Click 'Install' to proceed.".to_string());
    
    #[cfg(target_os = "linux")]
    let install_guide = Some("Please install Podman using your package manager:\n  sudo apt install podman".to_string());
    
    Ok(RuntimeInfo {
        runtime: "none".to_string(),
        version: None,
        install_guide,
    })
}

#[tauri::command]
async fn install_podman(app: tauri::AppHandle) -> Result<String, String> {
    let resource_dir = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;

    #[cfg(target_os = "macos")]
    {
        // Determine the correct package based on architecture
        let pkg_name = if cfg!(target_arch = "aarch64") {
            "podman-installer-arm64.pkg"
        } else if cfg!(target_arch = "x86_64") {
            "podman-installer-x64.pkg"
        } else {
            return Err(format!("Unsupported macOS architecture: {}", std::env::consts::ARCH));
        };

        let pkg_path = resource_dir.join("resources").join("podman").join(pkg_name);
        if !pkg_path.exists() {
            return Err(format!("Podman installer not found in bundle. Looking for: {:?}", pkg_path));
        }
        println!("Opening Podman installer: {:?}", pkg_path);
        // Open the PKG file - macOS will launch the installer GUI
        StdCommand::new("open")
            .arg(&pkg_path)
            .spawn()
            .map_err(|e| format!("Failed to open installer: {}", e))?;
        Ok("Opened Podman installer. Please follow the installation instructions.".to_string())
    }

    #[cfg(target_os = "windows")]
    {
        let msi_path = resource_dir.join("resources").join("podman").join("podman-x64.msi");
        if !msi_path.exists() {
            return Err(format!("Podman installer not found in bundle. Looking for: {:?}", msi_path));
        }
        println!("Starting Podman installer: {:?}", msi_path);
        // Run the MSI installer
        StdCommand::new("msiexec")
            .args(["/i", &msi_path.to_string_lossy()])
            .spawn()
            .map_err(|e| format!("Failed to start installer: {}", e))?;
        Ok("Started Podman installer. Please follow the installation instructions.".to_string())
    }

    #[cfg(target_os = "linux")]
    {
        Err("Please install Podman manually using your package manager".to_string())
    }
}

// ─── Auto Setup Container Runtime ───

async fn auto_setup_container_runtime(app: tauri::AppHandle) {
    println!("🔍 Checking container runtime...");

    // Check if Docker or Podman is already installed
    let runtime_info = check_container_runtime().await;

    match runtime_info {
        Ok(info) if info.runtime != "none" => {
            println!("✅ Container runtime found: {} {}", info.runtime, info.version.unwrap_or_default());

            // Check if Docker image needs to be loaded
            println!("🔍 Checking if container image is loaded...");
            match check_image().await {
                Ok(image_info) if image_info.exists => {
                    println!("✅ Container image already loaded: {} ({})", "agentmatrix:latest", image_info.size.unwrap_or_default());
                }
                Ok(_) => {
                    println!("📦 Container image not found, loading from bundle...");
                    match load_image(app.clone()).await {
                        Ok(msg) => {
                            println!("✅ Container image loaded successfully");
                        }
                        Err(e) => {
                            eprintln!("❌ Failed to load container image: {}", e);
                            eprintln!("⚠️  The application may not work correctly without the container image.");
                        }
                    }
                }
                Err(e) => {
                    eprintln!("❌ Error checking container image: {}", e);
                }
            }
        }
        Ok(_) => {
            println!("⚠️  No container runtime found. Attempting to install Podman...");

            // Try to auto-install Podman
            match install_podman(app).await {
                Ok(msg) => {
                    println!("📦 Podman installation initiated: {}", msg);
                }
                Err(e) => {
                    eprintln!("❌ Failed to install Podman: {}", e);
                    eprintln!("⚠️  Please install Podman manually to use container features.");
                }
            }
        }
        Err(e) => {
            eprintln!("❌ Error checking container runtime: {}", e);
        }
    }
}

// ─── Initialize Podman VM (for cold start wizard) ───

#[tauri::command]
async fn init_podman_vm() -> Result<String, String> {
    println!("🔄 Initializing Podman VM...");

    // Check if Podman is installed
    let runtime_info = check_container_runtime().await;
    let runtime_info = runtime_info.map_err(|e| e.to_string())?;

    if runtime_info.runtime != "podman" {
        return Err(format!("Podman is not installed. Runtime: {}", runtime_info.runtime));
    }

    // Check if VM is already initialized
    let list_output = StdCommand::new("podman")
        .args(["machine", "list"])
        .output()
        .map_err(|e| format!("Failed to list Podman machines: {}", e))?;

    let vm_exists = if list_output.status.success() {
        let stdout = String::from_utf8_lossy(&list_output.stdout);
        stdout.trim().lines().count() > 1  // Header + at least one machine
    } else {
        false
    };

    // Initialize VM if needed
    if !vm_exists {
        println!("📦 Podman VM not initialized, running 'podman machine init'...");
        let init_output = StdCommand::new("podman")
            .args(["machine", "init"])
            .output()
            .map_err(|e| format!("Failed to initialize Podman VM: {}", e))?;

        if !init_output.status.success() {
            let stderr = String::from_utf8_lossy(&init_output.stderr);
            return Err(format!("Failed to initialize Podman VM: {}", stderr));
        }
        println!("✅ Podman VM initialized");
    } else {
        println!("✅ Podman VM already initialized");
    }

    // Start VM
    println!("▶️ Starting Podman VM...");
    let start_output = StdCommand::new("podman")
        .args(["machine", "start"])
        .output()
        .map_err(|e| format!("Failed to start Podman VM: {}", e))?;

    if !start_output.status.success() {
        let stderr = String::from_utf8_lossy(&start_output.stderr);
        return Err(format!("Failed to start Podman VM: {}", stderr));
    }

    // Wait for Podman to be ready
    for i in 0..30 {
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        if StdCommand::new("podman")
            .args(["info"])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            println!("✅ Podman VM is ready (took {}s)", i + 1);
            return Ok("Podman VM initialized and started successfully".to_string());
        }
    }

    Err("Podman VM did not become ready after 30 seconds".to_string())
}

// ─── Ensure Container Image (for cold start wizard) ───

#[tauri::command]
async fn ensure_container_image(app: tauri::AppHandle) -> Result<String, String> {
    println!("🔍 Checking container image...");

    // Check if image exists
    let image_info = check_image().await.map_err(|e| e.to_string())?;

    if image_info.exists {
        println!("✅ Container image already loaded: {} ({})", "agentmatrix:latest", image_info.size.unwrap_or_default());
        return Ok("Container image already loaded".to_string());
    }

    // Load image
    println!("📦 Loading container image from bundle...");
    load_image(app).await?;
    println!("✅ Container image loaded successfully");

    Ok("Container image loaded successfully".to_string())
}

// ─── Docker Image Management ───

#[derive(serde::Serialize)]
struct ImageInfo {
    exists: bool,
    size: Option<String>,
}

#[tauri::command]
async fn check_image() -> Result<ImageInfo, String> {
    // Check if agentmatrix:latest image exists
    if let Ok(output) = StdCommand::new("podman")
        .args(["images", "--format", "{{.Size}}", "agentmatrix:latest"])
        .output()
    {
        if output.status.success() {
            let size_str = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !size_str.is_empty() {
                return Ok(ImageInfo {
                    exists: true,
                    size: Some(size_str),
                });
            }
        }
    }
    
    Ok(ImageInfo {
        exists: false,
        size: None,
    })
}

#[tauri::command]
async fn load_image(app: tauri::AppHandle) -> Result<String, String> {
    let resource_dir = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;

    let image_path = resource_dir.join("resources").join("docker").join("image.tar.gz");
    if !image_path.exists() {
        return Err(format!("Docker image not found in bundle. Looking for: {:?}", image_path));
    }

    println!("Loading Docker image from: {:?}", image_path);

    // Load image: gunzip | podman load
    let output = if cfg!(target_os = "windows") {
        StdCommand::new("cmd")
            .args(["/c", "type", &image_path.to_string_lossy(), "|", "gzip", "-d", "|", "podman", "load"])
            .output()
            .map_err(|e| format!("Failed to load image: {}", e))?
    } else {
        StdCommand::new("sh")
            .args(["-c", &format!("gunzip -c '{}' | podman load", image_path.to_string_lossy())])
            .output()
            .map_err(|e| format!("Failed to load image: {}", e))?
    };

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Failed to load image: {}", stderr));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    println!("✅ Image loaded: {}", stdout);

    Ok("Image loaded successfully".to_string())
}

fn main() {
    // Initialize config on first run (don't save, just check)
    match AppConfig::load() {
        Ok(config) => {
            println!("✅ Config loaded successfully");
            println!("MatrixWorld path: {}", config.matrix_world_path);
        }
        Err(e) => {
            println!("⚠️  Failed to load config: {}", e);
            println!("Will use default configuration");
        }
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(BackendState { child: Mutex::new(None), port: AtomicU16::new(0) })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" {
                    println!("Window closing, hiding instead of destroying...");
                    window.hide().ok();
                    api.prevent_close();
                }
            }
        })
        .setup(|app| {
            // Setup system tray
            let show_item = MenuItem::with_id(app, "show", "Open AgentMatrix", true, None::<&str>)?;
            let start_item = MenuItem::with_id(app, "start_backend", "Start Backend", true, None::<&str>)?;
            let stop_item = MenuItem::with_id(app, "stop_backend", "Stop Backend", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &start_item, &stop_item, &quit_item])?;

            let tray_icon = app.default_window_icon()
                .expect("No default window icon available")
                .clone();

            let _tray = TrayIconBuilder::new()
                .icon(tray_icon)
                .menu(&menu)
                .show_menu_on_left_click(true)
                .tooltip("AgentMatrix")
                .on_menu_event(|app, event| {
                    match event.id.as_ref() {
                        "show" => {
                            // Check if backend is reachable before showing window
                            let state = app.state::<BackendState>();
                            let port = state.port.load(Ordering::SeqCst);
                            if port > 0 {
                                if let Some(window) = app.get_webview_window("main") {
                                    let _ = window.show();
                                    let _ = window.set_focus();
                                }
                            } else {
                                // Backend not running — try reading port file as fallback
                                if let Ok(config) = AppConfig::load() {
                                    let mw = expand_path(&config.matrix_world_path);
                                    if read_port_from_file(&mw).is_some() {
                                        if let Some(window) = app.get_webview_window("main") {
                                            let _ = window.show();
                                            let _ = window.set_focus();
                                        }
                                        return;
                                    }
                                }
                                // Show error dialog
                                use tauri_plugin_dialog::DialogExt;
                                app.dialog()
                                    .message("Backend is not running. Please start it first from the tray menu.")
                                    .title("AgentMatrix")
                                    .show(|_| {});
                            }
                        }
                        "start_backend" => {
                            println!("Tray: Start Backend requested");
                            let app_handle = app.clone();
                            // Check if already running (using app.state inside the closure is fine)
                            {
                                let state = app.state::<BackendState>();
                                if state.child.lock().unwrap().is_some() {
                                    println!("Backend already running, showing window");
                                    if let Some(window) = app_handle.get_webview_window("main") {
                                        let _ = window.show();
                                        let _ = window.set_focus();
                                    }
                                    return;
                                }
                            }
                            tauri::async_runtime::spawn(async move {
                                let state = app_handle.state::<BackendState>();
                                match start_backend_logic(&app_handle, &state).await {
                                    Ok(_port) => {
                                        if let Some(window) = app_handle.get_webview_window("main") {
                                            let _ = window.show();
                                            let _ = window.set_focus();
                                        }
                                    }
                                    Err(e) => {
                                        eprintln!("Tray: Failed to start backend: {}", e);
                                        use tauri_plugin_dialog::DialogExt;
                                        app_handle.dialog()
                                            .message(format!("Failed to start backend:\n\n{}", e))
                                            .title("AgentMatrix - Error")
                                            .show(|_| {});
                                    }
                                }
                            });
                        }
                        "stop_backend" => {
                            println!("Tray: Stop Backend requested");
                            let state = app.state::<BackendState>();
                            if let Some(mut child) = state.child.lock().unwrap().take() {
                                kill_process_group(&mut child);
                            }
                            state.port.store(0, Ordering::SeqCst);
                            // Remove port file
                            if let Ok(app_config) = AppConfig::load() {
                                let port_file = expand_path(&app_config.matrix_world_path)
                                    .join(".matrix").join("backend_port");
                                let _ = std::fs::remove_file(&port_file);
                            }
                            println!("Backend stopped");
                        }
                        "quit" => {
                            // Hide window first so user sees it close immediately
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.hide();
                            }
                            // Stop backend in a separate thread so hide() can render
                            let app_handle = app.clone();
                            std::thread::spawn(move || {
                                let state = app_handle.state::<BackendState>();
                                if let Some(mut child) = state.child.lock().unwrap().take() {
                                    kill_process_group(&mut child);
                                }
                                state.port.store(0, Ordering::SeqCst);
                                if let Ok(app_config) = AppConfig::load() {
                                    let port_file = expand_path(&app_config.matrix_world_path)
                                        .join(".matrix").join("backend_port");
                                    let _ = std::fs::remove_file(&port_file);
                                }
                                app_handle.exit(0);
                            });
                        }
                        _ => {}
                    }
                })
                .build(app)?;

            // Create splash window immediately
            let splash_path = if cfg!(dev) {
                let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
                manifest_dir.join("splash.html")
            } else {
                app.path().resource_dir()
                    .unwrap_or_else(|_| std::path::PathBuf::from("."))
                    .join("splash.html")
            };
            let splash_url = tauri::WebviewUrl::External(
                format!("file://{}", splash_path.to_string_lossy()).parse().unwrap()
            );
            let _splash = tauri::WebviewWindowBuilder::new(app, "splash", splash_url)
                .title("AgentMatrix")
                .inner_size(400.0, 280.0)
                .center()
                .resizable(false)
                .decorations(false)
                .build()?;

            // Check if cold start wizard is needed BEFORE starting backend
            let needs_cold_start = AppConfig::load()
                .map(|config| config.is_first_run())
                .unwrap_or(true);

            println!("🎯 Cold start check: needs_wizard = {}", needs_cold_start);

            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if needs_cold_start {
                    // Cold start: create main window WITHOUT starting backend
                    // Vue app will detect is_first_run=true and show wizard
                    println!("🧙 Cold start required, showing wizard (no backend)");

                    let main_url = if cfg!(dev) {
                        tauri::WebviewUrl::External(
                            "http://localhost:5173".parse().unwrap()
                        )
                    } else {
                        tauri::WebviewUrl::App("index.html".into())
                    };

                    let _main = tauri::WebviewWindowBuilder::new(
                        &app_handle, "main", main_url,
                    )
                    .title("AgentMatrix")
                    .inner_size(1200.0, 800.0)
                    .min_inner_size(800.0, 600.0)
                    .center()
                    .resizable(true)
                    .fullscreen(false)
                    .devtools(true)
                    .build();

                    // Close splash
                    if let Some(splash) = app_handle.get_webview_window("splash") {
                        let _ = splash.close();
                    }
                } else {
                    // Normal startup: start backend first, then create main window
                    println!("🚀 Normal startup, starting backend...");

                    let state = app_handle.state::<BackendState>();
                    match start_backend_logic(&app_handle, &state).await {
                        Ok(_port) => {
                            println!("Backend ready, creating main window");
                            // Create main window with real frontend URL
                            let main_url = if cfg!(dev) {
                                tauri::WebviewUrl::External(
                                    "http://localhost:5173".parse().unwrap()
                                )
                            } else {
                                tauri::WebviewUrl::App("index.html".into())
                            };
                            let _main = tauri::WebviewWindowBuilder::new(
                                &app_handle, "main", main_url,
                            )
                            .title("AgentMatrix")
                            .inner_size(1200.0, 800.0)
                            .min_inner_size(800.0, 600.0)
                            .center()
                            .resizable(true)
                            .fullscreen(false)
                            .devtools(true)
                            .build();
                            // Close splash
                            if let Some(splash) = app_handle.get_webview_window("splash") {
                                let _ = splash.close();
                            }
                        }
                        Err(e) => {
                            eprintln!("Failed to start backend on launch: {}", e);
                            // Close splash
                            if let Some(splash) = app_handle.get_webview_window("splash") {
                                let _ = splash.close();
                            }
                            use tauri_plugin_dialog::DialogExt;
                            app_handle.dialog()
                                .message(format!(
                                    "Failed to start backend:\n\n{}\n\nYou can try starting it manually from the tray icon.",
                                    e
                                ))
                                .title("AgentMatrix - Startup Error")
                                .show(|_| {});
                        }
                    }
                }
            });

            // NOTE: Container runtime setup is now only done during cold start wizard,
            // not on app startup. This gives users better control and visibility.

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            check_backend,
            get_backend_port,
            get_config,
            update_config,
            is_first_run,
            mark_configured,
            select_directory,
            show_notification,
            open_attachment_path,
            open_folder,
            open_browser_with_profile,
            init_matrix_world,
            save_llm_config,
            save_email_proxy_config_cmd,
            save_env_file,
            check_container_runtime,
            install_podman,
            check_image,
            load_image,
            init_podman_vm,
            ensure_container_image,
            is_window_focused,
            show_window,
        ])
        .build(tauri::generate_context!())
        .expect("error with building tauri application")
        .run(|app_handle, event| {
            #[cfg(target_os = "macos")]
            if let tauri::RunEvent::Reopen { has_visible_windows, .. } = event {
                println!("🖥️  Dock icon clicked, has_visible_windows={}", has_visible_windows);

                if !has_visible_windows {
                    if let Some(window) = app_handle.get_webview_window("main") {
                        println!("📍 Showing main window...");
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
            }
        });
}
