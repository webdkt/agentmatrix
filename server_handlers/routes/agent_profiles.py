"""
Agent profile CRUD routes: list, get, create, update, delete, reload.
"""

import re

from fastapi import APIRouter, HTTPException

from ..state import server_state
from ..models import AgentConfigRequest, AgentUpdateRequest
from ..utils import (
    get_agent_yml_path,
    load_agent_profile,
    save_agent_profile,
    agent_profile_to_response,
)

router = APIRouter(prefix="/api/agent-profiles")


@router.get("/")
async def get_agent_profiles():
    """Get all agent profiles from runtime (in-memory, no file I/O)"""
    if not server_state.matrix_runtime:
        return {"agents": []}

    try:
        profiles = []
        user_agent_name = server_state.matrix_runtime.get_user_agent_name()

        for name, agent in server_state.matrix_runtime.agents.items():
            if name == user_agent_name:
                continue

            if hasattr(agent, "profile") and agent.profile:
                profiles.append(agent_profile_to_response(agent.profile))

        return {"agents": profiles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_name}")
async def get_agent_profile_by_name(agent_name: str):
    """Get a specific agent's full profile from YAML"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        profile = server_state.matrix_runtime.agent_service.read_profile(agent_name)
        return agent_profile_to_response(profile)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_agent_profile(request: AgentConfigRequest):
    """Create a new agent profile"""
    try:
        import yaml

        yml_path = get_agent_yml_path(request.name)

        if yml_path.exists():
            raise HTTPException(
                status_code=409, detail=f"Agent '{request.name}' already exists"
            )

        if not re.match(r"^[a-zA-Z0-9_-]+$", request.name):
            raise HTTPException(
                status_code=400,
                detail="Agent name can only contain letters, numbers, underscores, and hyphens",
            )

        profile = {
            "name": request.name,
            "description": request.description,
            "class_name": request.class_name,
        }

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

        if request.extra_fields:
            for key, value in request.extra_fields.items():
                if key not in profile:
                    profile[key] = value

        save_agent_profile(request.name, profile)

        runtime_loaded = False
        if server_state.matrix_runtime:
            try:
                await server_state.matrix_runtime.load_and_register_agent(request.name)
                runtime_loaded = True
                print(f"✅ Agent '{request.name}' 已动态加载并注册到系统")
            except Exception as e:
                print(f"⚠️  Agent配置已保存，但动态加载失败: {e}")
        else:
            print("⚠️  Runtime未初始化，Agent配置已保存，需要重启系统才能加载")

        return {
            "success": True,
            "message": f"Agent '{request.name}' created successfully",
            "agent": agent_profile_to_response(profile),
            "runtime_loaded": runtime_loaded,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_name}")
async def update_agent_profile(agent_name: str, request: AgentUpdateRequest):
    """Update an existing agent profile"""
    try:
        profile = load_agent_profile(agent_name)

        if request.description is not None:
            profile["description"] = request.description
        if request.backend_model is not None:
            profile["backend_model"] = request.backend_model
        if request.skills is not None:
            if request.skills:
                profile["skills"] = request.skills
            else:
                profile.pop("skills", None)
        if request.persona is not None:
            if request.persona:
                profile["persona"] = request.persona
            else:
                profile.pop("persona", None)
        if request.class_name is not None:
            profile["class_name"] = request.class_name

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

        if request.extra_fields:
            for key, value in request.extra_fields.items():
                if value is not None:
                    profile[key] = value
                else:
                    profile.pop(key, None)

        save_agent_profile(agent_name, profile)

        return {
            "success": True,
            "message": f"Agent '{agent_name}' updated successfully",
            "agent": agent_profile_to_response(profile),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_name}")
async def delete_agent_profile(agent_name: str):
    """Delete an agent profile"""
    try:
        if agent_name == "User":
            raise HTTPException(status_code=403, detail="Cannot delete User agent")

        yml_path = get_agent_yml_path(agent_name)

        if not yml_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Agent '{agent_name}' not found"
            )

        yml_path.unlink()

        return {
            "success": True,
            "message": f"Agent '{agent_name}' deleted successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_name}/reload")
async def reload_agent_profile(agent_name: str):
    """Reload an agent profile into runtime"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        profile = load_agent_profile(agent_name)

        return {
            "success": True,
            "message": f"Agent profile '{agent_name}' is valid. Restart server to apply changes.",
            "agent": agent_profile_to_response(profile),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
