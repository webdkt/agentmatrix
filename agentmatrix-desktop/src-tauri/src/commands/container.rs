use std::process::Command as StdCommand;
use serde::{Serialize};
use tauri::{Emitter, Manager};

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

/// 确保容器镜像已加载
#[tauri::command]
pub async fn ensure_container_image(app: tauri::AppHandle) -> Result<String, String> {
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
pub struct InstallProgress {
    pub stage: String,        // core, libreoffice, browsers, npm, complete
    pub percent: u8,          // 0-100
    pub message: String,
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
#[tauri::command]
pub async fn initialize_container_packages(app: tauri::AppHandle) -> Result<(), String> {
    // 检查是否已经初始化过，或者是否是冷启动
    let config = crate::config::AppConfig::load()?;
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
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
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
    let mut config = crate::config::AppConfig::load()?;
    config.container_packages_initialized = true;
    config.save()?;
    println!("✅ 已标记容器包为已初始化");

    println!("✅ 容器包初始化完成");

    // 注意：不再删除容器（去掉 cleanup_container 调用）
    // 主容器 agentmatrix_shared 会保留，供 Backend 复用

    Ok(())
}
