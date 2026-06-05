use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Agent status data from AGENT_STATUS_UPDATE and SYSTEM_STATUS messages.
/// Uses flatten to capture any extra fields from the backend.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AgentStatusData {
    pub status: Option<String>,
    pub current_session_id: Option<String>,
    pub current_user_session_id: Option<String>,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

/// WebSocket connection status
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "state")]
pub enum WsConnectionStatus {
    Disconnected,
    Connecting,
    Connected,
    Reconnecting { attempt: u32, next_retry_ms: u64 },
}

impl Default for WsConnectionStatus {
    fn default() -> Self {
        WsConnectionStatus::Disconnected
    }
}

/// Commands sent from IPC handlers to the WS client task
#[derive(Clone)]
pub enum WsCommand {
    SendSystemStatusRequest,
    #[allow(dead_code)]
    SendMessage(String),
}
