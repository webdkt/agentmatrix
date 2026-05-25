"""
Configuration routes: config status, init, first-run, LLM presets.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..state import server_state
from ..lifecycle import init_runtime, load_user_agent_name
from ..models import LLMConfig

router = APIRouter()

LLM_PRESETS = {
    "anthropic": {
        "label": "Anthropic",
        "url": "https://api.anthropic.com/v1/messages",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"],
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "label": "OpenAI",
        "url": "https://api.openai.com/v1/chat/completions",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "api_key_env": "OPENAI_API_KEY",
    },
    "custom": {
        "label": "Custom",
        "url": "",
        "models": [],
        "api_key_env": "",
    },
}


@router.get("/api/config/status")
async def get_config_status():
    """Check if the system is configured and runtime is ready"""
    return {
        "configured": server_state.matrix_runtime is not None,
        "matrix_world_dir": str(server_state.matrix_world_dir),
        "user_agent_name": server_state.matrix_runtime.get_user_agent_name()
        if server_state.matrix_runtime
        else None,
    }


@router.get("/api/config/llm-presets")
async def get_llm_presets():
    """Return available LLM provider presets for the configuration wizard"""
    return {"presets": LLM_PRESETS}


@router.get("/api/config")
async def get_config():
    """Get system configuration including user agent name"""
    response_data = {
        "configured": server_state.matrix_runtime is not None,
        "matrix_world_dir": str(server_state.matrix_world_dir),
        "agents_dir": str(server_state.agents_dir),
        "workspace_dir": str(server_state.workspace_dir),
    }

    if server_state.matrix_runtime:
        response_data["user_agent_name"] = server_state.matrix_runtime.get_user_agent_name()
    else:
        response_data["user_agent_name"] = load_user_agent_name(
            server_state.matrix_world_dir
        )

    return response_data


@router.post("/api/config/init")
async def init_runtime_api(request: dict):
    """
    Initialize runtime from existing directory structure.
    Files should already be created by Tauri commands.
    """
    try:
        mw_dir = Path(request["matrix_world_path"]).resolve()

        if not mw_dir.exists():
            return {
                "success": False,
                "message": f"Directory not found: {mw_dir}",
            }

        server_state.matrix_world_dir = mw_dir
        server_state.llm_config_path = (
            mw_dir / ".matrix" / "configs" / "llm_config.json"
        )
        server_state.system_config_path = (
            mw_dir / ".matrix" / "configs" / "system_config.yml"
        )
        server_state.email_proxy_config_path = (
            mw_dir / ".matrix" / "configs" / "email_proxy_config.yml"
        )
        server_state.agents_dir = mw_dir / ".matrix" / "configs" / "agents"

        runtime = await init_runtime(mw_dir)

        return {
            "success": True,
            "message": "Runtime initialized",
            "user_name": runtime.get_user_agent_name(),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        server_state.matrix_runtime = None
        return {"success": False, "message": str(e)}


@router.post("/api/config/first-run")
async def first_run_init(request: dict):
    """
    One-time initialization action, called only on first cold start.
    """
    if not server_state.matrix_runtime:
        return {"success": False, "message": "Runtime not initialized"}

    try:
        user_name = request.get("user_name", "User")

        print(f"🔧 First-run initialization for user: {user_name}")

        if "SystemAdmin" not in server_state.matrix_runtime.agents:
            available = list(server_state.matrix_runtime.agents.keys())
            return {
                "success": False,
                "message": f"SystemAdmin agent not found. Available: {available}",
            }

        from agentmatrix.core.message import Email

        task_id = str(uuid.uuid4())

        email = Email(
            id=str(uuid.uuid4()),
            sender="no-reply-system",
            recipient="SystemAdmin",
            subject="系统初始化完成",
            body=(
                f"用户 {user_name} 刚刚完成了系统初始化设置，系统第一次运行了。\n"
                f"你作为系统管理员，请写一封 welcome letter 给用户，介绍自己，"
                f"并简要介绍系统情况，帮助用户尽快熟悉系统使用。"
            ),
            task_id=task_id,
            sender_session_id=str(uuid.uuid4()),
            recipient_session_id=None,
        )

        await server_state.matrix_runtime.post_office.dispatch(email)
        print(f"✅ First-run email dispatched to SystemAdmin (task_id={task_id})")

        return {"success": True, "message": "First-run initialization complete"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}
