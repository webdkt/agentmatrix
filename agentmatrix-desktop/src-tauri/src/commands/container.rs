use std::process::Command as StdCommand;
use serde::{Serialize};
use tauri::Manager;

#[derive(Serialize)]
pub struct RuntimeInfo {
    pub runtime: String,  // "docker", "podman", or "none"
    pub version: Option<String>,
    pub path: Option<String>,  // absolute path to the executable
    pub install_guide: Option<String>,
}

#[derive(Serialize)]
pub struct ImageInfo {
    pub exists: bool,
    pub size: Option<String>,
}

/// Find an executable by trying direct lookup first, then common install paths,
/// and finally a login shell which inherits the user's full PATH.
fn find_executable(name: &str) -> Option<String> {
    // 1. Direct lookup (works if the binary is already in the process PATH)
    if let Ok(output) = StdCommand::new(name).arg("--version").output() {
        if output.status.success() {
            return Some(name.to_string());
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
                    return Some(p.clone());
                }
            }
        }
        // 3. Last resort: query the user's login shell for the full PATH
        //    Use `which` to resolve the absolute path so callers can execute
        //    it directly without relying on a full shell PATH.
        if let Ok(output) = StdCommand::new("zsh")
            .args(["-l", "-c", &format!("which {}", name)])
            .output()
        {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !path.is_empty() {
                    return Some(path);
                }
            }
        }
    }

    None
}

/// Resolve the available container runtime binary (podman preferred, then docker).
fn find_container_runtime() -> Result<String, String> {
    find_executable("podman")
        .or_else(|| find_executable("docker"))
        .ok_or_else(|| "No container runtime (podman/docker) found".to_string())
}

/// 检查容器镜像是否存在
#[tauri::command]
pub async fn check_image() -> Result<ImageInfo, String> {
    // Resolve runtime path (GUI apps don't inherit shell PATH on macOS)
    let runtime_bin = find_container_runtime()?;

    // Check if agentmatrix:latest image exists
    if let Ok(output) = StdCommand::new(&runtime_bin)
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

/// 加载容器镜像（从应用资源中）
#[tauri::command]
pub async fn load_image(app: tauri::AppHandle) -> Result<String, String> {
    let resource_dir = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;

    let image_path = resource_dir.join("resources").join("docker").join("image.tar.gz");
    if !image_path.exists() {
        return Err(format!("Docker image not found in bundle. Looking for: {:?}", image_path));
    }

    println!("Loading Docker image from: {:?}", image_path);

    // Resolve runtime path (GUI apps don't inherit shell PATH on macOS)
    let runtime_bin = find_container_runtime()?;

    // Load image: gunzip | runtime load
    let output = if cfg!(target_os = "windows") {
        StdCommand::new("cmd")
            .args(["/c", "type", &image_path.to_string_lossy(), "|", "gzip", "-d", "|", &runtime_bin, "load"])
            .output()
            .map_err(|e| format!("Failed to load image: {}", e))?
    } else {
        StdCommand::new("sh")
            .args(["-c", &format!("gunzip -c '{}' | '{}' load", image_path.to_string_lossy(), runtime_bin)])
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

/// 检查容器运行时（Podman 或 Docker）
#[tauri::command]
pub async fn check_container_runtime() -> Result<RuntimeInfo, String> {
    // Check Podman first (preferred)
    if let Some(path) = find_executable("podman") {
        println!("✅ Found Podman at: {}", path);
        return Ok(RuntimeInfo {
            runtime: "podman".to_string(),
            version: None,
            path: Some(path),
            install_guide: None,
        });
    }

    // Check Docker as fallback
    if let Some(path) = find_executable("docker") {
        println!("✅ Found Docker at: {}", path);
        return Ok(RuntimeInfo {
            runtime: "docker".to_string(),
            version: None,
            path: Some(path),
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
        path: None,
        install_guide,
    })
}

/// 安装 Podman
#[tauri::command]
pub async fn install_podman(app: tauri::AppHandle) -> Result<String, String> {
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

/// 初始化 Podman VM
#[tauri::command]
pub async fn init_podman_vm() -> Result<String, String> {
    println!("🔄 Initializing Podman VM...");

    // Check if Podman is installed
    let runtime_info = check_container_runtime().await;
    let runtime_info = runtime_info.map_err(|e| e.to_string())?;

    if runtime_info.runtime != "podman" {
        return Err(format!("Podman is not installed. Runtime: {}", runtime_info.runtime));
    }

    // Use the resolved absolute path so we don't depend on the process PATH
    let podman_bin = runtime_info.path.unwrap_or_else(|| "podman".to_string());

    // Check if VM is already initialized
    let list_output = StdCommand::new(&podman_bin)
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
        let init_output = StdCommand::new(&podman_bin)
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

    // Check if VM is already running
    let vm_running = StdCommand::new(&podman_bin)
        .args(["machine", "list"])
        .output()
        .map(|o| {
            if o.status.success() {
                let stdout = String::from_utf8_lossy(&o.stdout);
                stdout.contains("Currently running")
            } else {
                false
            }
        })
        .unwrap_or(false);

    // Start VM only if not already running
    if vm_running {
        println!("✅ Podman VM is already running");
    } else {
        println!("▶️ Starting Podman VM...");
        let start_output = StdCommand::new(&podman_bin)
            .args(["machine", "start"])
            .output()
            .map_err(|e| format!("Failed to start Podman VM: {}", e))?;

        if !start_output.status.success() {
            let stderr = String::from_utf8_lossy(&start_output.stderr);
            // Ignore "already running" error
            if !stderr.contains("already running") {
                return Err(format!("Failed to start Podman VM: {}", stderr));
            }
        }
    }

    // Wait for Podman to be ready
    for i in 0..30 {
        tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        if StdCommand::new(&podman_bin)
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
