import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from agentmatrix.core.log_util import AutoLoggerMixin
from ..config_schemas import LLMModelConfig
from ..config_verifier import verify_llm_connection
from ..utils.backup import backup_file, cleanup_old_backups


class LLMService(AutoLoggerMixin):
    """LLM configuration management and monitoring service."""

    REQUIRED_ENDPOINTS = {"default_llm", "default_slm"}

    def __init__(self, runtime):
        self.runtime = runtime
        self.paths = runtime.paths
        self.config = runtime.config
        self._monitor = None

    def _llm_config_dict(self) -> dict:
        return self.config._llm_config

    def _persist(self) -> None:
        llm_path = self.paths.llm_config_path
        llm_path.parent.mkdir(parents=True, exist_ok=True)
        with open(llm_path, "w", encoding="utf-8") as f:
            json.dump(self._llm_config_dict(), f, ensure_ascii=False, indent=2)
        self._sync_loader()

    def _sync_loader(self) -> None:
        if hasattr(self.runtime, 'loader') and self.runtime.loader:
            self.runtime.loader.llm_config = dict(self._llm_config_dict())

    # ── Read ──

    def list_models(self) -> Dict[str, Any]:
        return dict(self._llm_config_dict())

    def get_model_config(self, name: str) -> Optional[Dict[str, Any]]:
        return self._llm_config_dict().get(name)

    # ── Write ──

    async def add_endpoint(self, name: str, config: dict):
        llm = self._llm_config_dict()
        if name in llm:
            raise ValueError(f"LLM endpoint '{name}' already exists")
        validated = LLMModelConfig(**config)
        llm[name] = validated.model_dump()
        self.config._llm_config[name] = llm[name]
        self._persist()

    async def update_endpoint(self, name: str, config: dict):
        llm = self._llm_config_dict()
        if name not in llm:
            raise ValueError(f"LLM endpoint '{name}' not found")
        validated = LLMModelConfig(**config)
        backup_file(self.paths.llm_config_path, self.paths.backup_dir, "llm_config")
        llm[name] = validated.model_dump()
        self.config._llm_config[name] = llm[name]
        self._persist()
        cleanup_old_backups(self.paths.backup_dir, "llm_config")

    async def delete_endpoint(self, name: str):
        if name in self.REQUIRED_ENDPOINTS:
            raise ValueError(f"Cannot delete required endpoint '{name}'")
        llm = self._llm_config_dict()
        if name not in llm:
            raise ValueError(f"LLM endpoint '{name}' not found")
        backup_file(self.paths.llm_config_path, self.paths.backup_dir, "llm_config")
        del self.config._llm_config[name]
        self._persist()
        cleanup_old_backups(self.paths.backup_dir, "llm_config")

    async def reset_endpoint(self, name: str):
        if name not in self.REQUIRED_ENDPOINTS:
            raise ValueError(f"Can only reset required endpoints, got '{name}'")
        defaults = self.config._get_default_llm_config()
        if name not in defaults:
            raise ValueError(f"No default for '{name}'")
        backup_file(self.paths.llm_config_path, self.paths.backup_dir, "llm_config")
        self.config._llm_config[name] = defaults[name]
        self._persist()
        cleanup_old_backups(self.paths.backup_dir, "llm_config")

    # ── Validation ──

    def validate_config(self, config: dict):
        return LLMModelConfig(**config)

    async def verify_connection(self, name: str):
        config = self.get_model_config(name)
        if config is None:
            raise ValueError(f"LLM endpoint '{name}' not found")
        return await verify_llm_connection(config)

    # ── Monitor ──

    def start_monitor(self):
        from ..service_monitor import LLMServiceMonitor

        llm_config = dict(self._llm_config_dict())
        self._monitor = LLMServiceMonitor(
            llm_config=llm_config,
            check_interval=5,
            parent_logger=self.logger,
        )
        self._monitor_task = asyncio.create_task(self._monitor.start())
        self.echo("✅ LLM Service Monitor started")

    async def stop_monitor(self):
        if self._monitor:
            await asyncio.wait_for(self._monitor.stop(), timeout=5.0)
        if hasattr(self, '_monitor_task') and self._monitor_task:
            self._monitor_task.cancel()
            try:
                await asyncio.wait_for(self._monitor_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            self._monitor_task = None
        self.echo("✅ LLM Service Monitor stopped")

    def is_available(self, service_name: Optional[str] = None) -> bool:
        if self._monitor is None:
            return True
        return self._monitor.is_available(service_name)

    def get_monitor_status(self) -> Dict[str, bool]:
        if self._monitor is None:
            return {}
        return self._monitor.get_status()

    # ── Raw config access (for skill/API use) ──

    def read_raw(self) -> str:
        llm_path = self.paths.llm_config_path
        if not llm_path.exists():
            return "{}"
        return llm_path.read_text(encoding="utf-8")

    async def write_full_config(self, content: str) -> dict:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            return {"success": False, "message": f"Invalid JSON: {e}"}

        errors = []
        for key, value in parsed.items():
            if not isinstance(value, dict):
                errors.append(f"Entry '{key}' must be a dict")
                continue
            try:
                LLMModelConfig(**value)
            except Exception as ve:
                errors.append(f"Entry '{key}': {ve}")
        if errors:
            return {"success": False, "message": "Validation failed", "errors": errors}

        verify_results = []
        for key, value in parsed.items():
            if isinstance(value, dict) and key != "default_slm":
                result = await verify_llm_connection(value)
                verify_results.append(result.to_dict())
        verify_failed = any(not r.get("success", False) for r in verify_results)
        if verify_failed:
            return {
                "success": False,
                "message": "Verification tests failed",
                "verification": verify_results,
            }

        backup_file(self.paths.llm_config_path, self.paths.backup_dir, "llm_config")

        self.config._llm_config.clear()
        self.config._llm_config.update(parsed)
        self._persist()
        cleanup_old_backups(self.paths.backup_dir, "llm_config")

        return {"success": True, "message": "LLM config updated successfully"}

    def list_backups(self) -> List[dict]:
        backup_dir = self.paths.backup_dir
        if not backup_dir.exists():
            return []
        results = []
        for f in sorted(backup_dir.glob("llm_config_*"), key=lambda p: p.stat().st_mtime, reverse=True):
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