// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
use commands::container::{check_image, load_image, check_container_runtime, install_podman, init_podman_vm};

use std::process::{Command, Child};
use std::sync::Mutex;
use std::sync::atomic::{AtomicU16, Ordering};
use std::path::PathBuf;
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use tauri::{State, Manager, Emitter, menu::{Menu, MenuItem}, tray::TrayIconBuilder, WindowEvent};
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













// ─── Container Runtime Detection ───

use std::process::Command as StdCommand;

// ─── Auto Setup Container Runtime ───

#[allow(dead_code)]
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
                        Ok(_msg) => {
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

// ─── Initialize Container Packages (for lazy loading) ───

#[derive(Debug, Clone, serde::Serialize)]
struct InstallProgress {
    stage: String,        // core, libreoffice, browsers, npm, complete
    percent: u8,          // 0-100
    message: String,
}

/// 解析安装脚本的 PROGRESS 输出
/// 输入格式: PROGRESS:stage:stage_name:percent:message
fn parse_progress_line(line: &str) -> Option<InstallProgress> {
    if !line.starts_with("PROGRESS:") {
        return None;
    }

    let parts: Vec<&str> = line.trim_start_matches("PROGRESS:").split(':').collect();
    if parts.len() < 4 {
        return None;
    }

    let stage = parts.get(1)?.to_string();
    let percent = parts.get(2)?.parse::<u8>().ok()?;
    let message = parts.get(3)?.to_string();

    Some(InstallProgress {
        stage,
        percent,
        message,
    })
}

/// 过滤安装输出，提取有用的信息
/// 返回简化的消息，None 表示忽略此行
fn filter_install_output(line: &str) -> Option<String> {
    let line = line.trim();

    // 过滤掉无用的行
    if line.is_empty() {
        return None;
    }

    // 过滤掉进度条相关的行（如 [###.......]）
    if line.contains('[') && line.contains("...") && line.contains(']') {
        return None;
    }

    // 过滤掉纯百分比行
    if line.chars().all(|c| c.is_numeric() || c == '%' || c.is_whitespace()) {
        return None;
    }

    // apt-get 输出过滤
    if line.starts_with("Selecting ") || line.starts_with("Preparing ") || line.starts_with("Unpacking ") {
        // 提取包名
        let parts: Vec<&str> = line.split_whitespace().collect();
        if let Some(name) = parts.last() {
            return Some(format!("正在安装: {}", name.trim_end_matches(':')));
        }
    }

    if line.starts_with("Setting up ") {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if let Some(name) = parts.get(2) {
            return Some(format!("配置中: {}", name.trim_end_matches(':')));
        }
    }

    // pip 输出过滤
    if line.contains("Collecting ") {
        if let Some(pkg) = line.split("Collecting ").nth(1) {
            return Some(format!("下载中: {}", pkg.trim()));
        }
    }

    if line.contains("Downloading ") {
        if let Some(pkg) = line.split("Downloading ").nth(1) {
            let pkg_name = pkg.split_whitespace().next().unwrap_or("");
            return Some(format!("下载: {}", pkg_name));
        }
    }

    if line.contains("Installing collected packages") {
        return Some("正在安装已下载的包...".to_string());
    }

    if line.starts_with("Successfully installed ") {
        return Some("✅ 安装成功".to_string());
    }

    // npm 输出过滤
    if line.contains("added ") && line.contains("package") {
        return Some("npm 包安装完成".to_string());
    }

    if line.starts_with("+ ") {
        let pkg = line.trim_start_matches("+ ").trim();
        return Some(format!("npm: {}", pkg));
    }

    // Playwright 输出过滤
    if line.contains("Chromium") {
        return Some(format!("Playwright: {}", line.trim()));
    }

    // 默认：返回原始行（但限制长度）
    if line.len() > 100 {
        Some(format!("{}...", &line[..97]))
    } else {
        Some(line.to_string())
    }
}

/// 初始化容器包（延迟加载）
/// 在 cold start 流程中执行一次，安装重型依赖
/// 注意：此函数会检查 container_packages_initialized 标志，只在第一次安装
async fn initialize_container_packages(
    app: &tauri::AppHandle,
    _state: &BackendState,
) -> Result<(), String> {
    // 检查是否已经初始化过，或者是否是冷启动
    let config = AppConfig::load()?;
    if config.container_packages_initialized {
        println!("✅ 容器包已经初始化过，跳过安装");
        return Ok(());
    }
    if !config.is_first_run() {
        println!("✅ 非冷启动且容器包未标记已初始化，跳过安装");
        return Ok(());
    }

    println!("📦 开始容器初始化（安装重型依赖）...");

    // 1. 获取容器运行时
    let runtime_info = check_container_runtime().await.map_err(|e| e.to_string())?;
    let runtime_bin = runtime_info.path.unwrap_or_else(|| runtime_info.runtime.clone());

    // 2. 使用主容器而不是临时容器
    let container_name = "agentmatrix_shared";
    println!("📥 在主容器中执行初始化: {}", container_name);

    // 获取配置信息
    let matrix_world_path = config.get_matrix_world_path();
    let agents_root = matrix_world_path.join("agent_files");

    // 3. 检查主容器是否存在，不存在则创建
    let check_output = StdCommand::new(&runtime_bin)
        .args(["ps", "-a", "-q", "-f", &format!("name={}", container_name)])
        .output();
    let container_exists = match check_output {
        Ok(output) => output.status.success() && !String::from_utf8_lossy(&output.stdout).trim().is_empty(),
        Err(_) => false,
    };

    if !container_exists {
        println!("🔧 主容器不存在，创建主容器...");

        // 确保宿主机目录存在
        std::fs::create_dir_all(&agents_root)
            .map_err(|e| format!("Failed to create agents_root: {}", e))?;

        // 创建主容器（使用与 Backend 相同的配置）
        let agents_root_str = agents_root.to_str()
            .ok_or_else(|| "Failed to convert agents_root to string".to_string())?;

        let create_output = StdCommand::new(&runtime_bin)
            .args([
                "run",
                "-d",
                "--name", container_name,
                "-v", &format!("{}:/data/agents:rw", agents_root_str),
                "-e", "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "-e", "PYTHONPATH=/data/agents:$PYTHONPATH",
                "--tty",  // TTY 模式
                "agentmatrix:latest",
                "tail", "-f", "/dev/null",  // 保持容器运行
            ])
            .output()
            .map_err(|e| format!("Failed to create main container: {}", e))?;
        if !create_output.status.success() {
            let stderr = String::from_utf8_lossy(&create_output.stderr);
            return Err(format!("Failed to create main container: {}", stderr));
        }
        println!("✅ 主容器已创建");
    } else {
        // 检查容器状态，如果未运行则启动
        let status_output = StdCommand::new(&runtime_bin)
            .args(["inspect", "-f", "{{.State.Status}}", container_name])
            .output();

        if let Ok(output) = status_output {
            let status = String::from_utf8_lossy(&output.stdout);
            let status = status.trim();
            if status != "running" {
                println!("🔄 主容器未运行，启动中...");
                let _ = StdCommand::new(&runtime_bin)
                    .args(["start", container_name])
                    .output();
            }
        }
    }

    // 3. 拷贝并执行初始化脚本
    let script_path = if cfg!(dev) {
        // Dev mode: 使用源代码中的脚本
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("resources")
            .join("container-init-scripts")
            .join("install_packages.sh")
    } else {
        // Production: 使用打包的脚本
        let resource_dir = app.path().resource_dir()
            .map_err(|e| format!("Failed to get resource dir: {}", e))?;
        resource_dir.join("container-init-scripts").join("install_packages.sh")
    };

    let container_script_path = "/tmp/install_packages.sh";

    if !script_path.exists() {
        return Err(format!("脚本文件不存在: {:?}", script_path));
    }

    println!("📄 拷贝脚本到主容器: {:?} -> {}", script_path, container_script_path);

    // 拷贝脚本到主容器
    let copy_output = StdCommand::new(&runtime_bin)
        .args(["cp", script_path.to_str().unwrap(), &format!("{}:{}", container_name, container_script_path)])
        .output()
        .map_err(|e| format!("Failed to copy script: {}", e))?;

    if !copy_output.status.success() {
        let stderr = String::from_utf8_lossy(&copy_output.stderr);
        return Err(format!("拷贝脚本失败: {}", stderr));
    }

    println!("✅ 脚本已拷贝到主容器");

    // 4. 执行初始化脚本并监控进度
    println!("⚙️  在主容器中执行初始化脚本...");

    let mut child = StdCommand::new(&runtime_bin)
        .args(["exec", container_name, "bash", container_script_path])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| {
            format!("Failed to exec install script: {}", e)
        })?;

    // 读取输出并发送进度事件
    let mut stderr_output = String::new();
    let mut stdout_output = String::new();

    if let Some(stdout) = child.stdout.take() {
        use std::io::{BufRead, BufReader};
        let reader = BufReader::new(stdout);

        for line in reader.lines() {
            if let Ok(line_text) = line {
                stdout_output.push_str(&line_text);
                stdout_output.push('\n');

                if let Some(progress) = parse_progress_line(&line_text) {
                    println!("📊 进度: {} - {}% - {}", progress.stage, progress.percent, progress.message);

                    // 发送 Tauri 事件到 splash 窗口
                    if let Some(splash) = app.get_webview_window("splash") {
                        let _ = splash.emit("installation-progress", &progress);
                    } else {
                        // 如果 splash 窗口不存在，使用全局广播作为后备
                        let _ = app.emit("installation-progress", &progress);
                    }
                } else if !line_text.is_empty() {
                    // 过滤并发送有用的安装输出
                    let filtered = filter_install_output(&line_text);
                    if let Some(message) = filtered {
                        println!("📄 {}", message);

                        // 发送真实安装进度到前端
                        let progress = InstallProgress {
                            stage: "install".to_string(),
                            percent: 0,
                            message,
                        };

                        if let Some(splash) = app.get_webview_window("splash") {
                            let _ = splash.emit("installation-progress", &progress);
                        }
                    } else {
                        // 打印所有输出，方便调试
                        println!("📄 {}", line_text);
                    }
                }
            }
        }
    }

    // 读取 stderr（错误信息）
    if let Some(stderr) = child.stderr.take() {
        use std::io::{BufRead, BufReader};
        let reader = BufReader::new(stderr);

        for line in reader.lines() {
            if let Ok(line_text) = line {
                stderr_output.push_str(&line_text);
                stderr_output.push('\n');
                if !line_text.is_empty() {
                    println!("⚠️  STDERR: {}", line_text);
                }
            }
        }
    }

    // 5. 等待脚本完成
    let status = child.wait()
        .map_err(|e| format!("Failed to wait for install script: {}", e))?;

    if !status.success() {
        // 构建详细的错误信息
        let mut error_msg = format!("核心组件安装失败 (退出码: {:?})\n", status.code());
        error_msg.push_str(&format!("\n📤 标准输出:\n{}\n", stdout_output));
        error_msg.push_str(&format!("\n⚠️  错误输出:\n{}\n", stderr_output));

        println!("{}", error_msg);
        return Err(error_msg);
    }

    // 6. 安装成功后，标记为已初始化
    let mut config = AppConfig::load()?;
    config.container_packages_initialized = true;
    config.save()?;
    println!("✅ 已标记容器包为已初始化");

    println!("✅ 容器包初始化完成");

    // 注意：不再删除容器（去掉 cleanup_container 调用）
    // 主容器 agentmatrix_shared 会保留，供 Backend 复用

    Ok(())
}

// ─── Ensure Environment (unified startup: container runtime + backend) ───

async fn ensure_environment_logic(app: &tauri::AppHandle, state: &BackendState) -> Result<(), String> {
    let runtime_info = check_container_runtime().await?;
    if runtime_info.runtime == "none" {
        return Err("No container runtime found. Please install Docker or Podman.".to_string());
    }
    if runtime_info.runtime == "podman" {
        init_podman_vm().await?;
    }

    // 1. 确保容器镜像存在
    ensure_container_image(app.clone()).await?;

    // 2. 初始化容器包（仅在 cold start 时执行一次）
    // 函数内部会检查 container_packages_initialized 标志
    initialize_container_packages(app, state).await?;

    // 3. 启动 backend
    start_backend_logic(app, state).await?;

    Ok(())
}

#[tauri::command]
async fn wizard_complete(app: tauri::AppHandle, state: State<'_, BackendState>) -> Result<(), String> {
    // Close wizard window
    if let Some(wizard) = app.get_webview_window("wizard") {
        let _ = wizard.close();
    }
    // Show splash
    if let Some(splash) = app.get_webview_window("splash") {
        let _ = splash.show();
    }
    // Ensure environment (cold start: init packages)
    match ensure_environment_logic(&app, &state.inner()).await {
        Ok(_) => {
            if let Some(splash) = app.get_webview_window("splash") {
                let _ = splash.close();
            }
            if let Some(main) = app.get_webview_window("main") {
                let _ = main.show();
                let _ = main.set_focus();
            }
            Ok(())
        }
        Err(e) => {
            if let Some(splash) = app.get_webview_window("splash") {
                let _ = splash.close();
            }
            use tauri_plugin_dialog::DialogExt;
            app.dialog()
                .message(format!("Failed to start:\n\n{}\n\nYou can try starting it manually from the tray icon.", e))
                .title("AgentMatrix - Startup Error")
                .show(|_| {});
            Err(e)
        }
    }
}

// ─── Docker Image Management ───

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

            // Check if cold start wizard is needed
            let needs_cold_start = AppConfig::load()
                .map(|config| config.is_first_run())
                .unwrap_or(true);

            println!("🎯 Cold start check: needs_wizard = {}", needs_cold_start);

            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if needs_cold_start {
                    // Cold start: show wizard window
                    println!("🧙 Cold start required, showing wizard");
                    if let Some(wizard) = app_handle.get_webview_window("wizard") {
                        let _ = wizard.show();
                        let _ = wizard.set_focus();
                    }
                } else {
                    // Normal startup: show splash, then ensure environment
                    if let Some(splash) = app_handle.get_webview_window("splash") {
                        let _ = splash.show();
                    }

                    println!("🚀 Starting environment...");
                    let state = app_handle.state::<BackendState>();
                    match ensure_environment_logic(&app_handle, &state).await {
                        Ok(_) => {
                            println!("✅ Environment ready, showing main window");
                            if let Some(splash) = app_handle.get_webview_window("splash") {
                                let _ = splash.close();
                            }
                            if let Some(main) = app_handle.get_webview_window("main") {
                                let _ = main.show();
                                let _ = main.set_focus();
                            }
                        }
                        Err(e) => {
                            eprintln!("Failed to start environment: {}", e);
                            if let Some(splash) = app_handle.get_webview_window("splash") {
                                let _ = splash.close();
                            }
                            use tauri_plugin_dialog::DialogExt;
                            app_handle.dialog()
                                .message(format!(
                                    "Failed to start:\n\n{}\n\nYou can try starting it manually from the tray icon.",
                                    e
                                ))
                                .title("AgentMatrix - Startup Error")
                                .show(|_| {});
                        }
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            check_backend,
            get_backend_port,
            commands::config::get_config,
            commands::config::update_config,
            commands::config::is_first_run,
            commands::config::mark_configured,
            commands::config::select_directory,
            commands::ui::show_notification,
            commands::filesystem::open_attachment_path,
            commands::filesystem::open_folder,
            commands::filesystem::reveal_in_folder,
            commands::filesystem::read_directory,
            commands::ui::open_browser_with_profile,
            init_matrix_world,
            commands::filesystem::copy_file,
            commands::filesystem::file_exists,
            commands::config::save_llm_config,
            commands::config::save_email_proxy_config_cmd,
            commands::config::save_env_file,
            commands::container::check_container_runtime,
            commands::container::install_podman,
            commands::container::check_image,
            commands::container::load_image,
            commands::container::init_podman_vm,
            ensure_container_image,
            wizard_complete,
            commands::ui::is_window_focused,
            commands::ui::show_window,
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
