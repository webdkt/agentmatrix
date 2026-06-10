use std::fs;
use std::path::Path;
use std::process::Command as StdCommand;
use serde::Serialize;
use tauri::{Emitter, Manager};

use crate::config::AppConfig;

// ==================== Progress Events ====================

#[derive(Serialize, Clone)]
pub struct PythonEnvProgress {
    pub stage: String,  // "detecting", "downloading", "installing", "creating_venv", "done", "error"
    pub message: String,
}

fn emit_progress(app: &tauri::AppHandle, stage: &str, message: &str) {
    let progress = PythonEnvProgress {
        stage: stage.to_string(),
        message: message.to_string(),
    };
    // Try splash window first, fall back to global emit
    if let Some(splash) = app.get_webview_window("splash") {
        let _ = splash.emit("python-env-progress", &progress);
    } else {
        let _ = app.emit("python-env-progress", &progress);
    }
    println!("[python_env] {} - {}", stage, message);
}

// ==================== Python Detection ====================

/// Parse Python version string like "Python 3.12.1" → (3, 12, 1)
fn parse_python_version(output: &str) -> Option<(u32, u32, u32)> {
    let line = output.lines().next()?;
    let version_str = line.strip_prefix("Python ").or_else(|| line.strip_prefix("python "))?;
    let parts: Vec<&str> = version_str.split('.').collect();
    if parts.len() >= 2 {
        let major = parts[0].parse().ok()?;
        let minor = parts[1].parse().ok()?;
        let patch = parts.get(2).and_then(|s| s.parse().ok()).unwrap_or(0);
        Some((major, minor, patch))
    } else {
        None
    }
}

/// Check if a Python executable is >= 3.12
fn check_python_executable(path: &str) -> Option<String> {
    let output = StdCommand::new(path)
        .arg("--version")
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let version_output = String::from_utf8_lossy(&output.stdout);
    let (major, minor, _patch) = parse_python_version(&version_output)?;

    if major == 3 && minor >= 12 {
        Some(path.to_string())
    } else {
        None
    }
}

/// Find a suitable Python >= 3.12 on the system
fn find_system_python() -> Option<String> {
    // 1. Try "python3" directly
    if let Some(p) = check_python_executable("python3") {
        return Some(p);
    }

    // 2. Try "python"
    if let Some(p) = check_python_executable("python") {
        return Some(p);
    }

    // 3. Try common macOS paths (GUI apps don't inherit shell PATH)
    #[cfg(target_os = "macos")]
    {
        let candidates = [
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python",
            "/usr/local/bin/python",
        ];
        for path in &candidates {
            if let Some(p) = check_python_executable(path) {
                return Some(p);
            }
        }
        // 4. Last resort: query login shell
        if let Ok(output) = StdCommand::new("zsh")
            .args(["-l", "-c", "which python3"])
            .output()
        {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !path.is_empty() {
                    if let Some(p) = check_python_executable(&path) {
                        return Some(p);
                    }
                }
            }
        }
    }

    // 3b. Linux paths
    #[cfg(target_os = "linux")]
    {
        let candidates = [
            "/usr/bin/python3",
            "/usr/local/bin/python3",
        ];
        for path in &candidates {
            if let Some(p) = check_python_executable(path) {
                return Some(p);
            }
        }
    }

    // 3c. Windows
    #[cfg(target_os = "windows")]
    {
        // python launcher (py) can find installed versions
        if let Ok(output) = StdCommand::new("py").args(["-3", "--version"]).output() {
            if output.status.success() {
                let version_output = String::from_utf8_lossy(&output.stdout);
                if let Some((major, minor, _)) = parse_python_version(&version_output) {
                    if major == 3 && minor >= 12 {
                        // Use py launcher to get the actual path
                        if let Ok(path_output) = StdCommand::new("py").args(["-3", "-c", "import sys; print(sys.executable)"]).output() {
                            if path_output.status.success() {
                                let path = String::from_utf8_lossy(&path_output.stdout).trim().to_string();
                                if !path.is_empty() {
                                    return Some(path);
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    None
}

// ==================== Venv Creation ====================

/// Create venv using a Python executable
fn create_venv(python_path: &str, venv_path: &Path) -> Result<(), String> {
    let output = StdCommand::new(python_path)
        .args(["-m", "venv", venv_path.to_str().unwrap()])
        .output()
        .map_err(|e| format!("Failed to create venv: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("venv creation failed: {}", stderr));
    }

    Ok(())
}

/// Get the path to the shared_env_requirements.txt resource file.
/// Dev mode: uses CARGO_MANIFEST_DIR; production: uses Tauri resource dir.
fn get_requirements_path(app: &tauri::AppHandle) -> Result<std::path::PathBuf, String> {
    #[cfg(debug_assertions)]
    {
        let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
            .unwrap_or_else(|_| ".".to_string());
        let path = std::path::PathBuf::from(manifest_dir)
            .join("resources")
            .join("shared_env_requirements.txt");
        if path.exists() {
            return Ok(path);
        }
    }

    let resource_dir = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;
    let path = resource_dir.join("resources").join("shared_env_requirements.txt");
    if path.exists() {
        Ok(path)
    } else {
        Err(format!("shared_env_requirements.txt not found at {:?}", path))
    }
}

/// Install packages into the shared venv from requirements file.
/// Failures are logged but do NOT block app startup.
fn install_packages(app: &tauri::AppHandle, venv_python: &str, requirements_path: &Path) -> Result<(), String> {
    let pip_path = if cfg!(target_os = "windows") {
        let mut p = std::path::PathBuf::from(venv_python);
        p.pop();
        p.push("pip.exe");
        p
    } else {
        let mut p = std::path::PathBuf::from(venv_python);
        p.pop();
        p.push("pip3");
        p
    };

    if !pip_path.exists() {
        eprintln!("[python_env] pip not found at {:?}, skipping package installation", pip_path);
        emit_progress(&app, "installing_packages", "pip not found, skipping package installation.");
        return Ok(());
    }

    emit_progress(&app, "installing_packages", "Installing packages into shared environment...");

    let requirements_str = requirements_path.to_string_lossy().to_string();
    let output = StdCommand::new(&pip_path)
        .args(["install", "--no-cache-dir", "-r", &requirements_str])
        .output()
        .map_err(|e| format!("Failed to run pip: {}", e))?;

    if output.status.success() {
        emit_progress(&app, "installing_packages", "Packages installed successfully.");
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        eprintln!(
            "[python_env] pip install failed (non-blocking):\nstdout: {}\nstderr: {}",
            stdout, stderr
        );
        emit_progress(&app, "installing_packages", "Some packages failed to install, continuing...");
    }

    Ok(())
}

/// Verify a venv's python works and meets version requirement
fn verify_venv(venv_path: &Path) -> Result<String, String> {
    let python_path = if cfg!(target_os = "windows") {
        venv_path.join("Scripts").join("python.exe")
    } else {
        venv_path.join("bin").join("python3")
    };

    if !python_path.exists() {
        return Err(format!("venv python not found at {:?}", python_path));
    }

    let output = StdCommand::new(&python_path)
        .arg("--version")
        .output()
        .map_err(|e| format!("Failed to run venv python: {}", e))?;

    if !output.status.success() {
        return Err("venv python returned non-zero exit code".to_string());
    }

    let version_output = String::from_utf8_lossy(&output.stdout);
    let (major, minor, _) = parse_python_version(&version_output)
        .ok_or_else(|| format!("Cannot parse python version: {}", version_output))?;

    if major < 3 || (major == 3 && minor < 12) {
        return Err(format!("venv python version {}.{} is too old, need >= 3.12", major, minor));
    }

    Ok(python_path.to_string_lossy().to_string())
}

// ==================== Bundled Python (production) ====================

/// Get the path to the bundled standalone Python in app resources.
/// In production, this Python is packaged by CI and MUST exist.
/// In dev mode, returns None (use system Python instead).
fn get_bundled_python() -> Option<String> {
    if cfg!(dev) {
        return None;
    }

    // Production: use Tauri resource dir
    // Note: we can't use tauri::AppHandle here, so resolve resource dir from executable path
    let exe_dir = std::env::current_exe().ok()?
        .parent()?
        .to_path_buf();

    // On macOS .app bundle: <App>.app/Contents/Resources/resources/python_standalone/
    // The Tauri resource_dir is typically Contents/Resources/
    let candidates = vec![
        exe_dir.join("../Resources/resources/python_standalone"),
        exe_dir.join("resources/python_standalone"),
    ];

    for base in candidates {
        let python_path = if cfg!(target_os = "windows") {
            base.join("python.exe")
        } else {
            base.join("bin").join("python3")
        };
        if python_path.exists() {
            return Some(python_path.to_string_lossy().to_string());
        }
    }

    None
}

// ==================== Tauri Commands ====================

/// Check if the shared Python environment already exists
#[tauri::command]
pub async fn check_python_env() -> Result<Option<String>, String> {
    let config = AppConfig::load()?;
    if !config.python_env_ready {
        return Ok(None);
    }

    let venv_path = config.get_matrix_world_path().join(".shared_env");
    match verify_venv(&venv_path) {
        Ok(python_path) => Ok(Some(python_path)),
        Err(_) => Ok(None),
    }
}

/// Ensure a shared Python environment exists. Creates one if needed.
///
/// Strategy:
/// 1. Check if venv already exists → return
/// 2. Production: use bundled standalone Python (from resources/python_standalone/)
/// 3. Dev: find system Python >= 3.12
#[tauri::command]
pub async fn ensure_python_env(app: tauri::AppHandle) -> Result<String, String> {
    let config = AppConfig::load()?;
    let workspace = config.get_matrix_world_path();
    let shared_env = workspace.join(".shared_env");

    // 1. Check if venv already exists and is valid
    if config.python_env_ready {
        if let Ok(python_path) = verify_venv(&shared_env) {
            println!("[python_env] Shared env already exists: {}", python_path);
            return Ok(python_path);
        }
        println!("[python_env] Existing env invalid, recreating...");
    }

    // 2. Find Python source for venv creation
    emit_progress(&app, "detecting", "Preparing Python environment...");

    let python_path = if let Some(path) = get_bundled_python() {
        // Production: use the bundled standalone Python
        emit_progress(&app, "detecting", &format!("Using bundled Python: {}", path));
        path
    } else if cfg!(dev) {
        // Dev mode: find system Python
        emit_progress(&app, "detecting", "Searching for system Python >= 3.12...");
        if let Some(path) = find_system_python() {
            emit_progress(&app, "detecting", &format!("Found system Python: {}", path));
            path
        } else {
            return Err(
                "No Python >= 3.12 found on this system.\n\n\
                 In dev mode, please install Python 3.12+ (e.g. `brew install python@3.12`)."
                    .to_string(),
            );
        }
    } else {
        // Production but bundled Python missing — this is a build error
        return Err(
            "Bundled Python not found in app resources.\n\n\
             This is a BUILD ERROR: the app was not packaged correctly.\n\
             Expected: resources/python_standalone/bin/python3"
                .to_string(),
        );
    };

    // 3. Create shared venv
    emit_progress(&app, "creating_venv", &format!("Creating shared venv from {}...", python_path));

    // Remove existing venv if present (invalid state)
    if shared_env.exists() {
        fs::remove_dir_all(&shared_env)
            .map_err(|e| format!("Failed to remove old venv: {}", e))?;
    }

    create_venv(&python_path, &shared_env)?;

    // 4. Verify
    let venv_python = verify_venv(&shared_env)?;
    emit_progress(&app, "done", &format!("Shared Python environment ready: {}", venv_python));

    // 5. Install packages into the shared venv (non-blocking on failure)
    if let Ok(req_path) = get_requirements_path(&app) {
        if let Err(e) = install_packages(&app, &venv_python, &req_path) {
            eprintln!("[python_env] Package installation error: {}", e);
        }
    } else {
        eprintln!("[python_env] Requirements file not found, skipping package installation.");
    }

    // 6. Save config
    let mut config = AppConfig::load()?;
    config.python_env_ready = true;
    config.python_env_path = Some(venv_python.clone());
    config.save()?;

    Ok(venv_python)
}
