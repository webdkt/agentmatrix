use tauri::Manager;

/// 显示系统通知
#[tauri::command]
pub async fn show_notification(title: String, body: String) -> Result<(), String> {
    println!("Notification: {} - {}", title, body);
    Ok(())
}

/// 检查窗口是否聚焦
#[tauri::command]
pub async fn is_window_focused(app: tauri::AppHandle) -> Result<bool, String> {
    if let Some(window) = app.get_webview_window("main") {
        return window.is_focused().map_err(|e| e.to_string());
    }
    Ok(false)
}

/// 显示并聚焦窗口
#[tauri::command]
pub async fn show_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 创建浮动 Agent 窗口
#[tauri::command]
pub async fn create_floating_window(
    app: tauri::AppHandle,
    session_id: String,
    agent_name: String,
    agent_session_id: String,
) -> Result<(), String> {
    use tauri::WebviewWindowBuilder;
    use tauri::utils::config::WebviewUrl;

    // If floating window already exists, destroy it first
    if let Some(existing) = app.get_webview_window("floating") {
        let _ = existing.close();
    }

    let base = if cfg!(dev) {
        "http://localhost:5173/floating.html"
    } else {
        "https://tauri.localhost/floating.html"
    };

    let fragment = format!(
        "{}#sessionId={}&agentName={}&agentSessionId={}",
        base, session_id, agent_name, agent_session_id
    );

    let _window = WebviewWindowBuilder::new(&app, "floating", WebviewUrl::External(fragment.parse().map_err(|e| format!("Invalid URL: {}", e))?))
        .title("Floating Agent")
        .inner_size(380.0, 520.0)
        .min_inner_size(300.0, 200.0)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .resizable(true)
        .build()
        .map_err(|e| format!("Failed to create floating window: {}", e))?;

    Ok(())
}

/// 销毁浮动 Agent 窗口
#[tauri::command]
pub async fn destroy_floating_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("floating") {
        window.close().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 最小化主窗口
#[tauri::command]
pub async fn minimize_main_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.minimize().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 恢复主窗口
#[tauri::command]
pub async fn restore_main_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        window.unminimize().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// 使用指定配置文件打开浏览器
#[tauri::command]
pub async fn open_browser_with_profile(profile_path: String) -> Result<(), String> {
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
