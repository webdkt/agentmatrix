"""
HTTP proxy configuration routes.
"""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..state import server_state

router = APIRouter(prefix="/api/proxy")


@router.get("/config")
async def get_proxy_config():
    """Get HTTP Proxy configuration from system_config.yml"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        import yaml

        system_config_path = (
            Path(server_state.matrix_world_dir)
            / ".matrix"
            / "configs"
            / "system_config.yml"
        )

        if not system_config_path.exists():
            return {"enabled": False, "host": "", "port": 0}

        with open(system_config_path, "r", encoding="utf-8") as f:
            system_config = yaml.safe_load(f) or {}

        proxy = system_config.get("proxy", {})
        return {
            "enabled": proxy.get("enabled", False),
            "host": proxy.get("host", ""),
            "port": proxy.get("port", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_proxy_config(request: dict):
    """Update HTTP Proxy configuration in system_config.yml"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        import yaml

        system_config_path = (
            Path(server_state.matrix_world_dir)
            / ".matrix"
            / "configs"
            / "system_config.yml"
        )

        if system_config_path.exists():
            with open(system_config_path, "r", encoding="utf-8") as f:
                system_config = yaml.safe_load(f) or {}
        else:
            system_config = {}

        system_config["proxy"] = {
            "enabled": request.get("enabled", False),
            "host": request.get("host", ""),
            "port": int(request.get("port", 0)),
        }

        system_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(system_config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                system_config,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        if (
            system_config["proxy"]["enabled"]
            and system_config["proxy"]["host"]
            and system_config["proxy"]["port"]
        ):
            proxy_url = f"http://{system_config['proxy']['host']}:{system_config['proxy']['port']}"
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url

        return {"success": True, "message": "Proxy config updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable")
async def enable_proxy():
    """Enable HTTP Proxy"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        import yaml

        system_config_path = (
            Path(server_state.matrix_world_dir)
            / ".matrix"
            / "configs"
            / "system_config.yml"
        )

        if system_config_path.exists():
            with open(system_config_path, "r", encoding="utf-8") as f:
                system_config = yaml.safe_load(f) or {}
        else:
            system_config = {}

        if "proxy" not in system_config:
            system_config["proxy"] = {"enabled": False, "host": "", "port": 0}

        system_config["proxy"]["enabled"] = True

        with open(system_config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                system_config,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        proxy = system_config["proxy"]
        if proxy.get("host") and proxy.get("port"):
            proxy_url = f"http://{proxy['host']}:{proxy['port']}"
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url

        return {"success": True, "message": "Proxy enabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_proxy():
    """Disable HTTP Proxy"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        import yaml

        system_config_path = (
            Path(server_state.matrix_world_dir)
            / ".matrix"
            / "configs"
            / "system_config.yml"
        )

        if system_config_path.exists():
            with open(system_config_path, "r", encoding="utf-8") as f:
                system_config = yaml.safe_load(f) or {}
        else:
            return {"success": True, "message": "Proxy already disabled"}

        if "proxy" in system_config:
            system_config["proxy"]["enabled"] = False

        with open(system_config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                system_config,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        if "proxy" in system_config:
            old_url = f"http://{system_config['proxy'].get('host', '')}:{system_config['proxy'].get('port', '')}"
            for var in ("HTTP_PROXY", "HTTPS_PROXY"):
                if os.environ.get(var) == old_url:
                    os.environ.pop(var, None)

        return {"success": True, "message": "Proxy disabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_proxy():
    """Test HTTP Proxy connectivity"""
    try:
        if not server_state.matrix_runtime:
            raise HTTPException(status_code=503, detail="Runtime not initialized")

        import yaml
        import aiohttp
        import asyncio

        system_config_path = (
            Path(server_state.matrix_world_dir)
            / ".matrix"
            / "configs"
            / "system_config.yml"
        )

        if not system_config_path.exists():
            return {"success": False, "message": "Proxy not configured"}

        with open(system_config_path, "r", encoding="utf-8") as f:
            system_config = yaml.safe_load(f) or {}

        proxy = system_config.get("proxy", {})
        if not proxy.get("enabled") or not proxy.get("host") or not proxy.get("port"):
            return {
                "success": False,
                "message": "Proxy is not enabled or not fully configured",
            }

        proxy_url = f"http://{proxy['host']}:{proxy['port']}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "http://www.gstatic.com/generate_204",
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 204 or resp.status == 200:
                        return {
                            "success": True,
                            "message": f"Proxy {proxy_url} is working",
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Proxy returned status {resp.status}",
                        }
        except aiohttp.ClientConnectorError as e:
            return {"success": False, "message": f"Connection failed: {str(e)}"}
        except asyncio.TimeoutError:
            return {"success": False, "message": "Connection timed out after 10s"}
        except Exception as e:
            return {"success": False, "message": f"Proxy test failed: {str(e)}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
