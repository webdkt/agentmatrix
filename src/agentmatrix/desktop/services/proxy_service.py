import asyncio
import os
import yaml
from datetime import datetime
from typing import Dict, List

from agentmatrix.core.log_util import AutoLoggerMixin
from ..config_schemas import ProxyConfig as ProxyConfigSchema, SystemConfig as SystemConfigSchema
from ..config_verifier import VerifyResult
from ..utils.backup import backup_file, cleanup_old_backups


class ProxyService(AutoLoggerMixin):
    """HTTP Proxy configuration and connectivity service."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.paths = runtime.paths
        self.config = runtime.config

    def _system_config_dict(self) -> dict:
        return self.config._matrix_config

    def _persist(self) -> None:
        system_path = self.paths.system_config_path
        system_path.parent.mkdir(parents=True, exist_ok=True)
        with open(system_path, "w", encoding="utf-8") as f:
            yaml.dump(
                self._system_config_dict(),
                f,
                allow_unicode=True,
                default_flow_style=False,
            )
        self.config._matrix_config = self._system_config_dict()
        self.config._proxy_config = self._system_config_dict().get("proxy", {})
        self._apply_proxy_env_vars()

    def _apply_proxy_env_vars(self) -> None:
        proxy = self.config._proxy_config
        if proxy and proxy.get("enabled") and proxy.get("host") and proxy.get("port"):
            proxy_url = f"http://{proxy['host']}:{proxy['port']}"
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            self.echo(f"✅ HTTP Proxy enabled: {proxy_url}")
        else:
            app_key = "HTTP_PROXY"
            for var in ("HTTP_PROXY", "HTTPS_PROXY"):
                if app_key + "_SET_BY_AMX" in os.environ:
                    os.environ.pop(var, None)
            self.echo("ℹ️ HTTP Proxy disabled")

    # ── Read ──

    def get_config(self) -> dict:
        return dict(self.config._proxy_config)

    # ── Write ──

    async def update_config(self, host: str, port: int, enabled: bool):
        backup_file(self.paths.system_config_path, self.paths.backup_dir, "system_config")
        proxy_data = {"enabled": enabled, "host": host, "port": port}
        validated = ProxyConfigSchema(**proxy_data)
        self.config._matrix_config["proxy"] = validated.model_dump()
        self._persist()
        cleanup_old_backups(self.paths.backup_dir, "system_config")

    async def enable(self):
        proxy = self.config._proxy_config
        if not proxy.get("host") or not proxy.get("port"):
            raise ValueError("Proxy host and port must be configured before enabling")
        self.config._matrix_config.setdefault("proxy", {})["enabled"] = True
        self._persist()

    async def disable(self):
        self.config._matrix_config.setdefault("proxy", {})["enabled"] = False
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        self._persist()

    async def test_connection(self) -> VerifyResult:
        import aiohttp

        proxy = self.config._proxy_config
        if not proxy.get("host") or not proxy.get("port"):
            return VerifyResult(
                success=False,
                test_type="proxy_connection",
                message="Proxy not configured (missing host or port)",
            )

        proxy_url = f"http://{proxy['host']}:{proxy['port']}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://www.google.com",
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status in (200, 204):
                        return VerifyResult(
                            success=True,
                            test_type="proxy_connection",
                            message=f"Proxy connection successful ({proxy_url})",
                        )
                    return VerifyResult(
                        success=False,
                        test_type="proxy_connection",
                        message=f"Proxy returned status {resp.status}",
                    )
        except aiohttp.ClientConnectorError as e:
            return VerifyResult(
                success=False,
                test_type="proxy_connection",
                message=f"Connection failed: {e}",
            )
        except asyncio.TimeoutError:
            return VerifyResult(
                success=False,
                test_type="proxy_connection",
                message="Connection timed out after 10s",
            )
        except Exception as e:
            return VerifyResult(
                success=False,
                test_type="proxy_connection",
                message=f"Unexpected error: {e}",
            )

    # ── Raw config access (for skill/API use) ──

    def read_raw(self) -> str:
        system_path = self.paths.system_config_path
        if not system_path.exists():
            return ""
        return system_path.read_text(encoding="utf-8")

    async def write_full_config(self, content: str) -> dict:
        try:
            parsed = yaml.safe_load(content) or {}
        except Exception as e:
            return {"success": False, "message": f"Invalid YAML: {e}"}

        try:
            SystemConfigSchema(**parsed)
        except Exception as e:
            return {"success": False, "message": f"Schema validation failed: {e}"}

        backup_file(self.paths.system_config_path, self.paths.backup_dir, "system_config")

        system_path = self.paths.system_config_path
        system_path.parent.mkdir(parents=True, exist_ok=True)
        with open(system_path, "w", encoding="utf-8") as f:
            yaml.dump(parsed, f, allow_unicode=True, default_flow_style=False)

        cleanup_old_backups(self.paths.backup_dir, "system_config")

        self.config._matrix_config.clear()
        self.config._matrix_config.update(parsed)
        self.config._proxy_config = parsed.get("proxy", {})
        self._apply_proxy_env_vars()

        return {"success": True, "message": "System config updated successfully"}

    def list_backups(self) -> List[dict]:
        backup_dir = self.paths.backup_dir
        if not backup_dir.exists():
            return []
        results = []
        for f in sorted(backup_dir.glob("system_config_*"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = f.stat()
            results.append({
                "name": f.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
        return results

    def read_backup(self, filename: str) -> str:
        path = self.paths.backup_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Backup not found: {filename}")
        return path.read_text(encoding="utf-8")

    @staticmethod
    async def restart_system() -> str:
        return "⚠️ System restart is not yet implemented. Please restart the server manually."