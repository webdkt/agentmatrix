"""
ConfigService - Content-First Configuration Management

Design principles:
- Read: return raw YAML/JSON content as string
- Write: accept raw YAML/JSON content, validate, verify, backup, then write
- Schema discovery: expose JSON Schema for Agent to understand expected structure
- Backup: auto backup before every write, keep last 5 per config type
- Agent never touches files directly
"""

import json
import yaml
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..core.paths import MatrixPaths
from ..core.config_schemas import (
    AgentProfile,
    LLMModelConfig,
    LLMConfig,
    SystemConfig,
    EmailProxyConfig,
    get_schema,
    get_config_types,
)

logger = logging.getLogger(__name__)

BACKUP_KEEP_COUNT = 5


# ==================== Result Types ====================


@dataclass
class ConfigError:
    field: str
    value: Any
    issue: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        d = {"field": self.field, "value": str(self.value)[:200], "issue": self.issue}
        if self.suggestion:
            d["suggestion"] = self.suggestion
        return d


@dataclass
class ConfigReadResult:
    success: bool
    content: str
    config_type: str
    name: Optional[str]
    file_path: str
    error: Optional[str] = None


@dataclass
class ConfigWriteResult:
    success: bool
    validation_passed: bool
    verification_passed: bool
    errors: List[ConfigError] = field(default_factory=list)
    verify_results: List[dict] = field(default_factory=list)
    backup_path: Optional[str] = None
    file_path: Optional[str] = None
    message: str = ""

    def to_dict(self) -> dict:
        d = {
            "success": self.success,
            "validation_passed": self.validation_passed,
            "verification_passed": self.verification_passed,
            "message": self.message,
        }
        if self.errors:
            d["errors"] = [e.to_dict() for e in self.errors]
        if self.verify_results:
            d["verification"] = self.verify_results
        if self.backup_path:
            d["backup_path"] = self.backup_path
        if self.file_path:
            d["file_path"] = self.file_path
        return d


@dataclass
class ConfigValidateResult:
    success: bool
    errors: List[ConfigError] = field(default_factory=list)
    parsed_content: Optional[dict] = None
    message: str = ""


@dataclass
class BackupInfo:
    name: str
    path: str
    size: int
    modified: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "modified": self.modified,
        }


# ==================== ConfigService ====================


class ConfigService:
    """
    Content-First Configuration Management Service.

    All config operations go through this service.
    Config files are never accessed directly by agents.
    """

    def __init__(self, paths: MatrixPaths):
        self.paths = paths

    # ==================== Schema & Discovery ====================

    def list_config_types(self) -> List[str]:
        """Return available config types."""
        return get_config_types()

    def get_schema(self, config_type: str) -> dict:
        """
        Get JSON Schema for a config type.

        Args:
            config_type: "agent", "llm", "system", "email_proxy"

        Returns:
            dict: JSON Schema
        """
        return get_schema(config_type)

    # ==================== Read ====================

    def read_config(self, config_type: str, name: str = None) -> ConfigReadResult:
        """
        Read config and return raw content.

        Args:
            config_type: "agent", "llm", "system", "email_proxy"
            name: Agent name (only for config_type="agent")
        """
        try:
            file_path = self._resolve_file_path(config_type, name)
            if not file_path.exists():
                return ConfigReadResult(
                    success=False,
                    content="",
                    config_type=config_type,
                    name=name,
                    file_path=str(file_path),
                    error=f"Config file not found: {file_path}",
                )

            content = file_path.read_text(encoding="utf-8")
            return ConfigReadResult(
                success=True,
                content=content,
                config_type=config_type,
                name=name,
                file_path=str(file_path),
            )
        except Exception as e:
            return ConfigReadResult(
                success=False,
                content="",
                config_type=config_type,
                name=name,
                file_path="",
                error=str(e),
            )

    # ==================== Write ====================

    async def write_config(
        self,
        config_type: str,
        content: str,
        name: str = None,
        skip_verification: bool = False,
    ) -> ConfigWriteResult:
        """
        Write config: parse → validate → verify → backup → write.

        Args:
            config_type: "agent", "llm", "system", "email_proxy"
            content: Raw YAML/JSON string
            name: Agent name (only for config_type="agent")
            skip_verification: If True, skip connection tests (for initial setup)

        Returns:
            ConfigWriteResult with structured feedback
        """
        # Step 1: Parse
        try:
            parsed = self._parse_content(config_type, content)
        except Exception as e:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="(parse)",
                        value=content[:200],
                        issue=f"Failed to parse content: {str(e)}",
                        suggestion=f"Content should be valid {'JSON' if config_type == 'llm' else 'YAML'}.",
                    )
                ],
                message="Parse failed",
            )

        # Step 2: Pydantic validation
        errors = self._validate_with_schema(config_type, parsed)
        if errors:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=errors,
                message="Schema validation failed",
            )

        # Step 3: Basic content validation
        content_errors = self._validate_content(config_type, parsed, name)
        if content_errors:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=content_errors,
                message="Content validation failed",
            )

        # Step 4: Verification tests (optional)
        verify_results = []
        if not skip_verification:
            verify_results = await self._run_verification(config_type, parsed)
            verify_failed = any(not r.get("success", False) for r in verify_results)
            if verify_failed:
                return ConfigWriteResult(
                    success=False,
                    validation_passed=True,
                    verification_passed=False,
                    verify_results=verify_results,
                    message="Verification tests failed",
                )

        # Step 5: Backup old file
        file_path = self._resolve_file_path(config_type, name)
        backup_path = None
        if file_path.exists():
            backup_path = self._backup_file(file_path, config_type, name)

        # Step 6: Write new file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if config_type == "llm":
            file_path.write_text(
                json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        else:
            file_path.write_text(
                yaml.dump(
                    parsed,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

        # Step 7: Cleanup old backups
        self._cleanup_old_backups(config_type, name)

        return ConfigWriteResult(
            success=True,
            validation_passed=True,
            verification_passed=True if not skip_verification else None,
            verify_results=verify_results,
            backup_path=backup_path,
            file_path=str(file_path),
            message=f"Config '{config_type}' written successfully",
        )

    # ==================== Validate Only ====================

    def validate_config(
        self, config_type: str, content: str, name: str = None
    ) -> ConfigValidateResult:
        """
        Validate config without writing.

        Args:
            config_type: "agent", "llm", "system", "email_proxy"
            content: Raw YAML/JSON string
            name: Agent name (only for config_type="agent")
        """
        try:
            parsed = self._parse_content(config_type, content)
        except Exception as e:
            return ConfigValidateResult(
                success=False,
                errors=[
                    ConfigError(
                        field="(parse)",
                        value=content[:200],
                        issue=f"Failed to parse: {str(e)}",
                    )
                ],
                message="Parse failed",
            )

        schema_errors = self._validate_with_schema(config_type, parsed)
        content_errors = self._validate_content(config_type, parsed, name)
        all_errors = schema_errors + content_errors

        return ConfigValidateResult(
            success=len(all_errors) == 0,
            errors=all_errors,
            parsed_content=parsed,
            message="Validation passed"
            if not all_errors
            else f"{len(all_errors)} error(s) found",
        )

    # ==================== Backup ====================

    def list_backups(self, config_type: str, name: str = None) -> List[BackupInfo]:
        """
        List available backups for a config type.

        Args:
            config_type: "agent", "llm", "system", "email_proxy"
            name: Agent name (only for config_type="agent")
        """
        if config_type == "agent":
            backup_dir = self.paths.agent_backup_dir
            pattern = f"{name}_*.yml" if name else "*.yml"
        elif config_type == "llm":
            backup_dir = self.paths.backup_dir
            pattern = "llm_config_*.json"
        elif config_type == "system":
            backup_dir = self.paths.backup_dir
            pattern = "system_config_*.yml"
        elif config_type == "email_proxy":
            backup_dir = self.paths.backup_dir
            pattern = "email_proxy_config_*.yml"
        else:
            return []

        if not backup_dir.exists():
            return []

        backups = []
        for f in sorted(backup_dir.glob(pattern), reverse=True):
            stat = f.stat()
            backups.append(
                BackupInfo(
                    name=f.name,
                    path=str(f),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                )
            )

        return backups

    def read_backup(self, config_type: str, backup_name: str, name: str = None) -> str:
        """
        Read a specific backup file.

        Args:
            config_type: "agent", "llm", "system", "email_proxy"
            backup_name: Backup filename (e.g. "SystemAdmin_20260324_120000.yml")
            name: Agent name (for path resolution)
        """
        if config_type == "agent":
            backup_dir = self.paths.agent_backup_dir
        else:
            backup_dir = self.paths.backup_dir

        backup_path = backup_dir / backup_name
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        return backup_path.read_text(encoding="utf-8")

    # ==================== Agent-specific helpers ====================

    def list_agent_profiles(self) -> List[str]:
        """List all agent profile names (without .yml extension)."""
        agent_dir = self.paths.agent_config_dir
        if not agent_dir.exists():
            return []
        return [
            f.stem
            for f in sorted(agent_dir.glob("*.yml"))
            if f.name != "llm_config.json"
        ]

    def get_available_skills(self) -> List[str]:
        """Get list of registered skill names for validation."""
        try:
            from ..skills.registry import SKILL_REGISTRY

            registered = SKILL_REGISTRY.list_registered_skills()
            return registered.get("python", []) + registered.get("md", [])
        except Exception:
            return []

    def get_available_llm_models(self) -> List[str]:
        """Get list of configured LLM model names for validation."""
        try:
            llm_path = self.paths.llm_config_path
            if llm_path.exists():
                with open(llm_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                return list(config.keys())
        except Exception:
            pass
        return []

    # ==================== Internal helpers ====================

    def _resolve_file_path(self, config_type: str, name: str = None) -> Path:
        """Resolve config file path for a given type and name."""
        if config_type == "agent":
            if not name:
                raise ValueError("Agent name is required for config_type='agent'")
            return self.paths.agent_config_dir / f"{name}.yml"
        elif config_type == "llm":
            return self.paths.llm_config_path
        elif config_type == "system":
            return self.paths.system_config_path
        elif config_type == "email_proxy":
            return self.paths.email_proxy_config_path
        else:
            raise ValueError(
                f"Unknown config type: '{config_type}'. Available: {get_config_types()}"
            )

    def _parse_content(self, config_type: str, content: str) -> dict:
        """Parse YAML or JSON content into dict."""
        if config_type == "llm":
            return json.loads(content)
        else:
            return yaml.safe_load(content) or {}

    def _validate_with_schema(
        self, config_type: str, parsed: dict
    ) -> List[ConfigError]:
        """Validate parsed content against Pydantic schema."""
        schema_map = {
            "agent": AgentProfile,
            "llm": self._validate_llm_schema,
            "system": SystemConfig,
            "email_proxy": EmailProxyConfig,
        }

        validator = schema_map.get(config_type)
        if not validator:
            return []

        errors = []
        try:
            if callable(validator) and not isinstance(validator, type):
                # Custom validator for LLM (dynamic keys)
                validator(parsed)
            else:
                validator(**parsed)
        except Exception as e:
            # Parse Pydantic validation errors
            if hasattr(e, "errors"):
                for err in e.errors():
                    field_path = ".".join(str(loc) for loc in err["loc"])
                    errors.append(
                        ConfigError(
                            field=field_path,
                            value=err.get("input", ""),
                            issue=err["msg"],
                            suggestion=self._get_suggestion(
                                config_type, field_path, err
                            ),
                        )
                    )
            else:
                errors.append(
                    ConfigError(field="(schema)", value=str(parsed)[:200], issue=str(e))
                )

        return errors

    def _validate_llm_schema(self, parsed: dict):
        """Custom LLM validation: each entry must have url, API_KEY, model_name."""
        for key, value in parsed.items():
            if not isinstance(value, dict):
                raise ValueError(f"LLM config entry '{key}' must be a dict")
            LLMModelConfig(**value)

    def _validate_content(
        self, config_type: str, parsed: dict, name: str = None
    ) -> List[ConfigError]:
        """Basic content validation beyond schema."""
        errors = []

        if config_type == "agent":
            # Validate skills exist in registry
            available_skills = self.get_available_skills()
            skills = parsed.get("skills", [])
            for skill in skills:
                if skill not in available_skills:
                    errors.append(
                        ConfigError(
                            field="skills",
                            value=skill,
                            issue=f"Skill '{skill}' not found in registry",
                            suggestion=f"Available skills: {', '.join(available_skills)}",
                        )
                    )

            # Validate backend_model exists in llm_config
            available_models = self.get_available_llm_models()
            backend_model = parsed.get("backend_model", "default_llm")
            if backend_model not in available_models:
                errors.append(
                    ConfigError(
                        field="backend_model",
                        value=backend_model,
                        issue=f"Model '{backend_model}' not found in llm_config.json",
                        suggestion=f"Available models: {', '.join(available_models)}",
                    )
                )

        return errors

    def _get_suggestion(self, config_type: str, field_path: str, error: dict) -> str:
        """Generate helpful suggestions for validation errors."""
        if config_type == "agent" and "skills" in field_path:
            skills = self.get_available_skills()
            return (
                f"Available skills: {', '.join(skills)}"
                if skills
                else "No skills registered"
            )
        if config_type == "agent" and "backend_model" in field_path:
            models = self.get_available_llm_models()
            return (
                f"Available models: {', '.join(models)}"
                if models
                else "No models configured"
            )
        return ""

    async def _run_verification(self, config_type: str, parsed: dict) -> List[dict]:
        """Run verification tests for applicable config types."""
        if config_type == "email_proxy" and parsed.get("enabled"):
            from ..core.config_verifier import verify_email_proxy_config

            results = await verify_email_proxy_config(parsed)
            return [r.to_dict() for r in results]

        if config_type == "llm":
            from ..core.config_verifier import verify_llm_connection

            results = []
            for key, value in parsed.items():
                if isinstance(value, dict) and key != "default_slm":
                    result = await verify_llm_connection(value)
                    results.append(result.to_dict())
            return results

        return []

    def _backup_file(
        self, file_path: Path, config_type: str, name: str = None
    ) -> Optional[str]:
        """Create a timestamped backup of a config file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = file_path.suffix

            if config_type == "agent":
                backup_dir = self.paths.agent_backup_dir
                backup_name = f"{name}_{timestamp}{suffix}"
            else:
                backup_dir = self.paths.backup_dir
                stem = file_path.stem  # e.g. "llm_config", "system_config"
                backup_name = f"{stem}_{timestamp}{suffix}"

            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / backup_name

            import shutil

            shutil.copy2(file_path, backup_path)
            logger.info(f"📦 Backed up {file_path.name} → {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.warning(f"Failed to backup {file_path}: {e}")
            return None

    def _cleanup_old_backups(self, config_type: str, name: str = None):
        """Keep only the last BACKUP_KEEP_COUNT backups."""
        backups = self.list_backups(config_type, name)
        if len(backups) > BACKUP_KEEP_COUNT:
            for old in backups[BACKUP_KEEP_COUNT:]:
                try:
                    Path(old.path).unlink()
                    logger.debug(f"🗑️ Removed old backup: {old.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove old backup {old.name}: {e}")
