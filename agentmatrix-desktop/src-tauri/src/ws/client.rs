use std::sync::atomic::Ordering;
use std::time::Duration;

use futures_util::{SinkExt, StreamExt};
use tauri::{AppHandle, Emitter, Manager};
use tokio::sync::{broadcast, watch};
use tokio_tungstenite::{connect_async, tungstenite::Message};

use crate::commands::state::AppState;
use crate::BackendState;
use super::types::{AgentStatusData, WsCommand, WsConnectionStatus};

const CONNECT_TIMEOUT_SECS: u64 = 10;

/// Spawn the WebSocket manager as a long-lived tokio task.
/// It manages the connection lifecycle: connect, read messages,
/// handle disconnects with exponential backoff, and forward
/// incoming messages to all Tauri windows via app.emit().
pub fn spawn_ws_manager(
    app: AppHandle,
    cmd_tx: broadcast::Sender<WsCommand>,
    mut shutdown_rx: watch::Receiver<bool>,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let mut reconnect_delay = 1u64;
        let max_delay = 30u64;
        let mut attempt: u32 = 0;

        loop {
            // Check shutdown signal
            if *shutdown_rx.borrow() {
                println!("[WS] Shutdown signal received, exiting manager");
                break;
            }

            // Get backend port
            let port = {
                let state = app.state::<BackendState>();
                state.port.load(Ordering::SeqCst)
            };
            if port == 0 {
                // Backend not ready yet, wait
                tokio::time::sleep(Duration::from_secs(1)).await;
                continue;
            }

            let ws_url = format!("ws://localhost:{}/ws", port);

            // Update status to Connecting
            update_ws_status(&app, WsConnectionStatus::Connecting);

            // Attempt connection with timeout (BUG 3: prevents blocking on dead endpoints)
            match tokio::time::timeout(
                Duration::from_secs(CONNECT_TIMEOUT_SECS),
                connect_async(&ws_url),
            ).await {
                Ok(Ok((ws_stream, _))) => {
                    reconnect_delay = 1; // Reset backoff on success
                    attempt = 0;
                    update_ws_status(&app, WsConnectionStatus::Connected);
                    println!("[WS] Connected to {}", ws_url);

                    let (write, read) = ws_stream.split();
                    let mut cmd_rx = cmd_tx.subscribe();

                    // Run read + write concurrently until one fails
                    let result = run_connection(
                        &app, read, write, &mut cmd_rx, &mut shutdown_rx,
                    ).await;

                    // Connection lost
                    update_ws_status(&app, WsConnectionStatus::Disconnected);
                    match result {
                        Ok(()) => println!("[WS] Connection closed"),
                        Err(e) => eprintln!("[WS] Connection error: {}", e),
                    }
                }
                Ok(Err(e)) => {
                    // Connection failed, backoff
                    attempt += 1;
                    eprintln!("[WS] Connection failed: {} (attempt {}, retry in {}s)", e, attempt, reconnect_delay);
                    update_ws_status(&app, WsConnectionStatus::Reconnecting {
                        attempt,
                        next_retry_ms: reconnect_delay * 1000,
                    });
                    // BUG 4: Check shutdown before sleeping to avoid blocking on quit
                    if wait_or_shutdown(&mut shutdown_rx, Duration::from_secs(reconnect_delay)).await {
                        println!("[WS] Shutdown during reconnect backoff, exiting manager");
                        break;
                    }
                    reconnect_delay = (reconnect_delay * 2).min(max_delay);
                }
                Err(_timeout) => {
                    // Connection timed out
                    attempt += 1;
                    eprintln!("[WS] Connection timed out after {}s (attempt {}, retry in {}s)", CONNECT_TIMEOUT_SECS, attempt, reconnect_delay);
                    update_ws_status(&app, WsConnectionStatus::Reconnecting {
                        attempt,
                        next_retry_ms: reconnect_delay * 1000,
                    });
                    if wait_or_shutdown(&mut shutdown_rx, Duration::from_secs(reconnect_delay)).await {
                        println!("[WS] Shutdown during reconnect backoff, exiting manager");
                        break;
                    }
                    reconnect_delay = (reconnect_delay * 2).min(max_delay);
                }
            }
        }
    })
}

/// Sleep for the given duration, but return early if shutdown is signaled.
/// Returns `true` if shutdown was signaled, `false` if the full duration elapsed.
async fn wait_or_shutdown(shutdown_rx: &mut watch::Receiver<bool>, duration: Duration) -> bool {
    tokio::select! {
        _ = tokio::time::sleep(duration) => false,
        _ = shutdown_rx.changed() => *shutdown_rx.borrow(),
    }
}

/// Run the concurrent read/write loop for a single WS connection.
async fn run_connection(
    app: &AppHandle,
    mut read: futures_util::stream::SplitStream<tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>>,
    mut write: futures_util::stream::SplitSink<tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>, Message>,
    cmd_rx: &mut broadcast::Receiver<WsCommand>,
    shutdown_rx: &mut watch::Receiver<bool>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // Send initial REQUEST_SYSTEM_STATUS (mirrors frontend behavior)
    let msg = serde_json::json!({"type": "REQUEST_SYSTEM_STATUS"});
    write.send(Message::Text(msg.to_string())).await?;

    loop {
        tokio::select! {
            // Incoming message from backend
            msg = read.next() => {
                match msg {
                    Some(Ok(Message::Text(text))) => {
                        handle_incoming_message(app, &text);
                    }
                    Some(Ok(Message::Close(_))) => {
                        println!("[WS] Server sent close frame");
                        let _ = write.close().await;
                        break;
                    }
                    Some(Err(e)) => {
                        let _ = write.close().await;
                        return Err(Box::new(e));
                    }
                    None => {
                        println!("[WS] Stream ended");
                        let _ = write.close().await;
                        break;
                    }
                    _ => {} // Ping/Pong handled automatically by tungstenite
                }
            }
            // Outbound command from frontend (via IPC)
            cmd = cmd_rx.recv() => {
                match cmd {
                    Ok(WsCommand::SendSystemStatusRequest) => {
                        let msg = serde_json::json!({"type": "REQUEST_SYSTEM_STATUS"});
                        if let Err(e) = write.send(Message::Text(msg.to_string())).await {
                            return Err(Box::new(e));
                        }
                    }
                    Ok(WsCommand::SendMessage(text)) => {
                        if let Err(e) = write.send(Message::Text(text)).await {
                            return Err(Box::new(e));
                        }
                    }
                    Err(broadcast::error::RecvError::Lagged(_)) => {
                        eprintln!("[WS] Command channel lagged, skipping");
                        continue;
                    }
                    Err(broadcast::error::RecvError::Closed) => {
                        println!("[WS] Command channel closed");
                        break;
                    }
                }
            }
            // Shutdown signal
            _ = shutdown_rx.changed() => {
                if *shutdown_rx.borrow() {
                    println!("[WS] Shutdown requested, closing connection");
                    let _ = write.close().await;
                    return Ok(());
                }
            }
        }
    }
    Ok(())
}

/// Handle an incoming WS message. Parses minimally for routing,
/// updates AppState where needed, and forwards raw JSON to all windows.
fn handle_incoming_message(app: &AppHandle, text: &str) {
    let envelope: serde_json::Value = match serde_json::from_str(text) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("[WS] Failed to parse message: {}", e);
            return;
        }
    };

    let msg_type = envelope
        .get("type")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    // Update Rust AppState where needed
    match msg_type {
        "AGENT_STATUS_UPDATE" => {
            if let (Some(name), Some(data)) = (
                envelope.get("agent_name").and_then(|v| v.as_str()),
                envelope.get("data"),
            ) {
                if let Ok(status_data) = serde_json::from_value::<AgentStatusData>(data.clone()) {
                    if let Some(state) = app.try_state::<AppState>() {
                        if let Ok(mut statuses) = state.agent_statuses.lock() {
                            statuses.insert(name.to_string(), status_data);
                        }
                    }
                }
            }
        }
        "SYSTEM_STATUS" => {
            if let Some(agents) = envelope.pointer("/data/agents").and_then(|v| v.as_object()) {
                if let Some(state) = app.try_state::<AppState>() {
                    if let Ok(mut statuses) = state.agent_statuses.lock() {
                        for (name, info) in agents {
                            if let Ok(s) = serde_json::from_value::<AgentStatusData>(info.clone()) {
                                statuses.insert(name.clone(), s);
                            }
                        }
                    }
                }
            }
        }
        _ => {}
    }

    // Forward raw JSON to ALL windows — zero data loss
    let event_name = match msg_type {
        "SYSTEM_STATUS" => "ws:system-status",
        "SESSION_EVENT" => "ws:session-event",
        "AGENT_STATUS_UPDATE" => "ws:agent-status-update",
        "NEW_USER_SESSION" => "ws:new-user-session",
        "UI_ACTION_RESULT" => "ws:ui-action-result",
        "COLLAB_BASH_OUTPUT" => "ws:collab-bash-output",
        "SERVICE_EVENT" => "ws:service-event",
        "runtime_event" => "ws:runtime-event",
        "echo" | "error" => return, // protocol-level, no frontend interest
        _ => "ws:message", // BUG 8: forward unknown types instead of silently dropping
    };
    if let Err(e) = app.emit(event_name, &envelope) {
        eprintln!("[WS] Failed to emit {}: {}", event_name, e);
    }
}

/// Update WS connection status in AppState and emit event to frontend.
fn update_ws_status(app: &AppHandle, status: WsConnectionStatus) {
    // Update AppState
    if let Some(state) = app.try_state::<AppState>() {
        if let Ok(mut s) = state.ws_status.lock() {
            *s = status.clone();
        }
    }
    // Emit event for frontend status indicator
    let _ = app.emit("ws:connection-status", &status);
}
