use std::sync::Mutex;
use serde::{Deserialize, Serialize};
use tauri::{Emitter, State};

/// 当前会话的全局状态，所有窗口共享
#[derive(Default, Clone, Serialize, Deserialize)]
pub struct CurrentSession {
    pub user_session_id: Option<String>,
    pub agent_session_id: Option<String>,
    pub agent_name: Option<String>,
    pub task_id: Option<String>,
    pub last_email_id: Option<String>,
    pub user_agent_name: Option<String>,
}

/// UI Action 结果的全局状态
#[derive(Default, Clone, Serialize, Deserialize)]
pub struct UIActionResult {
    pub agent_name: Option<String>,
    pub action_name: Option<String>,
    pub result: Option<serde_json::Value>,
    pub display_mode: Option<String>,
}

pub struct AppState {
    pub current_session: Mutex<CurrentSession>,
    pub ui_action_result: Mutex<UIActionResult>,
}

#[tauri::command]
pub fn get_current_session(state: State<'_, AppState>) -> Result<CurrentSession, String> {
    let session = state.current_session.lock().map_err(|e| e.to_string())?;
    Ok(session.clone())
}

#[tauri::command]
pub fn set_current_session(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    session: CurrentSession,
) -> Result<(), String> {
    {
        let mut s = state.current_session.lock().map_err(|e| e.to_string())?;
        *s = session;
    }
    let _ = app.emit("session-changed", ());
    Ok(())
}

#[tauri::command]
pub fn get_ui_action_result(state: State<'_, AppState>) -> Result<UIActionResult, String> {
    let result = state.ui_action_result.lock().map_err(|e| e.to_string())?;
    Ok(result.clone())
}

#[tauri::command]
pub fn set_ui_action_result(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
    result: UIActionResult,
) -> Result<(), String> {
    {
        let mut r = state.ui_action_result.lock().map_err(|e| e.to_string())?;
        *r = result;
    }
    let _ = app.emit("result:changed", ());
    Ok(())
}
