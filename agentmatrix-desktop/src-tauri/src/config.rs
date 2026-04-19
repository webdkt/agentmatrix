use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

const CONFIG_DIR: &str = ".agentmatrix";
const CONFIG_FILE: &str = "settings.json";

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AppConfig {
    pub matrix_world_path: String,
    #[serde(default)]
    pub auto_start_backend: bool,
    #[serde(default)]
    pub enable_notifications: bool,
    #[serde(default)]
    pub log_level: String,
    #[serde(default)]
    pub container_packages_initialized: bool,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            matrix_world_path: "~/MatrixWorld".to_string(),
            auto_start_backend: true,
            enable_notifications: true,
            log_level: "INFO".to_string(),
            container_packages_initialized: false,
        }
    }
}

impl AppConfig {
    pub fn get_config_dir() -> Result<PathBuf, String> {
        let home_dir = std::env::var("HOME")
            .or_else(|_| std::env::var("USERPROFILE"))
            .map_err(|_| "Could not find home directory")?;

        let config_dir = PathBuf::from(home_dir).join(CONFIG_DIR);

        if !config_dir.exists() {
            fs::create_dir_all(&config_dir)
                .map_err(|e| format!("Failed to create config directory: {}", e))?;
        }

        Ok(config_dir)
    }

    pub fn get_config_path() -> Result<PathBuf, String> {
        let config_dir = Self::get_config_dir()?;
        Ok(config_dir.join(CONFIG_FILE))
    }

    pub fn load() -> Result<Self, String> {
        let config_path = Self::get_config_path()?;

        if !config_path.exists() {
            return Ok(Self::default());
        }

        let config_str = fs::read_to_string(&config_path)
            .map_err(|e| format!("Failed to read config file: {}", e))?;

        let config: Self = serde_json::from_str(&config_str)
            .map_err(|e| format!("Failed to parse config file: {}", e))?;

        Ok(config)
    }

    pub fn save(&self) -> Result<(), String> {
        let config_path = Self::get_config_path()?;

        let config_str = serde_json::to_string_pretty(self)
            .map_err(|e| format!("Failed to serialize config: {}", e))?;

        fs::write(&config_path, config_str)
            .map_err(|e| format!("Failed to write config file: {}", e))?;

        Ok(())
    }

    pub fn get_matrix_world_path(&self) -> PathBuf {
        let path_str = if self.matrix_world_path.starts_with("~/") {
            if let Ok(home) = std::env::var("HOME") {
                PathBuf::from(home)
                    .join(&self.matrix_world_path[2..])
                    .to_string_lossy()
                    .to_string()
            } else {
                self.matrix_world_path.clone()
            }
        } else {
            self.matrix_world_path.clone()
        };

        if path_str.starts_with('.') || !path_str.starts_with('/') {
            let desktop_dir = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
            let parent_dir = desktop_dir.parent().unwrap_or(&desktop_dir);
            parent_dir.join(&path_str)
        } else {
            PathBuf::from(path_str)
        }
    }

    /// Cold start detection based on file system state, not flags.
    ///
    /// Returns true (needs wizard) if:
    ///   1. No ~/.agentmatrix/settings.json
    ///   2. Settings exist but matrix_world_path directory doesn't exist
    ///   3. Directory exists but .matrix/configs/llm_config.json doesn't exist
    pub fn is_first_run(&self) -> bool {
        // Force wizard via env var
        if std::env::var("AGENTMATRIX_FORCE_WIZARD").is_ok() {
            return true;
        }

        // Check 1: settings.json exists?
        let config_path = match Self::get_config_path() {
            Ok(p) => p,
            Err(_) => return true,
        };
        if !config_path.exists() {
            return true;
        }

        // Check 2: matrix_world_path directory exists?
        let world_path = self.get_matrix_world_path();
        if !world_path.exists() {
            return true;
        }

        // Check 3: .matrix/configs/llm_config.json exists?
        let llm_config = world_path
            .join(".matrix")
            .join("configs")
            .join("llm_config.json");
        if !llm_config.exists() {
            return true;
        }

        false
    }
}
