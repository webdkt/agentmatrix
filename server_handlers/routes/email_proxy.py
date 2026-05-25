"""
Email proxy configuration routes.
"""

from fastapi import APIRouter, HTTPException

from agentmatrix.desktop.services.config_service import ConfigService
from ..state import server_state

router = APIRouter(prefix="/api/email-proxy")


@router.get("/config")
async def get_email_proxy_config():
    """Get Email Proxy configuration"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        import yaml

        result = ConfigService(server_state.matrix_runtime.paths).read_config("email_proxy")

        if not result.success:
            return {}

        config = yaml.safe_load(result.content) or {}
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_email_proxy_config(request: dict):
    """Update Email Proxy configuration"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        import yaml

        yaml_content = yaml.dump(
            request, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
        result = await ConfigService(server_state.matrix_runtime.paths).write_config(
            "email_proxy", yaml_content, skip_verification=False
        )

        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)

        return {"success": True, "message": "Email proxy config updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable")
async def enable_email_proxy():
    """Enable Email Proxy"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        import yaml

        result = ConfigService(server_state.matrix_runtime.paths).read_config("email_proxy")

        if result.success:
            config = yaml.safe_load(result.content) or {}
        else:
            config = {}

        config["enabled"] = True
        yaml_content = yaml.dump(
            config, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
        await ConfigService(server_state.matrix_runtime.paths).write_config(
            "email_proxy", yaml_content, skip_verification=True
        )

        return {"success": True, "message": "Email proxy enabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_email_proxy():
    """Disable Email Proxy"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        import yaml

        result = ConfigService(server_state.matrix_runtime.paths).read_config("email_proxy")

        if result.success:
            config = yaml.safe_load(result.content) or {}
        else:
            config = {}

        config["enabled"] = False
        yaml_content = yaml.dump(
            config, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
        await ConfigService(server_state.matrix_runtime.paths).write_config(
            "email_proxy", yaml_content, skip_verification=True
        )

        return {"success": True, "message": "Email proxy disabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user-mailbox")
async def add_user_mailbox(request: dict):
    """Add user mailbox"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        ConfigService(server_state.matrix_runtime.paths).add_user_mailbox(email)
        return {"success": True, "message": f"Added user mailbox: {email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/user-mailbox")
async def remove_user_mailbox(request: dict):
    """Remove user mailbox"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        ConfigService(server_state.matrix_runtime.paths).remove_user_mailbox(email)
        return {"success": True, "message": f"Removed user mailbox: {email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
