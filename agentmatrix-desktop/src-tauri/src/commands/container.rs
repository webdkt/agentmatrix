use std::process::Command as StdCommand;
use serde::{Serialize};

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
