#!/usr/bin/env python3
"""
AgentMatrix Server
"""
import os
import sys
import json
import re
import asyncio
import argparse
from pathlib import Path
from urllib.parse import quote, unquote
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

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
workspace_dir = matrix_world_dir / "workspace"

# 新架构：所有配置集中在 .matrix/configs/
system_dir = matrix_world_dir / ".matrix"
configs_dir = system_dir / "configs"
agents_dir = configs_dir / "agents"
llm_config_path = agents_dir / "llm_config.json"
system_config_path = configs_dir / "system_config.yml"
matrix_config_path = configs_dir / "matrix_config.yml"

active_websockets = []
matrix_runtime = None


# === Broadcast Functions ===

async def broadcast_message_to_clients(message: dict):
    """
    广播消息到所有 WebSocket 客户端

    Args:
        message: 要广播的消息（字典）
    """
    if not active_websockets:
        return

    try:
        json_message = json.dumps(message)

        # 发送给所有活跃的 WebSocket 连接
        websockets_to_remove = []
        for ws in active_websockets:
            try:
                await ws.send_text(json_message)
            except Exception as e:
                print(f"⚠️ Error sending to WebSocket: {e}")
                websockets_to_remove.append(ws)

        # 清理失效的连接
        for ws in websockets_to_remove:
            active_websockets.remove(ws)

    except Exception as e:
        print(f"⚠️ Error in broadcast: {e}")


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


class ColdStartConfigRequest(BaseModel):
    """Complete cold start configuration request model"""
    user_name: str
    default_llm: LLMConfig
    default_slm: LLMConfig


class SendEmailRequest(BaseModel):
    """Send email request model"""
    task_id: Optional[str] = None  # None = new session, str = existing session
    recipient: str
    subject: str
    body: str
    in_reply_to: Optional[str] = None


class AgentConfigRequest(BaseModel):
    """Agent configuration request model - 灵活的Agent配置"""
    name: str
    description: str
    class_name: str = "agentmatrix.agents.base.BaseAgent"  # 新格式：完整类路径
    backend_model: str = "default_llm"
    skills: list = []
    persona: dict = {}
    # 可选配置
    cerebellum: Optional[dict] = None
    vision_brain: Optional[dict] = None
    prompts: Optional[dict] = None
    logging: Optional[dict] = None
    # 保留其他未知字段的灵活性
    extra_fields: Optional[dict] = None


class AgentUpdateRequest(BaseModel):
    """Agent update request model - 灵活的Agent更新"""
    description: Optional[str] = None
    class_name: Optional[str] = None  # 新格式：完整类路径
    backend_model: Optional[str] = None
    skills: Optional[list] = None
    persona: Optional[dict] = None
    cerebellum: Optional[dict] = None
    vision_brain: Optional[dict] = None
    prompts: Optional[dict] = None
    logging: Optional[dict] = None
    # 保留其他未知字段的灵活性
    extra_fields: Optional[dict] = None


class LLMEndpointConfig(BaseModel):
    """Single LLM endpoint configuration"""
    url: str
    api_key: str
    model_name: str


class LLMConfigUpdateRequest(BaseModel):
    """LLM configuration update request"""
    url: str
    api_key: str
    model_name: str


class LLMConfigCreateRequest(BaseModel):
    """LLM configuration create request"""
    name: str
    url: str
    api_key: str
    model_name: str


# === Required LLM Configs ===
REQUIRED_LLM_CONFIGS = ["default_llm", "default_slm", "browser-use-llm"]


# === Helper Functions ===



def check_cold_start(config_path: Path) -> bool:
    """Check if this is a cold start (no LLM config exists)"""
    if not config_path or not config_path.exists():
        return True
    return False


def load_user_agent_name(matrix_world_dir: Path) -> str:
    """Load user agent name from matrix_config.yml configuration file"""
    import yaml

    # 新架构：从 .matrix/configs/matrix_config.yml 读取
    config_path = matrix_world_dir / ".matrix" / "configs" / "matrix_config.yml"
    if not config_path.exists():
        # 向后兼容：尝试从旧的位置读取
        old_config_path = matrix_world_dir / "matrix_world.yml"
        if old_config_path.exists():
            print("⚠️  Warning: Using old matrix_world.yml, please migrate to new structure")
            with open(old_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('user_agent_name', 'User')
        else:
            print("⚠️  Warning: matrix_config.yml not found, using default 'User'")
            return "User"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            user_name = config.get('user_agent_name', 'User')
            return user_name
    except Exception as e:
        print(f"⚠️  Error loading matrix_config.yml: {e}, using default 'User'")
        return "User"


def create_directory_structure(matrix_world_dir: Path, user_name: str):
    """
    创建 Matrix World 目录结构并复制模板，并替换 User agent 名称

    新架构：模板已经是正确的结构，直接复制即可
    """
    import shutil

    template_dir = Path(__file__).resolve().parent / "web" / "matrix_template"
    if not template_dir.exists():
        raise FileNotFoundError(f"Matrix template directory not found: {template_dir}")

    # 创建根目录
    matrix_world_dir.mkdir(parents=True, exist_ok=True)

    # 直接复制整个 template 到 Matrix World 根目录
    shutil.copytree(template_dir, matrix_world_dir, dirs_exist_ok=True)
    print(f"✅ Copied matrix template from {template_dir}")

    # 替换 User.yml 中的 {{USER_NAME}} 占位符
    # 新架构：User.yml 在 .matrix/configs/agents/User.yml
    user_yml_path = matrix_world_dir / ".matrix" / "configs" / "agents" / "User.yml"
    if user_yml_path.exists():
        with open(user_yml_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 替换模板变量
        content = content.replace('{{USER_NAME}}', user_name)

        with open(user_yml_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ User agent configured with name: {user_name}")
    else:
        print(f"⚠️  Warning: {user_yml_path} not found")




def create_world_config(matrix_world_dir: Path, user_name: str):
    """创建 matrix_config.yml 配置文件（新架构）"""
    import yaml

    config = {
        "user_agent_name": user_name,
        "matrix_version": "1.0.0",
        "description": "AgentMatrix World",
        "timezone": "UTC"
    }

    # 新架构：保存到 .matrix/configs/matrix_config.yml
    config_path = matrix_world_dir / ".matrix" / "configs" / "matrix_config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"✅ Created matrix configuration: {config_path}")





# === Graceful Shutdown Handler ===

async def graceful_shutdown():
    """Gracefully shutdown the AgentMatrix runtime"""
    global matrix_runtime, active_websockets
    
    print("\n👋 Shutting down AgentMatrix Server...")
    
    # 1. Close all WebSocket connections
    if active_websockets:
        print(f"📡 Closing {len(active_websockets)} WebSocket connections...")
        for ws in active_websockets[:]:
            try:
                await ws.close()
            except Exception:
                pass
        active_websockets.clear()
        print("✅ WebSocket connections closed")
    
    # 2. Save matrix state with timeout
    if matrix_runtime:
        try:
            print("💾 Saving Matrix state...")
            # Use wait_for to prevent hanging
            await asyncio.wait_for(matrix_runtime.save_matrix(), timeout=10.0)
            print("✅ Matrix state saved successfully")
        except asyncio.TimeoutError:
            print("⚠️  Saving matrix state timed out (10s), forcing shutdown...")
        except asyncio.CancelledError:
            # 🔧 任务被取消（正常情况，不打印错误）
            print("⚠️  Shutdown cancelled by user")
        except Exception as e:
            print(f"⚠️  Error saving Matrix state: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("🧹 Cleaning up runtime resources...")
            # 强制清理，防止内存泄漏
            matrix_runtime = None
            print("✅ Runtime cleaned up")

    print("👋 AgentMatrix Server shutdown complete")


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
        print("❄️  Cold start detected - Waiting for user configuration via wizard")
        # Don't create directory structure here - wait for wizard to complete
        # Runtime will be initialized after wizard completes configuration
        try:
            yield
        finally:
            # Even cold start needs cleanup
            await graceful_shutdown()
        return
    else:
        print("✅ Configuration found - warm start")

        # Load world configuration to get user_agent_name
        user_agent_name = load_user_agent_name(config['matrix_world_dir'])
        print(f"✅ Loaded user agent name: {user_agent_name}")

        # Initialize AgentMatrix runtime
        try:
            print("🔧 Initializing AgentMatrix runtime...")

            # Create event callback for WebSocket broadcasting
            async def event_callback(event):
                """Callback to broadcast runtime events to WebSocket clients"""
                try:
                    # 🔍 调试日志
                    print(f"📡 event_callback called: event_type={event.event_type}")
                    # 特殊处理 SYSTEM_STATUS 事件：直接发送，不包装在 runtime_event 中
                    if event.event_type == "SYSTEM_STATUS":
                        message = json.dumps({
                            "type": "SYSTEM_STATUS",
                            "data": event.payload.get("status", {}) if event.payload else {}
                        })
                        print(f"📊 Broadcasting SYSTEM_STATUS to {len(active_websockets)} clients")
                    else:
                        # 其他事件包装在 runtime_event 中
                        message = json.dumps({
                            "type": "runtime_event",
                            "data": event.to_dict()
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
                matrix_root=str(config['matrix_world_dir']),
                async_event_callback=event_callback,
                user_agent_name=user_agent_name
            )

            # 🔧 注入广播回调
            matrix_runtime.set_broadcast_callback(broadcast_message_to_clients)

            # ✅ 注入广播回调给所有 Agent
            for agent in matrix_runtime.agents.values():
                agent._broadcast_message_callback = matrix_runtime.get_broadcast_callback()
            print("✅ 广播回调已注入到所有 Agent")

            # Validate User agent exists and has correct name
            if user_agent_name not in matrix_runtime.agents:
                raise Exception(f"User agent '{user_agent_name}' not found in loaded agents. Available agents: {list(matrix_runtime.agents.keys())}")

            user_agent = matrix_runtime.agents[user_agent_name]
            if not hasattr(user_agent, 'set_mail_handler'):
                raise Exception(f"Agent '{user_agent_name}' is not a UserProxyAgent (missing set_mail_handler method)")

            print(f"✅ User agent validation passed: '{user_agent_name}'")

            # Store runtime in app.state for API access
            app.state.matrix = matrix_runtime

            # Set up User agent's mail callback to push emails via WebSocket
            user_agent_name = matrix_runtime.get_user_agent_name()
            if user_agent_name in matrix_runtime.agents:
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
                            "task_id": email.task_id,
                            "receiver_session_id": email.receiver_session_id
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
                matrix_runtime.agents[user_agent_name].set_mail_handler(user_mail_callback)
                print(f"✅ User agent mail callback configured for '{user_agent_name}'")
            else:
                print(f"⚠️  Warning: User agent '{user_agent_name}' not found in runtime")

            print(f"✅ AgentMatrix runtime initialized successfully")
            print(f"🤖 Loaded agents: {list(matrix_runtime.agents.keys())}")

        except Exception as e:
            print(f"❌ Failed to initialize AgentMatrix runtime: {e}")
            import traceback
            traceback.print_exc()
            matrix_runtime = None
            app.state.matrix = None

    try:
        yield
    finally:
        await graceful_shutdown()


# === FastAPI Application ===

app = FastAPI(
    title="AgentMatrix",
    description="An intelligent agent framework with pluggable skills and LLM integrations",
    version="0.1.5",
    lifespan=lifespan
)

# Store configuration in app.state
app.state.config = {
    "matrix_world_dir": matrix_world_dir,
    "workspace_dir": workspace_dir,
    "system_dir": system_dir,
    "configs_dir": configs_dir,
    "agents_dir": agents_dir,
    "llm_config_path": llm_config_path,
    "system_config_path": system_config_path,
    "matrix_config_path": matrix_config_path,
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
    global matrix_runtime

    await websocket.accept()
    active_websockets.append(websocket)

    try:
        # ✅ 新连接时立即发送当前完整状态
        if matrix_runtime and hasattr(matrix_runtime, 'status_collector'):
            status = matrix_runtime.status_collector.collect_status()
            await websocket.send_text(json.dumps({
                "type": "SYSTEM_STATUS",
                "data": status
            }))
            print(f"📊 Sent initial status to new client")

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # 🆕 Handle different message types
            if message.get("type") == "REQUEST_SYSTEM_STATUS":
                # 发送当前系统状态
                if matrix_runtime and hasattr(matrix_runtime, 'status_collector'):
                    status = matrix_runtime.status_collector.collect_status()
                    response = {
                        "type": "SYSTEM_STATUS",
                        "data": status
                    }
                    await websocket.send_text(json.dumps(response))
                    print(f"📊 Sent system status to WebSocket client")
                else:
                    # Runtime not initialized
                    response = {
                        "type": "error",
                        "message": "Runtime not initialized"
                    }
                    await websocket.send_text(json.dumps(response))
            else:
                # Echo back for unknown message types
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


@app.get("/api/config")
async def get_config():
    """Get system configuration including user agent name"""
    global matrix_runtime

    config = app.state.config
    is_cold = check_cold_start(config['llm_config_path'])

    response_data = {
        "configured": not is_cold,
        "matrix_world_dir": str(config['matrix_world_dir']),
        "agents_dir": str(config['agents_dir']),
        "workspace_dir": str(config['workspace_dir'])
    }

    # Only include user_agent_name if runtime is initialized
    if matrix_runtime and not is_cold:
        response_data["user_agent_name"] = matrix_runtime.get_user_agent_name()
    else:
        # Try to load from config file even if runtime is not initialized
        user_agent_name = load_user_agent_name(config['matrix_world_dir'])
        response_data["user_agent_name"] = user_agent_name

    return response_data





@app.post("/api/config/complete")
async def complete_cold_start(configs: ColdStartConfigRequest):
    """Complete cold start configuration with user name and LLM configs"""
    try:
        config = app.state.config

        # 1. Create directory structure and replace template variables
        create_directory_structure(config['matrix_world_dir'], configs.user_name)

        # 2. Create world configuration file
        create_world_config(config['matrix_world_dir'], configs.user_name)

        # 3. Save LLM configurations
        configs_dict = {
            "default_llm": configs.default_llm,
            "default_slm": configs.default_slm
        }
        save_llm_configs(configs_dict, config['llm_config_path'])

        return {
            "success": True,
            "message": "Cold start configuration completed successfully",
            "user_name": configs.user_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def get_sessions(page: int = 1, per_page: int = 20):
    """
    Get user's email conversations (sessions)

    Args:
        page: Page number (starts from 1, default: 1)
        per_page: Items per page (default: 20, max: 100)
    """
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    # Limit per_page to avoid excessive queries
    per_page = min(per_page, 100)

    user_agent_name = matrix_runtime.get_user_agent_name()

    # Query conversations from database
    result = matrix_runtime.post_office.email_db.get_user_conversations(
        user_agent_name=user_agent_name,
        page=page,
        per_page=per_page
    )

    # Transform to response format
    conversations = []
    for conv in result['conversations']:
        conversations.append({
            "session_id": conv['session_id'],
            "subject": conv['subject'],
            "last_email_time": conv['last_email_time'],
            "participants": conv['participants']
        })

    return {
        "success": True,
        "conversations": conversations,
        "total": result['total'],
        "page": result['page'],
        "per_page": result['per_page'],
        "total_pages": result['total_pages']
    }

@app.post("/api/sessions/{session_id}/emails")
async def send_email(
    session_id: str,
    task_id: Optional[str] = Form(None),
    recipient: str = Form(...),
    subject: Optional[str] = Form(''),
    body: str = Form(...),
    in_reply_to: Optional[str] = Form(None),
    attachments: List[UploadFile] = File(default=[])
):
    """Send an email with attachments (new conversation or reply)"""
    print(f"📧 Received email request: recipient={recipient}, subject={subject}, body_length={len(body)}, attachments={len(attachments)}")
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    user_agent_name = matrix_runtime.get_user_agent_name()
    user_agent = matrix_runtime.agents.get(user_agent_name)
    if not user_agent:
        raise HTTPException(status_code=404, detail=f"User agent '{user_agent_name}' not found")

    # Use session_id from URL if task_id is None
    # session_id from URL is the task_id for existing conversations
    effective_task_id = task_id
    if effective_task_id is None:
        if session_id == 'new':
            # Generate new UUID for new conversations
            import uuid
            effective_task_id = str(uuid.uuid4())
            print(f"📧 New conversation: generated task_id={effective_task_id}")
        else:
            # Use existing session_id for replies (session_id from URL is task_id)
            effective_task_id = session_id
            print(f"📧 Reply: using task_id={effective_task_id}, in_reply_to={in_reply_to}")
    else:
        print(f"📧 Using provided task_id={effective_task_id}")

    # Validate task_id
    if not effective_task_id or effective_task_id in ('null', 'undefined', 'None'):
        raise HTTPException(status_code=400, detail=f"Invalid task_id: {effective_task_id}")

    # 处理附件
    attachment_metadata = []
    if attachments:
        # 获取附件保存目录（通过 runtime.paths）
        attachments_dir = user_agent.runtime.paths.get_agent_attachments_dir(
            user_agent.name, 
            effective_task_id
        )
        
        attachments_dir.mkdir(parents=True, exist_ok=True)
        
        for attachment in attachments:
            try:
                # 读取文件内容
                content = await attachment.read()
                filename = attachment.filename or "unnamed"
                file_path = attachments_dir / filename
                
                # 保存文件（同名文件直接覆盖）
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                # 添加到附件 metadata
                attachment_metadata.append({
                    'filename': filename,
                    'size': len(content),
                    'container_path': f'/work_files/attachments/{filename}'
                })
                print(f"✅ Attachment saved: {filename} ({len(content)} bytes) -> {file_path}")
            except Exception as e:
                print(f"❌ Failed to save attachment {attachment.filename}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to save attachment: {str(e)}")

    # Determine session_id
    # For new conversations, we need to create/get a session first
    # For replies, we use the existing session_id from the email being replied to
    effective_session_id = session_id

    if session_id == 'new':
        # New conversation: need to create a session
        # We'll use the task_id as the session_id for User's outgoing emails
        # This will be stored in the reply_mapping
        effective_session_id = effective_task_id
        print(f"📧 New conversation: using session_id={effective_session_id}")
    else:
        # Reply: use the existing session_id
        effective_session_id = session_id
        print(f"📧 Reply: using session_id={effective_session_id}")

    # Call User agent's speak method
    # 将附件 metadata 传递给 speak 方法
    await user_agent.speak(
        session_id=effective_session_id,
        task_id=effective_task_id,
        to=recipient,
        subject=subject,
        content=body,
        reply_to_id=in_reply_to,
        attachments=attachment_metadata if attachment_metadata else None
    )

    return {
        "success": True,
        "task_id": effective_task_id,
        "message": "Email sent successfully",
        "attachments_count": len(attachment_metadata)
    }


@app.get("/api/sessions/{session_id}/emails")
async def get_session_emails(session_id: str):
    """Get all emails for a specific session"""
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        # Get emails from PostOffice
        emails = matrix_runtime.post_office.get_session_emails_for_user(session_id)

        # Convert to dict format for JSON response
        emails_data = []
        for email in emails:
            emails_data.append({
                "id": email.id,
                "timestamp": email.timestamp.isoformat() if hasattr(email.timestamp, 'isoformat') else str(email.timestamp),
                "sender": email.sender,
                "recipient": email.recipient,
                "subject": email.subject,
                "body": email.body,
                "in_reply_to": email.in_reply_to,
                "task_id": email.task_id,
                            "receiver_session_id": email.receiver_session_id,
                "is_from_user": getattr(email, 'is_from_user', False),
                "attachments": email.attachments
            })

        return {
            "success": True,
            "emails": emails_data,
            "total_count": len(emails_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/emails/{email_id}/attachments/{filename}")
async def download_email_attachment(session_id: str, email_id: str, filename: str):
    """Download an attachment from an email"""
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        # Get the email to find the recipient (who has the attachment)
        emails = matrix_runtime.post_office.get_session_emails_for_user(session_id)
        target_email = None
        for email in emails:
            if email.id == email_id:
                target_email = email
                break

        if not target_email:
            raise HTTPException(status_code=404, detail="Email not found")

        # The recipient is the one who has the attachment
        recipient_name = target_email.recipient
        task_id = target_email.task_id

        # Get recipient agent
        recipient_agent = matrix_runtime.agents.get(recipient_name)
        if not recipient_agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {recipient_name}")

        # Build the attachment path (via runtime.paths)
        attachment_path = recipient_agent.runtime.paths.get_agent_attachments_dir(
            recipient_name, 
            task_id
        ) / filename

        # Check if file exists
        if not attachment_path.exists():
            raise HTTPException(status_code=404, detail=f"Attachment not found: {filename}")

        # Determine media type and disposition based on file extension
        file_ext = Path(filename).suffix.lower()
        
        # Files that can be previewed in browser
        previewable_extensions = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.pdf': 'application/pdf',
            '.svg': 'image/svg+xml',
        }
        
        # Images that can be previewed
        image_extensions = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
        }
        
        # Merge all previewable types
        all_previewable = {**previewable_extensions, **image_extensions}
        
        if file_ext in all_previewable:
            # File can be previewed in browser
            media_type = all_previewable[file_ext]
            # Use inline to display in browser instead of downloading
            with open(attachment_path, 'rb') as f:
                file_content = f.read()
            # Encode filename for HTTP header (support Chinese and other non-ASCII characters)
            encoded_filename = quote(filename, safe='')
            
            return Response(
                content=file_content,
                media_type=media_type,
                headers={
                    'Content-Disposition': f"inline; filename*=UTF-8''{encoded_filename}"
                }
            )
        else:
            # Download the file
            return FileResponse(
                path=str(attachment_path),
                filename=filename,
                media_type='application/octet-stream'
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    """Get all agents with their details"""
    global matrix_runtime
    
    if not matrix_runtime:
        return {"agents": []}
    
    try:
        agents_list = []
        for name, agent in matrix_runtime.agents.items():
            # Skip User agent (don't show user as an agent)
            if name == matrix_runtime.get_user_agent_name():
                continue
            
            agents_list.append({
                "name": name,
                "description": getattr(agent, 'description', 'No description'),
                "backend_model": getattr(agent, 'backend_model', 'default_llm')
            })
        
        return {"agents": agents_list}
    except Exception as e:
        print(f"Error getting agents: {e}")
        return {"agents": [], "error": str(e)}


@app.get("/api/agents/{agent_name}")
async def get_agent(agent_name: str):
    """Get a specific agent's details"""
    global matrix_runtime
    
    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")
    
    if agent_name not in matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    
    agent = matrix_runtime.agents[agent_name]
    
    return {
        "name": agent_name,
        "description": getattr(agent, 'description', 'No description'),
        "backend_model": getattr(agent, 'backend_model', 'default_llm'),

    }


@app.get("/api/agents/{agent_name}/status/history")
async def get_agent_status_history(agent_name: str):
    """获取 Agent 状态历史（最近 3 条）"""
    global matrix_runtime
    
    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")
    
    if agent_name not in matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    
    agent = matrix_runtime.agents[agent_name]
    
    # 检查是否有状态管理方法
    if hasattr(agent, 'get_status_history'):
        return agent.get_status_history()
    else:
        return []


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


# === Skills APIs ===

def scan_available_skills() -> list:
    """扫描所有可用的 skills（从文件系统）"""
    import importlib
    from pathlib import Path
    
    skills_info = []
    
    # 1. 扫描内置 skills 目录
    try:
        skills_module = importlib.import_module('agentmatrix.skills')
        skills_dir = Path(skills_module.__file__).parent
        
        # 扫描目录结构: agentmatrix/skills/{name}/skill.py
        for item in skills_dir.iterdir():
            if item.is_dir() and not item.name.startswith('__') and not item.name.startswith('.'):
                skill_file = item / "skill.py"
                if skill_file.exists():
                    skill_name = item.name
                    # 尝试读取文件获取描述
                    description = get_skill_description(skill_file, skill_name)
                    skills_info.append({
                        "name": skill_name,
                        "description": description,
                        "source": "built-in"
                    })
            # 扫描扁平文件: agentmatrix/skills/{name}_skill.py
            elif item.is_file() and item.name.endswith('_skill.py') and not item.name.startswith('__'):
                skill_name = item.name[:-9]  # 移除 _skill.py
                description = get_skill_description(item, skill_name)
                skills_info.append({
                    "name": skill_name,
                    "description": description,
                    "source": "built-in"
                })
    except Exception as e:
        print(f"Error scanning built-in skills: {e}")
    
    # 2. 扫描 workspace skills 目录
    try:
        if matrix_world_dir:
            workspace_skills_dir = Path(matrix_world_dir) / "skills"
            if workspace_skills_dir.exists():
                for item in workspace_skills_dir.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        skill_file = item / "skill.py"
                        if skill_file.exists():
                            skill_name = item.name
                            description = get_skill_description(skill_file, skill_name)
                            skills_info.append({
                                "name": skill_name,
                                "description": description,
                                "source": "workspace"
                            })
    except Exception as e:
        print(f"Error scanning workspace skills: {e}")
    
    # 去重（按名称）
    seen = set()
    unique_skills = []
    for skill in skills_info:
        if skill["name"] not in seen:
            seen.add(skill["name"])
            unique_skills.append(skill)
    
    # 按名称排序
    unique_skills.sort(key=lambda x: x["name"])
    
    return unique_skills


def get_skill_description(skill_file: Path, skill_name: str) -> str:
    """从 skill 文件中提取描述"""
    try:
        content = skill_file.read_text(encoding='utf-8')
        # 查找文件开头的 docstring
        if '"""' in content:
            start = content.find('"""') + 3
            end = content.find('"""', start)
            if end > start:
                docstring = content[start:end].strip()
                # 取第一行非空行作为描述
                for line in docstring.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('=='):
                        return line[:100]  # 限制长度
    except Exception:
        pass
    return f"{skill_name} skill"


@app.get("/api/skills")
async def get_available_skills():
    """Get all available skills in the system"""
    try:
        skills = scan_available_skills()
        return {"skills": skills}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Agent Profile Management APIs ===

def get_agent_yml_path(agent_name: str) -> Path:
    """Get the YAML file path for an agent"""
    return agents_dir / f"{agent_name}.yml"


def load_agent_profile(agent_name: str) -> dict:
    """Load agent profile from YAML file"""
    import yaml
    yml_path = get_agent_yml_path(agent_name)
    if not yml_path.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    
    with open(yml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_agent_profile(agent_name: str, profile: dict):
    """Save agent profile to YAML file"""
    import yaml
    yml_path = get_agent_yml_path(agent_name)
    with open(yml_path, 'w', encoding='utf-8') as f:
        yaml.dump(profile, f, default_flow_style=False, allow_unicode=True)


def agent_profile_to_response(profile: dict) -> dict:
    """Convert agent profile to API response format - 支持灵活的配置结构"""
    # Handle backward compatibility: mixins -> skills (仅用于显示)
    skills = profile.get("skills", [])
    if not skills and "mixins" in profile:
        # Convert mixins to skills format for display
        mixins = profile["mixins"]
        if isinstance(mixins, list):
            skills = [m.split(".")[-1].replace("SkillMixin", "").lower() for m in mixins if isinstance(m, str)]
    
    # 构建响应，包含所有标准字段
    response = {
        "name": profile.get("name", ""),
        "description": profile.get("description", ""),
        "module": profile.get("module", ""),
        "class_name": profile.get("class_name", ""),
        "backend_model": profile.get("backend_model", "default_llm"),
        "skills": skills,
        "persona": profile.get("persona", {}),
        # 新增配置项
        "cerebellum": profile.get("cerebellum"),
        "vision_brain": profile.get("vision_brain"),
        "prompts": profile.get("prompts", {}),
        "logging": profile.get("logging"),
        # 保留原始 profile 的引用，方便前端获取完整信息
        "_raw_profile": profile
    }
    
    return response


@app.get("/api/agent-profiles")
async def get_agent_profiles():
    """Get all agent profiles from YAML files (including full details)"""
    try:
        import yaml
        profiles = []
        
        if not agents_dir.exists():
            return {"agents": []}
        
        for yml_file in agents_dir.glob("*.yml"):
            # Skip User.yml - it's special
            if yml_file.stem == "User":
                continue
                
            try:
                with open(yml_file, 'r', encoding='utf-8') as f:
                    profile = yaml.safe_load(f)
                    if profile and isinstance(profile, dict):
                        profiles.append(agent_profile_to_response(profile))
            except Exception as e:
                print(f"Error loading agent profile {yml_file}: {e}")
                continue
        
        return {"agents": profiles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent-profiles/{agent_name}")
async def get_agent_profile(agent_name: str):
    """Get a specific agent's full profile from YAML"""
    try:
        global matrix_runtime
        if not matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        profile = matrix_runtime.config_service.get_agent_profile(agent_name)
        return agent_profile_to_response(profile)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent-profiles")
async def create_agent_profile(request: AgentConfigRequest):
    """Create a new agent profile - 支持灵活的配置结构"""
    try:
        import yaml
        yml_path = get_agent_yml_path(request.name)
        
        # Check if agent already exists
        if yml_path.exists():
            raise HTTPException(status_code=409, detail=f"Agent '{request.name}' already exists")
        
        # Validate name (alphanumeric, underscore, hyphen)
        if not re.match(r'^[a-zA-Z0-9_-]+$', request.name):
            raise HTTPException(status_code=400, detail="Agent name can only contain letters, numbers, underscores, and hyphens")
        
        # Build profile - 只包含非空值，保持配置文件简洁
        profile = {
            "name": request.name,
            "description": request.description,
            "class_name": request.class_name,  # 新格式：完整类路径
        }
        
        # 可选字段 - 只在有值时添加
        if request.backend_model and request.backend_model != "default_llm":
            profile["backend_model"] = request.backend_model
        if request.skills:
            profile["skills"] = request.skills
        if request.persona:
            profile["persona"] = request.persona
        if request.cerebellum:
            profile["cerebellum"] = request.cerebellum
        if request.vision_brain:
            profile["vision_brain"] = request.vision_brain
        if request.prompts:
            profile["prompts"] = request.prompts
        if request.logging:
            profile["logging"] = request.logging
        
        # 处理额外字段（保留灵活性）
        if request.extra_fields:
            for key, value in request.extra_fields.items():
                if key not in profile:  # 不覆盖已处理的字段
                    profile[key] = value
        
        save_agent_profile(request.name, profile)

        # 🆕 动态加载并注册新Agent到运行时
        global matrix_runtime
        runtime_loaded = False
        if matrix_runtime:
            try:
                await matrix_runtime.load_and_register_agent(request.name)
                runtime_loaded = True
                print(f"✅ Agent '{request.name}' 已动态加载并注册到系统")
            except Exception as e:
                print(f"⚠️  Agent配置已保存，但动态加载失败: {e}")
                # 注意：即使加载失败，配置文件也已保存，用户可以重启系统来加载
        else:
            print("⚠️  Runtime未初始化，Agent配置已保存，需要重启系统才能加载")

        return {
            "success": True,
            "message": f"Agent '{request.name}' created successfully",
            "agent": agent_profile_to_response(profile),
            "runtime_loaded": runtime_loaded  # 返回是否已加载到运行时
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/agent-profiles/{agent_name}")
async def update_agent_profile(agent_name: str, request: AgentUpdateRequest):
    """Update an existing agent profile - 支持灵活的配置结构"""
    try:
        profile = load_agent_profile(agent_name)
        
        # 更新基本字段
        if request.description is not None:
            profile["description"] = request.description
        if request.backend_model is not None:
            profile["backend_model"] = request.backend_model
        if request.skills is not None:
            if request.skills:
                profile["skills"] = request.skills
            else:
                profile.pop("skills", None)  # 删除空数组
        if request.persona is not None:
            if request.persona:
                profile["persona"] = request.persona
            else:
                profile.pop("persona", None)
        if request.class_name is not None:
            profile["class_name"] = request.class_name
        
        # 更新新字段
        if request.cerebellum is not None:
            if request.cerebellum:
                profile["cerebellum"] = request.cerebellum
            else:
                profile.pop("cerebellum", None)
        if request.vision_brain is not None:
            if request.vision_brain:
                profile["vision_brain"] = request.vision_brain
            else:
                profile.pop("vision_brain", None)
        if request.prompts is not None:
            if request.prompts:
                profile["prompts"] = request.prompts
            else:
                profile.pop("prompts", None)
        if request.logging is not None:
            if request.logging:
                profile["logging"] = request.logging
            else:
                profile.pop("logging", None)
        
        # 处理额外字段（保留灵活性）
        if request.extra_fields:
            for key, value in request.extra_fields.items():
                if value is not None:
                    profile[key] = value
                else:
                    profile.pop(key, None)  # 允许通过 None 删除字段
        
        save_agent_profile(agent_name, profile)
        
        return {
            "success": True,
            "message": f"Agent '{agent_name}' updated successfully",
            "agent": agent_profile_to_response(profile)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/agent-profiles/{agent_name}")
async def delete_agent_profile(agent_name: str):
    """Delete an agent profile"""
    try:
        # Prevent deleting User agent
        if agent_name == "User":
            raise HTTPException(status_code=403, detail="Cannot delete User agent")
        
        yml_path = get_agent_yml_path(agent_name)
        
        if not yml_path.exists():
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        yml_path.unlink()
        
        return {
            "success": True,
            "message": f"Agent '{agent_name}' deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent-profiles/{agent_name}/reload")
async def reload_agent_profile(agent_name: str):
    """Reload an agent profile into runtime (requires runtime restart to take full effect)"""
    global matrix_runtime
    
    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")
    
    try:
        profile = load_agent_profile(agent_name)
        
        # Note: Full reload requires restarting the runtime
        # For now, we just verify the profile is valid
        return {
            "success": True,
            "message": f"Agent profile '{agent_name}' is valid. Restart server to apply changes.",
            "agent": agent_profile_to_response(profile)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === LLM Configuration Management APIs ===




@app.get("/api/llm-configs")
async def get_llm_configs():
    """Get all LLM configurations"""
    try:
        configs = load_llm_configs()
        
        # Format response with metadata
        result = []
        for name, config in configs.items():
            is_required = name in REQUIRED_LLM_CONFIGS
            result.append({
                "name": name,
                "url": config.get("url", ""),
                "api_key": config.get("API_KEY", ""),
                "model_name": config.get("model_name", ""),
                "is_required": is_required,
                "description": get_llm_config_description(name)
            })
        
        # Sort: required configs first, then by name
        result.sort(key=lambda x: (not x["is_required"], x["name"]))
        
        return {"configs": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_llm_config_description(name: str) -> str:
    """Get description for a LLM config based on its name"""
    descriptions = {
        "default_llm": "Primary large language model for main agent reasoning",
        "default_slm": "Smaller/faster model for simple tasks and cerebellum",
        "browser-use-llm": "Model for browser automation tasks",
        "default_vision": "Vision model for image understanding tasks"
    }
    return descriptions.get(name, "Custom LLM configuration")


@app.get("/api/llm-configs/{config_name}")
async def get_llm_config(config_name: str):
    """Get a specific LLM configuration"""
    try:
        global matrix_runtime
        if not matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        configs = matrix_runtime.config_service.list_llm_models()
        
        if config_name not in configs:
            raise HTTPException(status_code=404, detail=f"LLM config '{config_name}' not found")
        
        config = configs[config_name]
        return {
            "name": config_name,
            "url": config.get("url", ""),
            "api_key": config.get("API_KEY", ""),
            "model_name": config.get("model_name", ""),
            "is_required": config_name in REQUIRED_LLM_CONFIGS,
            "description": get_llm_config_description(config_name)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llm-configs")
async def create_llm_config(request: LLMConfigCreateRequest):
    """Create a new LLM configuration"""
    try:
        global matrix_runtime
        if not matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        # Validate name (alphanumeric, underscore, hyphen)
        if not re.match(r'^[a-zA-Z0-9_-]+$', request.name):
            raise HTTPException(status_code=400, detail="Config name can only contain letters, numbers, underscores, and hyphens")
        
        # Create new config using ConfigService
        config = {
            "url": request.url,
            "API_KEY": request.api_key,
            "model_name": request.model_name
        }
        
        matrix_runtime.config_service.add_llm_model(request.name, config)
        
        return {
            "success": True,
            "message": f"LLM config '{request.name}' created successfully",
            "config": {
                "name": request.name,
                "url": request.url,
                "api_key": request.api_key,
                "model_name": request.model_name,
                "is_required": False,
                "description": get_llm_config_description(request.name)
            }
        }
    except HTTPException:
        raise
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/llm-configs/{config_name}")
async def update_llm_config(config_name: str, request: LLMConfigUpdateRequest):
    """Update an existing LLM configuration"""
    try:
        configs = load_llm_configs()
        
        if config_name not in configs:
            raise HTTPException(status_code=404, detail=f"LLM config '{config_name}' not found")
        
        # Update config
        configs[config_name] = {
            "url": request.url,
            "API_KEY": request.api_key,
            "model_name": request.model_name
        }
        
        save_llm_configs_to_file(configs)
        
        return {
            "success": True,
            "message": f"LLM config '{config_name}' updated successfully",
            "config": {
                "name": config_name,
                "url": request.url,
                "api_key": request.api_key,
                "model_name": request.model_name,
                "is_required": config_name in REQUIRED_LLM_CONFIGS,
                "description": get_llm_config_description(config_name)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/llm-configs/{config_name}")
async def delete_llm_config(config_name: str):
    """Delete an LLM configuration"""
    try:
        # Check if this is a required config
        if config_name in REQUIRED_LLM_CONFIGS:
            raise HTTPException(status_code=403, detail=f"Cannot delete required config '{config_name}'")
        
        configs = load_llm_configs()
        
        if config_name not in configs:
            raise HTTPException(status_code=404, detail=f"LLM config '{config_name}' not found")
        
        # Remove config
        del configs[config_name]
        
        save_llm_configs_to_file(configs)
        
        return {
            "success": True,
            "message": f"LLM config '{config_name}' deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llm-configs/{config_name}/reset")
async def reset_llm_config(config_name: str):
    """Reset a required LLM config to default values"""
    try:
        if config_name not in REQUIRED_LLM_CONFIGS:
            raise HTTPException(status_code=400, detail=f"Can only reset required configs")
        
        configs = load_llm_configs()
        
        # Set default values based on config name
        defaults = {
            "default_llm": {
                "url": "https://api.openai.com/v1/chat/completions",
                "API_KEY": "your-api-key",
                "model_name": "gpt-4"
            },
            "default_slm": {
                "url": "https://api.openai.com/v1/chat/completions",
                "API_KEY": "your-api-key",
                "model_name": "gpt-3.5-turbo"
            },
            "browser-use-llm": {
                "url": "https://api.openai.com/v1/chat/completions",
                "API_KEY": "your-api-key",
                "model_name": "gpt-4"
            }
        }
        
        configs[config_name] = defaults.get(config_name, defaults["default_llm"])
        save_llm_configs_to_file(configs)
        
        return {
            "success": True,
            "message": f"LLM config '{config_name}' reset to defaults",
            "config": {
                "name": config_name,
                **configs[config_name],
                "is_required": True,
                "description": get_llm_config_description(config_name)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Agent Control APIs (暂停/恢复/状态查询) ===

@app.post("/api/agents/{agent_name}/pause")
async def pause_agent(agent_name: str):
    """暂停 Agent 执行"""
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    if agent_name not in matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        agent = matrix_runtime.agents[agent_name]
        await agent.pause()

        return {
            "success": True,
            "message": f"Agent '{agent_name}' paused successfully",
            "agent_name": agent_name,
            "paused": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_name}/resume")
async def resume_agent(agent_name: str):
    """恢复 Agent 执行"""
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    if agent_name not in matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        agent = matrix_runtime.agents[agent_name]
        await agent.resume()

        return {
            "success": True,
            "message": f"Agent '{agent_name}' resumed successfully",
            "agent_name": agent_name,
            "paused": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_name}/status")
async def get_agent_status(agent_name: str):
    """获取 Agent 当前执行状态"""
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    if agent_name not in matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        agent = matrix_runtime.agents[agent_name]
        
        # 使用新的状态管理方法
        if hasattr(agent, 'get_current_status'):
            return {
                "success": True,
                "agent_name": agent_name,
                **agent.get_current_status()  # 展开返回 message 和 timestamp
            }
        else:
            # 向后兼容：使用旧方法
            return {
                "success": True,
                "agent_name": agent_name,
                "message": str(getattr(agent, 'status', 'unknown')),
                "timestamp": None
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_name}/pending_user_input")
async def get_pending_user_input(agent_name: str):
    """获取 Agent 等待用户输入的问题"""
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    if agent_name not in matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    try:
        agent = matrix_runtime.agents[agent_name]

        # 检查是否在等待用户输入
        if not agent._user_input_future or agent._user_input_future.done():
            return {
                "success": True,
                "agent_name": agent_name,
                "waiting": False
            }

        # 返回等待中的问题
        return {
            "success": True,
            "agent_name": agent_name,
            "waiting": True,
            "question": agent._pending_user_question
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_name}/submit_user_input")
async def submit_user_input(agent_name: str, request: Request):
    """提交用户输入，唤醒正在等待的 Agent"""
    global matrix_runtime

    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not available")

    if agent_name not in matrix_runtime.agents:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    # 获取用户输入
    request_data = await request.json()
    answer = request_data.get("answer")
    if not answer:
        raise HTTPException(status_code=400, detail="Missing 'answer' field")

    try:
        agent = matrix_runtime.agents[agent_name]
        await agent.submit_user_input(answer)

        return {
            "success": True,
            "message": f"User input submitted to agent '{agent_name}'",
            "agent_name": agent_name
        }
    except RuntimeError as e:
        # Agent 没有在等待用户输入
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Main Entry Point ===

def main():
    """Main entry point"""
    import uvicorn

    print("""
    ╔═══════════════════════════════════════╗
    ║       AgentMatrix Server v0.1.5       ║
    ╚═══════════════════════════════════════╝
    """)

    # Args already parsed at module level
    # Access via module-level 'args' variable
    try:
        uvicorn.run(
            "server:app",
            host=args.host,
            port=args.port,
            reload=args.reload
        )
    except KeyboardInterrupt:
        # Ctrl-C 正常退出，已在 lifespan shutdown 中打印告别信息
        pass
    except asyncio.CancelledError:
        # 异步任务取消（正常 shutdown 的一部分）
        pass




# === Email Proxy Configuration Endpoints ===

@app.get("/api/email-proxy/config")
async def get_email_proxy_config():
    """Get Email Proxy configuration"""
    try:
        global matrix_runtime
        if not matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        config = matrix_runtime.config_service.get_email_proxy_config()
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/email-proxy/config")
async def update_email_proxy_config(request: dict):
    """Update Email Proxy configuration"""
    try:
        global matrix_runtime
        if not matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        path = matrix_runtime.config_service.update_email_proxy_config(request)
        return {"success": True, "message": "Email proxy config updated", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email-proxy/enable")
async def enable_email_proxy():
    """Enable Email Proxy"""
    try:
        global matrix_runtime
        if not matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        matrix_runtime.config_service.enable_email_proxy()
        return {"success": True, "message": "Email proxy enabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email-proxy/disable")
async def disable_email_proxy():
    """Disable Email Proxy"""
    try:
        global matrix_runtime
        if not matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        matrix_runtime.config_service.disable_email_proxy()
        return {"success": True, "message": "Email proxy disabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email-proxy/user-mailbox")
async def add_user_mailbox(request: dict):
    """Add user mailbox"""
    try:
        global matrix_runtime
        if not matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        matrix_runtime.config_service.add_user_mailbox(email)
        return {"success": True, "message": f"Added user mailbox: {email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/email-proxy/user-mailbox")
async def remove_user_mailbox(request: dict):
    """Remove user mailbox"""
    try:
        global matrix_runtime
        if not matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        matrix_runtime.config_service.remove_user_mailbox(email)
        return {"success": True, "message": f"Removed user mailbox: {email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
if __name__ == "__main__":
    main()
