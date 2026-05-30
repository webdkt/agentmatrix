"""
Email proxy configuration routes.
"""

import yaml

from fastapi import APIRouter, HTTPException

from ..state import server_state

router = APIRouter(prefix="/api/email-proxy")


def _svc():
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")
    return server_state.matrix_runtime.email_proxy_config_svc


@router.get("/config")
async def get_email_proxy_config():
    """Get Email Proxy configuration"""
    try:
        raw = _svc().read_raw()
        config = yaml.safe_load(raw) or {}
        return config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_email_proxy_config(request: dict):
    """Update Email Proxy configuration"""
    try:
        yaml_content = yaml.dump(
            request, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
        result = await _svc().write_full_config(yaml_content)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "Update failed"))

        return {"success": True, "message": "Email proxy config updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable")
async def enable_email_proxy():
    """Enable Email Proxy"""
    try:
        msg = await _svc().enable()
        return {"success": True, "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_email_proxy():
    """Disable Email Proxy"""
    try:
        msg = await _svc().disable()
        return {"success": True, "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user-mailbox")
async def add_user_mailbox(request: dict):
    """Add user mailbox"""
    try:
        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        _svc().add_user_mailbox(email)
        return {"success": True, "message": f"Added user mailbox: {email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/user-mailbox")
async def remove_user_mailbox(request: dict):
    """Remove user mailbox"""
    try:
        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        _svc().remove_user_mailbox(email)
        return {"success": True, "message": f"Removed user mailbox: {email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
