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

// ==================== Micromamba Download ====================

/// Get the micromamba download URL for the current platform
fn get_micromamba_url() -> Option<&'static str> {
    match (std::env::consts::OS, std::env::consts::ARCH) {
        ("macos", "aarch64") => Some("https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-osx-arm64"),
        ("macos", "x86_64") => Some("https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-osx-64"),
        ("linux", "x86_64") => Some("https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64"),
        ("windows", "x86_64") => Some("https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64.exe"),
        _ => None,
    }
}

/// Download a file from URL to the given path
fn download_file(url: &str, dest: &Path) -> Result<(), String> {
    let output = StdCommand::new("curl")
        .args(["-L", "-f", "-o", dest.to_str().unwrap(), url])
        .output()
        .map_err(|e| format!("Failed to run curl: {}. Please install curl.", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Download failed: {}", stderr));
    }

    Ok(())
}

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
/// 2. Find system Python >= 3.12 → use it to create venv
/// 3. No suitable Python → download micromamba, create conda env, then venv
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

    // 2. Try to find system Python
    emit_progress(&app, "detecting", "Searching for Python >= 3.12...");

    let python_path = if let Some(path) = find_system_python() {
        emit_progress(&app, "detecting", &format!("Found system Python: {}", path));
        path
    } else {
        // 3. No system Python — download micromamba
        emit_progress(&app, "downloading", "No suitable Python found. Downloading micromamba...");

        let micromamba_url = get_micromamba_url()
            .ok_or("Unsupported platform for micromamba download")?;

        let tools_dir = workspace.join(".agentmatrix_python");
        fs::create_dir_all(&tools_dir)
            .map_err(|e| format!("Failed to create tools directory: {}", e))?;

        let micromamba_path = if cfg!(target_os = "windows") {
            tools_dir.join("micromamba.exe")
        } else {
            tools_dir.join("micromamba")
        };

        // Download if not already present
        if !micromamba_path.exists() {
            download_file(micromamba_url, &micromamba_path)?;
            // Make executable on Unix
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let mut perms = fs::metadata(&micromamba_path)
                    .map_err(|e| format!("Failed to get micromamba permissions: {}", e))?
                    .permissions();
                perms.set_mode(0o755);
                fs::set_permissions(&micromamba_path, perms)
                    .map_err(|e| format!("Failed to set micromamba permissions: {}", e))?;
            }
            emit_progress(&app, "downloading", "micromamba downloaded successfully.");
        } else {
            emit_progress(&app, "downloading", "Using existing micromamba.");
        }

        // Create conda environment with Python 3.12
        let conda_env_path = tools_dir.join("env");
        emit_progress(&app, "installing", "Creating Python 3.12 environment with micromamba (this may take a few minutes)...");

        let micromamba_str = micromamba_path.to_string_lossy().to_string();
        let conda_env_str = conda_env_path.to_string_lossy().to_string();

        let output = StdCommand::new(&micromamba_str)
            .args([
                "create", "-p", &conda_env_str,
                "python=3.12", "-c", "conda-forge", "-y",
            ])
            .output()
            .map_err(|e| format!("Failed to run micromamba: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            let stdout = String::from_utf8_lossy(&output.stdout);
            return Err(format!(
                "micromamba create failed:\nstdout: {}\nstderr: {}", stdout, stderr
            ));
        }

        emit_progress(&app, "installing", "Python 3.12 environment created.");

        // Find the python in the conda env
        let conda_python = if cfg!(target_os = "windows") {
            conda_env_path.join("python.exe")
        } else {
            conda_env_path.join("bin").join("python3")
        };

        if !conda_python.exists() {
            return Err(format!("Python not found in conda env: {:?}", conda_python));
        }

        conda_python.to_string_lossy().to_string()
    };

    // 4. Create shared venv
    emit_progress(&app, "creating_venv", &format!("Creating shared venv from {}...", python_path));

    // Remove existing venv if present (invalid state)
    if shared_env.exists() {
        fs::remove_dir_all(&shared_env)
            .map_err(|e| format!("Failed to remove old venv: {}", e))?;
    }

    create_venv(&python_path, &shared_env)?;

    // 5. Verify
    let venv_python = verify_venv(&shared_env)?;
    emit_progress(&app, "done", &format!("Shared Python environment ready: {}", venv_python));

    // 6. Save config
    let mut config = AppConfig::load()?;
    config.python_env_ready = true;
    config.python_env_path = Some(venv_python.clone());
    config.save()?;

    Ok(venv_python)
}
