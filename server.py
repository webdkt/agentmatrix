#!/usr/bin/env python3
"""
AgentMatrix Server
"""
import os
import sys
import json
import argparse
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import AgentMatrix
from agentmatrix import AgentMatrix


# === Parse Command-Line Arguments at Module Level ===

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="AgentMatrix Server")
    parser.add_argument(
        "--matrix-world",
        type=str,
        default="./MatrixWorld",
        help="Path to the Matrix World directory (default: ./MatrixWorld)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    return parser.parse_args()


# Parse args at module import time
args = parse_args()

# Set path variables based on parsed args
matrix_world_dir = Path(args.matrix_world).resolve()
agents_dir = matrix_world_dir / "agents"
workspace_dir = matrix_world_dir / "workspace"
llm_config_path = agents_dir / "llm_config.json"
active_websockets = []

# Global AgentMatrix runtime instance
matrix_runtime = None


# === Configuration Models ===

class LLMConfig(BaseModel):
    """LLM configuration model"""
    url: str
    api_key: str
    model_name: str


class LLMConfigsRequest(BaseModel):
    """LLM configurations request model"""
    default_llm: LLMConfig
    default_slm: LLMConfig


class SendEmailRequest(BaseModel):
    """Send email request model"""
    user_session_id: Optional[str] = None  # None = new session, str = existing session
    recipient: str
    subject: str
    body: str
    in_reply_to: Optional[str] = None


# === Helper Functions ===

def check_cold_start(config_path: Path) -> bool:
    """Check if this is a cold start (no LLM config exists)"""
    if not config_path or not config_path.exists():
        return True
    return False


def create_directory_structure(matrix_world_dir: Path):
    """创建 Matrix World 目录结构并复制模板"""
    import shutil

    template_dir = Path(__file__).resolve().parent / "web" / "matrix_template"
    if not template_dir.exists():
        raise FileNotFoundError(f"Matrix template directory not found: {template_dir}")

    # 创建根目录
    matrix_world_dir.mkdir(parents=True, exist_ok=True)

    # 直接复制整个 template 到 Matrix World 根目录
    shutil.copytree(template_dir, matrix_world_dir, dirs_exist_ok=True)
    print(f"✅ Copied matrix template from {template_dir}")


def save_llm_configs(configs: dict, config_path: Path):
    """Save LLM configurations to file"""
    llm_config_data = {}
    for name, config in configs.items():
        llm_config_data[name] = {
            "url": config.url,
            "API_KEY": config.api_key,
            "model_name": config.model_name
        }

    config_path.write_text(json.dumps(llm_config_data, indent=4))


# === Lifespan Management ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global matrix_runtime

    # Get config from app.state
    config = app.state.config

    # Startup
    print(f"🚀 Starting AgentMatrix Server...")
    print(f"📁 Matrix World Directory: {config['matrix_world_dir']}")

    # Check if this is cold start
    is_cold_start = check_cold_start(config['llm_config_path'])
    if is_cold_start:
        print("❄️  Cold start detected - LLM configuration required")
        create_directory_structure(config['matrix_world_dir'])
    else:
        print("✅ Configuration found - warm start")

        # Initialize AgentMatrix runtime
        try:
            print("🔧 Initializing AgentMatrix runtime...")

            # Create event callback for WebSocket broadcasting
            async def event_callback(event):
                """Callback to broadcast runtime events to WebSocket clients"""
                try:
                    message = json.dumps({
                        "type": "runtime_event",
                        "data": str(event)
                    })
                    # Send to all active WebSocket connections
                    for ws in active_websockets[:]:  # Copy list to avoid modification during iteration
                        try:
                            await ws.send_text(message)
                        except Exception as e:
                            print(f"⚠️  Error sending to WebSocket: {e}")
                            active_websockets.remove(ws)
                except Exception as e:
                    print(f"⚠️  Error in event callback: {e}")

            # Initialize AgentMatrix
            matrix_runtime = AgentMatrix(
                agent_profile_path=str(config['agents_dir']),
                matrix_path=str(config['workspace_dir']),
                async_event_callback=event_callback
            )

            # Store runtime in app.state for API access
            app.state.matrix = matrix_runtime

            # Set up User agent's mail callback to push emails via WebSocket
            if "User" in matrix_runtime.agents:
                async def user_mail_callback(email):
                    """Callback to push User agent's received emails to WebSocket clients"""
                    try:
                        # Convert email to dict for JSON serialization
                        email_data = {
                            "id": email.id,
                            "timestamp": email.timestamp.isoformat(),
                            "sender": email.sender,
                            "recipient": email.recipient,
                            "subject": email.subject,
                            "body": email.body,
                            "in_reply_to": email.in_reply_to,
                            "user_session_id": email.user_session_id
                        }

                        message = json.dumps({
                            "type": "new_email",
                            "data": email_data
                        })

                        # Send to all active WebSocket connections
                        for ws in active_websockets[:]:
                            try:
                                await ws.send_text(message)
                            except Exception as e:
                                print(f"⚠️  Error sending email to WebSocket: {e}")
                                active_websockets.remove(ws)

                        print(f"📧 User received email from {email.sender}: {email.subject}")
                    except Exception as e:
                        print(f"⚠️  Error in user mail callback: {e}")

                # Set the mail handler for User agent
                matrix_runtime.agents["User"].set_mail_handler(user_mail_callback)
                print("✅ User agent mail callback configured")
            else:
                print("⚠️  Warning: User agent not found in runtime")

            print(f"✅ AgentMatrix runtime initialized successfully")
            print(f"🤖 Loaded agents: {list(matrix_runtime.agents.keys())}")

        except Exception as e:
            print(f"❌ Failed to initialize AgentMatrix runtime: {e}")
            import traceback
            traceback.print_exc()
            matrix_runtime = None
            app.state.matrix = None

    yield

    # Shutdown
    print("👋 Shutting down AgentMatrix Server...")
    if matrix_runtime:
        try:
            print("💾 Saving Matrix state...")
            await matrix_runtime.save_matrix()
            print("✅ Matrix state saved successfully")
        except Exception as e:
            print(f"⚠️  Error saving Matrix state: {e}")


# === FastAPI Application ===

app = FastAPI(
    title="AgentMatrix",
    description="An intelligent agent framework with pluggable skills and LLM integrations",
    version="0.1.4",
    lifespan=lifespan
)

# Store configuration in app.state
app.state.config = {
    "matrix_world_dir": matrix_world_dir,
    "agents_dir": agents_dir,
    "workspace_dir": workspace_dir,
    "llm_config_path": llm_config_path,
    "host": args.host,
    "port": args.port,
    "reload": args.reload
}


# === Static Files ===

# Mount the web directory for static files
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


# === WebSocket Endpoint ===

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()
    active_websockets.append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # TODO: Handle different message types
            # For now, just echo back
            response = {
                "type": "echo",
                "data": message
            }
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        active_websockets.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)


# === API Endpoints ===

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main application or wizard based on configuration status"""
    config = app.state.config
    is_cold = check_cold_start(config['llm_config_path'])

    if is_cold:
        # Cold start - show configuration wizard
        wizard_path = WEB_DIR / "wizard.html"
        return HTMLResponse(wizard_path.read_text())
    else:
        # Warm start - show main application
        index_path = WEB_DIR / "index.html"
        return HTMLResponse(index_path.read_text())


@app.get("/api/config/status")
async def get_config_status():
    """Check if the system is configured (cold/warm start)"""
    config = app.state.config
    is_cold = check_cold_start(config['llm_config_path'])

    return {
        "configured": not is_cold,
        "matrix_world_dir": str(config['matrix_world_dir']),
        "agents_dir": str(config['agents_dir']),
        "workspace_dir": str(config['workspace_dir'])
    }


@app.post("/api/config/llm")
async def save_llm_config(configs: LLMConfigsRequest):
    """Save LLM configurations"""
    try:
        config = app.state.config
        # Convert Pydantic models to dict
        configs_dict = {
            "default_llm": configs.default_llm,
            "default_slm": configs.default_slm
        }

        save_llm_configs(configs_dict, config['llm_config_path'])

        return {
            "success": True,
            "message": "LLM configuration saved successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def get_sessions():
    """Get all user sessions"""
    config = app.state.config
    sessions_file = config['workspace_dir'] / ".matrix" / "user_sessions.json"

    if not sessions_file.exists():
        raise HTTPException(status_code=404, detail="user_sessions.json not found")

    data = json.loads(sessions_file.read_text())

    # Convert to list and sort by last_email_time descending
    sessions_list = []
    for session_id, session_data in data.items():
        sessions_list.append({
            "session_id": session_id,
            "name": session_data["name"],
            "last_email_time": session_data["last_email_time"]
        })

    sessions_list.sort(key=lambda x: x["last_email_time"], reverse=True)

    return {
        "success": True,
        "sessions": sessions_list,
        "total_count": len(sessions_list)
    }


@app.post("/api/sessions/{session_id}/emails")
async def send_email(session_id: str, request: SendEmailRequest):
    """Send an email (new conversation or reply)"""
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    user_agent = matrix_runtime.agents.get("User")
    if not user_agent:
        raise HTTPException(status_code=404, detail="User agent not found")

    # Generate new session_id if None
    user_session_id = request.user_session_id
    if user_session_id is None:
        import uuid
        user_session_id = str(uuid.uuid4())

    # Call User agent's speak method
    await user_agent.speak(
        user_session_id=user_session_id,
        to=request.recipient,
        subject=request.subject,
        content=request.body,
        reply_to_id=request.in_reply_to
    )

    return {
        "success": True,
        "user_session_id": user_session_id,
        "message": "Email sent successfully"
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific session"""
    # TODO: Implement session details retrieval
    return {
        "session_id": session_id,
        "messages": []
    }


@app.get("/api/agents")
async def get_agents():
    """Get all agents"""
    # TODO: Implement agent retrieval
    return {
        "agents": []
    }


@app.get("/api/agents/{agent_name}")
async def get_agent(agent_name: str):
    """Get a specific agent"""
    # TODO: Implement agent details retrieval
    return {
        "name": agent_name
    }


@app.get("/api/files")
async def get_files(path: str = ""):
    """Get files in workspace"""
    # TODO: Implement file listing
    return {
        "files": []
    }


@app.get("/api/system/status")
async def get_system_status():
    """Get system status"""
    return {
        "status": "running",
        "active_websockets": len(active_websockets)
    }


@app.get("/api/runtime/status")
async def get_runtime_status():
    """Get AgentMatrix runtime status"""
    global matrix_runtime

    if matrix_runtime is None:
        return {
            "initialized": False,
            "running": False,
            "agents": []
        }

    try:
        # Get list of agent names
        agent_names = list(matrix_runtime.agents.keys()) if matrix_runtime.agents else []

        return {
            "initialized": True,
            "running": True,
            "agents": agent_names
        }
    except Exception as e:
        return {
            "initialized": True,
            "running": False,
            "agents": [],
            "error": str(e)
        }


# === Main Entry Point ===

def main():
    """Main entry point"""
    import uvicorn

    print("""
    ╔═══════════════════════════════════════╗
    ║       AgentMatrix Server v0.1.4       ║
    ╚═══════════════════════════════════════╝
    """)

    # Args already parsed at module level
    # Access via module-level 'args' variable
    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
