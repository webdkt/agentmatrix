// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Child};
use std::sync::Mutex;
use std::path::PathBuf;
use tauri::{State, Manager};
use serde_json::Value as JsonValue;

mod config;
use config::AppConfig;

// ─── Matrix World Initialization ───

#[tauri::command]
fn init_matrix_world(app: tauri::AppHandle, matrix_world_path: String, user_name: String) -> Result<(), String> {
    let src = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?
        .join("matrix-template");

    if !src.exists() {
        return Err(format!("Template directory not found: {:?}", src));
    }

    let dest = PathBuf::from(&matrix_world_path);
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

    println!("✅ Matrix world initialized at {}", matrix_world_path);
    Ok(())
}

#[tauri::command]
fn save_llm_config(matrix_world_path: String, llm_config: JsonValue) -> Result<(), String> {
    let config_path = PathBuf::from(&matrix_world_path)
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
    let config_path = PathBuf::from(&matrix_world_path)
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

fn copy_dir_recursive(src: &std::path::Path, dst: &std::path::Path) -> std::io::Result<()> {
    std::fs::create_dir_all(dst)?;
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

// Backend state management
struct BackendState(Mutex<Option<Child>>);

/// Get the path to the server executable (sidecar or fallback to python)
fn get_server_path(app: &tauri::AppHandle) -> Result<(String, Vec<String>), String> {
    // In dev mode, always use python server.py
    // The sidecar placeholder in binaries/ exists only for Tauri compilation
    if cfg!(dev) {
        println!("Dev mode: using python server.py");
        return Ok(("python".to_string(), vec!["server.py".to_string()]));
    }

    // Try to find sidecar server executable (production)
    let resource_path = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;
    
    let sidecar_path = resource_path.join("binaries").join("server");
    
    #[cfg(target_os = "windows")]
    let sidecar_path = resource_path.join("binaries").join("server.exe");
    
    if sidecar_path.exists() {
        println!("Using sidecar server: {:?}", sidecar_path);
        return Ok((sidecar_path.to_string_lossy().to_string(), vec![]));
    }
    
    // Fallback to python
    println!("Sidecar not found, using python server.py");
    Ok(("python".to_string(), vec!["server.py".to_string()]))
}

#[tauri::command]
async fn start_backend(app: tauri::AppHandle, state: State<'_, BackendState>) -> Result<String, String> {
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
    let (server_bin, server_args) = get_server_path(&app)?;
    
    let mut cmd = Command::new(&server_bin);
    
    // Add server.py if using python fallback
    for arg in &server_args {
        cmd.arg(arg);
    }
    
    // Add common arguments
    cmd.arg("--matrix-world")
       .arg(matrix_world.to_string_lossy().to_string());
    
    // Set working directory only if using python (for server.py to find src/)
    if !server_args.is_empty() {
        // Find the project root (relative to the executable)
        if let Some(resource_dir) = app.path().resource_dir().ok() {
            let project_root = if cfg!(dev) {
                // Dev mode: resource_dir is src-tauri/target/debug/
                // Go up 4 levels to reach project root (where server.py lives)
                resource_dir.parent()
                    .and_then(|p| p.parent())
                    .and_then(|p| p.parent())
                    .and_then(|p| p.parent())
                    .unwrap_or(&resource_dir)
            } else {
                // Production: go up 2 levels from resources/binaries
                resource_dir.parent()
                    .and_then(|p| p.parent())
                    .unwrap_or(&resource_dir)
            };
            cmd.current_dir(project_root);
            println!("Working directory: {:?}", project_root);
        }
    }
    
    let child = cmd.spawn()
        .map_err(|e| {
            eprintln!("Failed to start backend: {}", e);
            format!("Failed to start backend: {}", e)
        })?;

    let mut state_guard = state.0.lock().unwrap();
    *state_guard = Some(child);

    println!("Backend started successfully");
    Ok("Backend started".to_string())
}

#[tauri::command]
async fn stop_backend(state: State<'_, BackendState>) -> Result<String, String> {
    println!("Stopping Python backend...");

    if let Some(mut child) = state.0.lock().unwrap().take() {
        child.kill()
            .map_err(|e| format!("Failed to stop backend: {}", e))?;
        println!("Backend stopped successfully");
    } else {
        println!("No backend running");
    }

    Ok("Backend stopped".to_string())
}

#[tauri::command]
async fn check_backend() -> Result<bool, String> {
    use std::time::Duration;

    // Try to connect to the backend
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let response = client.get("http://localhost:8000/")
        .send()
        .await;

    Ok(response.is_ok())
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
async fn open_attachment_path(path: String) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(["/c", "start", "", &path])
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
    }

    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("Failed to open file: {}", e))?;
    }

    println!("✅ Opened: {}", path);
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

#[tauri::command]
async fn check_container_runtime() -> Result<RuntimeInfo, String> {
    // Check Podman first (preferred)
    if let Ok(output) = StdCommand::new("podman").arg("--version").output() {
        if output.status.success() {
            let version = String::from_utf8_lossy(&output.stdout).trim().to_string();
            println!("✅ Found Podman: {}", version);
            return Ok(RuntimeInfo {
                runtime: "podman".to_string(),
                version: Some(version),
                install_guide: None,
            });
        }
    }
    
    // Check Docker as fallback
    if let Ok(output) = StdCommand::new("docker").arg("--version").output() {
        if output.status.success() {
            let version = String::from_utf8_lossy(&output.stdout).trim().to_string();
            println!("✅ Found Docker: {}", version);
            return Ok(RuntimeInfo {
                runtime: "docker".to_string(),
                version: Some(version),
                install_guide: None,
            });
        }
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
        let dmg_path = resource_dir.join("podman").join("Podman.dmg");
        if !dmg_path.exists() {
            return Err("Podman installer not found in bundle".to_string());
        }
        // Open the DMG file
        StdCommand::new("open")
            .arg(&dmg_path)
            .spawn()
            .map_err(|e| format!("Failed to open installer: {}", e))?;
        Ok("Opened Podman installer. Please follow the installation instructions.".to_string())
    }
    
    #[cfg(target_os = "windows")]
    {
        let msi_path = resource_dir.join("podman").join("podman.msi");
        if !msi_path.exists() {
            return Err("Podman installer not found in bundle".to_string());
        }
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

// ─── XQuartz Detection & Installation (macOS) ───

#[derive(serde::Serialize)]
struct XQuartzInfo {
    installed: bool,
    version: Option<String>,
    running: bool,
}

#[tauri::command]
async fn check_xquartz() -> Result<XQuartzInfo, String> {
    #[cfg(target_os = "macos")]
    {
        // Check if XQuartz is installed
        let xquartz_path = std::path::Path::new("/Applications/Utilities/XQuartz.app");
        let installed = xquartz_path.exists();

        let mut version = None;
        let mut running = false;

        if installed {
            // Get version from plist
            if let Ok(output) = StdCommand::new("defaults")
                .args(["read", "/Applications/Utilities/XQuartz.app/Contents/Info.plist", "CFBundleShortVersionString"])
                .output()
            {
                if output.status.success() {
                    version = Some(String::from_utf8_lossy(&output.stdout).trim().to_string());
                }
            }

            // Check if XQuartz is running
            if let Ok(output) = StdCommand::new("pgrep")
                .arg("-x", "X11.bin")
                .output()
            {
                running = output.status.success();
            }
        }

        println!("XQuartz installed: {}, version: {:?}, running: {}", installed, version, running);
        Ok(XQuartzInfo { installed, version, running })
    }

    #[cfg(not(target_os = "macos"))]
    {
        Ok(XQuartzInfo { installed: false, version: None, running: false })
    }
}

#[tauri::command]
async fn install_xquartz(app: tauri::AppHandle) -> Result<String, String> {
    #[cfg(target_os = "macos")]
    {
        let resource_dir = app.path().resource_dir()
            .map_err(|e| format!("Failed to get resource dir: {}", e))?;

        let pkg_path = resource_dir.join("xquartz").join("XQuartz-2.8.5.pkg");
        if !pkg_path.exists() {
            return Err("XQuartz installer not found in bundle".to_string());
        }

        // Open the PKG installer
        StdCommand::new("open")
            .arg(&pkg_path)
            .spawn()
            .map_err(|e| format!("Failed to open installer: {}", e))?;

        Ok("Opened XQuartz installer. Please follow the installation instructions.".to_string())
    }

    #[cfg(not(target_os = "macos"))]
    {
        Err("XQuartz is only available on macOS".to_string())
    }
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
    
    let image_path = resource_dir.join("docker").join("image.tar.gz");
    if !image_path.exists() {
        return Err("Docker image not found in bundle".to_string());
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
        .manage(BackendState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            check_backend,
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
            check_container_runtime,
            install_podman,
            check_xquartz,
            install_xquartz,
            check_image,
            load_image,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
