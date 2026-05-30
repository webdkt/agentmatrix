"""
HTTP proxy configuration routes.
"""

from fastapi import APIRouter, HTTPException

from ..state import server_state

router = APIRouter(prefix="/api/proxy")


def _svc():
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")
    return server_state.matrix_runtime.proxy_service


@router.get("/config")
async def get_proxy_config():
    """Get HTTP Proxy configuration"""
    try:
        proxy = _svc().get_config()
        return {
            "enabled": proxy.get("enabled", False),
            "host": proxy.get("host", ""),
            "port": proxy.get("port", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_proxy_config(request: dict):
    """Update HTTP Proxy configuration"""
    try:
        await _svc().update_config(
            host=request.get("host", ""),
            port=int(request.get("port", 0)),
            enabled=request.get("enabled", False),
        )
        return {"success": True, "message": "Proxy config updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable")
async def enable_proxy():
    """Enable HTTP Proxy"""
    try:
        await _svc().enable()
        return {"success": True, "message": "Proxy enabled"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_proxy():
    """Disable HTTP Proxy"""
    try:
        await _svc().disable()
        return {"success": True, "message": "Proxy disabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_proxy():
    """Test HTTP Proxy connectivity"""
    try:
        result = await _svc().test_connection()
        return {
            "success": result.success,
            "message": result.message,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
