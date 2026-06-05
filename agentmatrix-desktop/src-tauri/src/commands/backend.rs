use std::collections::HashMap;
use tauri::State;

use crate::ws::types::{AgentStatusData, WsCommand, WsConnectionStatus};
use crate::ws::WsHandle;
use crate::commands::state::AppState;

/// Request system status from the backend via the WS connection.
#[tauri::command]
pub async fn request_system_status(ws: State<'_, WsHandle>) -> Result<(), String> {
    ws.cmd_tx
        .send(WsCommand::SendSystemStatusRequest)
        .map_err(|e| format!("Failed to send WS command: {}", e))?;
    Ok(())
}

/// Get current WS connection status.
#[tauri::command]
pub fn get_ws_status(state: State<'_, AppState>) -> Result<WsConnectionStatus, String> {
    let status = state.ws_status.lock().map_err(|e| e.to_string())?;
    Ok(status.clone())
}

/// Get all agent statuses from Rust AppState.
#[tauri::command]
pub fn get_agent_statuses(state: State<'_, AppState>) -> Result<HashMap<String, AgentStatusData>, String> {
    let statuses = state.agent_statuses.lock().map_err(|e| e.to_string())?;
    Ok(statuses.clone())
}
