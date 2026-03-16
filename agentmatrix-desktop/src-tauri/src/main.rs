// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Child};
use std::sync::Mutex;
use tauri::State;

// Backend state management
struct BackendState(Mutex<Option<Child>>);

#[tauri::command]
async fn start_backend(state: State<'_, BackendState>) -> Result<String, String> {
    println!("Starting Python backend...");

    let child = Command::new("python")
        .arg("server.py")
        .current_dir("..")
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
async fn show_notification(title: String, body: String) -> Result<(), String> {
    // Simple notification implementation
    // The plugin will handle native notifications
    println!("Notification: {} - {}", title, body);
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .manage(BackendState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            check_backend,
            show_notification
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
