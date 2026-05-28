"""
System info routes: root, status, files, runtime status.
"""

from fastapi import APIRouter

from agentmatrix import __version__
from ..state import server_state

router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint - API information"""
    actual_port = server_state.actual_port or (server_state.args.port if server_state.args else 0)

    return {
        "message": "AgentMatrix API Server",
        "version": __version__,
        "status": "running",
        "desktop_app": {
            "location": "agentmatrix-desktop/",
            "dev_command": "cd agentmatrix-desktop && npm run dev",
            "tauri_command": "cd agentmatrix-desktop && npm run tauri:dev",
        },
        "api_docs": "/docs",
        "endpoints": {
            "websocket": f"ws://localhost:{actual_port}/ws",
            "api_base": "/api",
            "health": "/api/system/status",
        },
        "web_ui": {
            "status": "deprecated",
            "message": "Legacy web UI removed. Use agentmatrix-desktop instead.",
            "desktop_app": "See 'desktop_app' section above",
        },
    }


@router.get("/api/files")
async def get_files(path: str = ""):
    """Get files in workspace"""
    return {"files": []}


@router.get("/api/system/status")
async def get_system_status():
    """Get system status"""
    return {
        "status": "running",
        "active_websockets": len(server_state.active_websockets),
    }


@router.get("/api/runtime/status")
async def get_runtime_status():
    """Get AgentMatrix runtime status"""
    if server_state.matrix_runtime is None:
        return {"initialized": False, "running": False, "agents": []}

    try:
        agent_names = (
            list(server_state.matrix_runtime.agents.keys())
            if server_state.matrix_runtime.agents
            else []
        )
        return {"initialized": True, "running": True, "agents": agent_names}
    except Exception as e:
        return {
            "initialized": True,
            "running": False,
            "agents": [],
            "error": str(e),
        }
