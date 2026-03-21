// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Child};
use std::sync::Mutex;
use tauri::State;

mod config;
use config::AppConfig;

// Backend state management
struct BackendState(Mutex<Option<Child>>);

#[tauri::command]
async fn start_backend(state: State<'_, BackendState>) -> Result<String, String> {
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

    let child = Command::new("python")
        .arg("server.py")
        .arg("--matrix-world")
        .arg(matrix_world.to_string_lossy().to_string())
        .current_dir("../..")
        .spawn()
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
async fn update_config(matrix_world_path: Option<String>, auto_start_backend: Option<bool>, enable_notifications: Option<bool>, is_configured: Option<bool>) -> Result<AppConfig, String> {
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
    if let Some(configured) = is_configured {
        config.is_configured = configured;
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
    config.is_configured = true;
    config.save()?;
    println!("✅ App marked as configured");
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
            open_attachment_path
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
