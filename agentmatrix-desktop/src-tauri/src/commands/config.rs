use std::path::PathBuf;
use serde_json::Value as JsonValue;
use serde_yaml;
use crate::config::AppConfig;

/// 扩展 ~ 路径为完整路径（辅助函数）
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

/// 保存 LLM 配置
#[tauri::command]
pub fn save_llm_config(matrix_world_path: String, llm_config: JsonValue) -> Result<(), String> {
    let config_path = expand_path(&matrix_world_path)
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

/// 保存邮件代理配置
#[tauri::command]
pub fn save_email_proxy_config_cmd(matrix_world_path: String, email_proxy: JsonValue) -> Result<(), String> {
    let config_path = expand_path(&matrix_world_path)
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

/// 保存环境变量文件
#[tauri::command]
pub fn save_env_file(matrix_world_path: String, env_vars: JsonValue) -> Result<(), String> {
    let env_path = expand_path(&matrix_world_path)
        .join(".matrix/configs/.env");

    if let Some(parent) = env_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create directory: {}", e))?;
    }

    let mut content = String::new();
    if let Some(obj) = env_vars.as_object() {
        for (key, value) in obj {
            if let Some(val_str) = value.as_str() {
                content.push_str(&format!("{}={}\n", key, val_str));
            }
        }
    }

    std::fs::write(&env_path, content)
        .map_err(|e| format!("Failed to write .env: {}", e))?;

    println!("✅ Saved .env to {:?}", env_path);
    Ok(())
}

/// 获取应用配置
#[tauri::command]
pub async fn get_config() -> Result<AppConfig, String> {
    let config = AppConfig::load()?;
    Ok(config)
}

/// 更新应用配置
#[tauri::command]
pub async fn update_config(matrix_world_path: Option<String>, auto_start_backend: Option<bool>, enable_notifications: Option<bool>) -> Result<AppConfig, String> {
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

/// 检查是否首次运行
#[tauri::command]
pub async fn is_first_run() -> Result<bool, String> {
    let config = AppConfig::load()?;
    Ok(config.is_first_run())
}

/// 标记应用已配置
#[tauri::command]
pub async fn mark_configured(matrix_world_path: String) -> Result<(), String> {
    let mut config = AppConfig::load()?;
    config.matrix_world_path = matrix_world_path;
    config.save()?;
    println!("✅ Config saved");
    Ok(())
}
