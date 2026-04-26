/// 显示系统通知
#[tauri::command]
pub async fn show_notification(title: String, body: String) -> Result<(), String> {
    println!("Notification: {} - {}", title, body);
    Ok(())
}
