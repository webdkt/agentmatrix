use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

const CONFIG_DIR: &str = ".agentmatrix";
const CONFIG_FILE: &str = "settings.json";

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AppConfig {
    pub matrix_world_path: String,
    #[serde(default)]
    pub is_configured: bool,
    #[serde(default)]
    pub auto_start_backend: bool,
    #[serde(default)]
    pub enable_notifications: bool,
    #[serde(default)]
    pub log_level: String,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            matrix_world_path: "~/MatrixWorld".to_string(),
            is_configured: false,
            auto_start_backend: true,
            enable_notifications: true,
            log_level: "INFO".to_string(),
        }
    }
}

impl AppConfig {
    pub fn get_config_dir() -> Result<PathBuf, String> {
        let home_dir = std::env::var("HOME")
            .or_else(|_| std::env::var("USERPROFILE"))
            .map_err(|_| "Could not find home directory")?;

        let config_dir = PathBuf::from(home_dir).join(CONFIG_DIR);

        // Create config directory if it doesn't exist
        if !config_dir.exists() {
            fs::create_dir_all(&config_dir)
                .map_err(|e| format!("Failed to create config directory: {}", e))?;
            println!("Created config directory: {:?}", config_dir);
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
            println!("Config file not found, returning default config (cold start)");
            return Ok(Self::default());
        }

        let config_str = fs::read_to_string(&config_path)
            .map_err(|e| format!("Failed to read config file: {}", e))?;

        let config: Self = serde_json::from_str(&config_str)
            .map_err(|e| format!("Failed to parse config file: {}", e))?;

        println!("Loaded config from: {:?}", config_path);
        Ok(config)
    }

    pub fn save(&self) -> Result<(), String> {
        let config_path = Self::get_config_path()?;

        let config_str = serde_json::to_string_pretty(self)
            .map_err(|e| format!("Failed to serialize config: {}", e))?;

        fs::write(&config_path, config_str)
            .map_err(|e| format!("Failed to write config file: {}", e))?;

        println!("Saved config to: {:?}", config_path);
        Ok(())
    }

    pub fn get_matrix_world_path(&self) -> PathBuf {
        // Expand ~ if present
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

        // If relative path, make it relative to parent of agentmatrix-desktop
        if path_str.starts_with('.') || !path_str.starts_with('/') {
            let desktop_dir = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
            let parent_dir = desktop_dir.parent().unwrap_or(&desktop_dir);
            parent_dir.join(&path_str)
        } else {
            PathBuf::from(path_str)
        }
    }

    pub fn is_first_run(&self) -> bool {
        // Support force-wizard mode for development/testing
        if std::env::var("AGENTMATRIX_FORCE_WIZARD").is_ok() {
            return true;
        }

        if !self.is_configured {
            return true;
        }
        let path = self.get_matrix_world_path();
        !path.exists()
    }
}
