pub mod client;
pub mod types;

use types::WsCommand;

/// Handle for communicating with the WS client task from IPC commands.
pub struct WsHandle {
    pub cmd_tx: tokio::sync::broadcast::Sender<WsCommand>,
    pub shutdown_tx: tokio::sync::watch::Sender<bool>,
    /// JoinHandle of the WS manager task, used to abort on restart
    pub task_handle: tokio::task::JoinHandle<()>,
}
