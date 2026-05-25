"""
LLM configuration management routes: CRUD and reset.
"""

import re

from fastapi import APIRouter, HTTPException

from agentmatrix.desktop.services.config_service import ConfigService
from ..state import server_state
from ..models import LLMConfigUpdateRequest, LLMConfigCreateRequest
from ..utils import (
    REQUIRED_LLM_CONFIGS,
    load_llm_configs,
    save_llm_configs_to_file,
    get_llm_config_description,
)

router = APIRouter(prefix="/api/llm-configs")


@router.get("/")
async def get_llm_configs():
    """Get all LLM configurations"""
    try:
        configs = load_llm_configs()

        result = []
        for name, config in configs.items():
            is_required = name in REQUIRED_LLM_CONFIGS
            result.append(
                {
                    "name": name,
                    "url": config.get("url", ""),
                    "api_key": config.get("API_KEY", ""),
                    "model_name": config.get("model_name", ""),
                    "is_required": is_required,
                    "description": get_llm_config_description(name),
                }
            )

        result.sort(key=lambda x: (not x["is_required"], x["name"]))

        return {"configs": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{config_name}")
async def get_llm_config(config_name: str):
    """Get a specific LLM configuration"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        configs = ConfigService(server_state.matrix_runtime.paths).list_llm_models()

        if config_name not in configs:
            raise HTTPException(
                status_code=404, detail=f"LLM config '{config_name}' not found"
            )

        config = configs[config_name]
        return {
            "name": config_name,
            "url": config.get("url", ""),
            "api_key": config.get("API_KEY", ""),
            "model_name": config.get("model_name", ""),
            "is_required": config_name in REQUIRED_LLM_CONFIGS,
            "description": get_llm_config_description(config_name),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_llm_config(request: LLMConfigCreateRequest):
    """Create a new LLM configuration"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        if not re.match(r"^[a-zA-Z0-9_-]+$", request.name):
            raise HTTPException(
                status_code=400,
                detail="Config name can only contain letters, numbers, underscores, and hyphens",
            )

        config = {
            "url": request.url,
            "API_KEY": request.api_key,
            "model_name": request.model_name,
        }

        ConfigService(server_state.matrix_runtime.paths).add_llm_model(request.name, config)

        return {
            "success": True,
            "message": f"LLM config '{request.name}' created successfully",
            "config": {
                "name": request.name,
                "url": request.url,
                "api_key": request.api_key,
                "model_name": request.model_name,
                "is_required": False,
                "description": get_llm_config_description(request.name),
            },
        }
    except HTTPException:
        raise
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{config_name}")
async def update_llm_config(config_name: str, request: LLMConfigUpdateRequest):
    """Update an existing LLM configuration"""
    try:
        configs = load_llm_configs()

        if config_name not in configs:
            raise HTTPException(
                status_code=404, detail=f"LLM config '{config_name}' not found"
            )

        configs[config_name] = {
            "url": request.url,
            "API_KEY": request.api_key,
            "model_name": request.model_name,
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
                "description": get_llm_config_description(config_name),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{config_name}")
async def delete_llm_config(config_name: str):
    """Delete an LLM configuration"""
    try:
        if config_name in REQUIRED_LLM_CONFIGS:
            raise HTTPException(
                status_code=403, detail=f"Cannot delete required config '{config_name}'"
            )

        configs = load_llm_configs()

        if config_name not in configs:
            raise HTTPException(
                status_code=404, detail=f"LLM config '{config_name}' not found"
            )

        del configs[config_name]

        save_llm_configs_to_file(configs)

        return {
            "success": True,
            "message": f"LLM config '{config_name}' deleted successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{config_name}/reset")
async def reset_llm_config(config_name: str):
    """Reset a required LLM config to default values"""
    try:
        if config_name not in REQUIRED_LLM_CONFIGS:
            raise HTTPException(
                status_code=400, detail=f"Can only reset required configs"
            )

        configs = load_llm_configs()

        defaults = {
            "default_llm": {
                "url": "https://api.openai.com/v1/chat/completions",
                "API_KEY": "your-api-key",
                "model_name": "gpt-4",
            },
            "default_slm": {
                "url": "https://api.openai.com/v1/chat/completions",
                "API_KEY": "your-api-key",
                "model_name": "gpt-3.5-turbo",
            },
            "browser-use-llm": {
                "url": "https://api.openai.com/v1/chat/completions",
                "API_KEY": "your-api-key",
                "model_name": "gpt-4",
            },
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
                "description": get_llm_config_description(config_name),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
