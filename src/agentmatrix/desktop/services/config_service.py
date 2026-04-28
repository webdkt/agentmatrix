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
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..paths import MatrixPaths
from ..config_schemas import (
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

    def list_agent_backups(self, agent_name: str) -> List[BackupInfo]:
        """
        根据 agent 的 name 属性列出配置备份。

        Args:
            agent_name: Agent 的显示名（name 字段的值），如 "John", "SystemAdmin"
        """
        try:
            file_path = self._find_agent_file_by_name(agent_name)
            file_name = file_path.stem
            return self.list_backups("agent", file_name)
        except FileNotFoundError:
            return []

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

    # ==================== Agent Profile (parsed dict) ====================

    def get_agent_profile(self, agent_name: str) -> dict:
        """
        Read agent config and return parsed dict.

        Args:
            agent_name: Agent 的显示名

        Returns:
            dict: Parsed agent profile

        Raises:
            FileNotFoundError: Agent config not found
        """
        file_path = self._find_agent_file_by_name(agent_name)
        content = file_path.read_text(encoding="utf-8")
        profile = yaml.safe_load(content)
        if not profile:
            raise FileNotFoundError(f"Agent config is empty: {file_path}")
        return profile

    # ==================== LLM Config Helpers ====================

    def list_llm_models(self) -> Dict[str, dict]:
        """
        Get all LLM model configurations as a dict.

        Returns:
            Dict mapping model name to config dict
        """
        llm_path = self.paths.llm_config_path
        if not llm_path.exists():
            return {}
        with open(llm_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def add_llm_model(self, name: str, config: dict) -> None:
        """
        Add a new LLM model configuration.

        Args:
            name: Model name (e.g. "my_gpt4")
            config: Config dict with url, API_KEY, model_name

        Raises:
            ValueError: If model name already exists
        """
        llm_path = self.paths.llm_config_path
        if llm_path.exists():
            with open(llm_path, "r", encoding="utf-8") as f:
                llm_config = json.load(f)
        else:
            llm_config = {}

        if name in llm_config:
            raise ValueError(f"LLM config '{name}' already exists")

        llm_config[name] = config

        # Backup before write
        if llm_path.exists():
            self._backup_file(llm_path, "llm")

        llm_path.write_text(
            json.dumps(llm_config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._cleanup_old_backups("llm")

    # ==================== LLM Endpoint CRUD (granular) ====================

    def add_llm_endpoint(self, name: str, entry_content: str) -> ConfigWriteResult:
        """
        Add a new LLM endpoint entry.

        Args:
            name: Entry name (e.g. "gpt4_turbo")
            entry_content: JSON string of the entry config

        Returns:
            ConfigWriteResult
        """
        try:
            entry = json.loads(entry_content)
        except json.JSONDecodeError as e:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="entry_content",
                        value=entry_content[:100],
                        issue=f"Invalid JSON: {e}",
                    )
                ],
                message="Parse failed",
            )

        # Validate entry structure
        try:
            LLMModelConfig(**entry)
        except Exception as e:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(field="entry", value=str(entry)[:100], issue=str(e))
                ],
                message="Schema validation failed",
            )

        # Read current config
        llm_path = self.paths.llm_config_path
        if llm_path.exists():
            with open(llm_path, "r", encoding="utf-8") as f:
                llm_config = json.load(f)
        else:
            llm_config = {}

        if name in llm_config:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="name",
                        value=name,
                        issue=f"LLM endpoint '{name}' already exists",
                    )
                ],
                message="Entry already exists",
            )

        # Backup and write
        if llm_path.exists():
            backup_path = self._backup_file(llm_path, "llm")
        else:
            backup_path = None

        llm_config[name] = entry
        llm_path.write_text(
            json.dumps(llm_config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._cleanup_old_backups("llm")

        return ConfigWriteResult(
            success=True,
            validation_passed=True,
            verification_passed=True,
            backup_path=backup_path,
            file_path=str(llm_path),
            message=f"LLM endpoint '{name}' added successfully",
        )

    def delete_llm_endpoint(self, name: str) -> ConfigWriteResult:
        """
        Delete a LLM endpoint entry.

        Cannot delete default_llm or default_slm.

        Args:
            name: Entry name to delete

        Returns:
            ConfigWriteResult
        """
        if name in ("default_llm", "default_slm"):
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="name",
                        value=name,
                        issue=f"Cannot delete required LLM endpoint '{name}'",
                    )
                ],
                message="Cannot delete required endpoint",
            )

        llm_path = self.paths.llm_config_path
        if not llm_path.exists():
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="config",
                        value="llm_config.json",
                        issue="LLM config file not found",
                    )
                ],
                message="Config not found",
            )

        with open(llm_path, "r", encoding="utf-8") as f:
            llm_config = json.load(f)

        if name not in llm_config:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="name",
                        value=name,
                        issue=f"LLM endpoint '{name}' not found",
                    )
                ],
                message="Entry not found",
            )

        # Backup and write
        backup_path = self._backup_file(llm_path, "llm")
        del llm_config[name]
        llm_path.write_text(
            json.dumps(llm_config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._cleanup_old_backups("llm")

        return ConfigWriteResult(
            success=True,
            validation_passed=True,
            verification_passed=True,
            backup_path=backup_path,
            file_path=str(llm_path),
            message=f"LLM endpoint '{name}' deleted successfully",
        )

    def update_llm_endpoint(self, name: str, entry_content: str) -> ConfigWriteResult:
        """
        Update an existing LLM endpoint entry.

        Args:
            name: Entry name to update
            entry_content: JSON string of the new entry config

        Returns:
            ConfigWriteResult
        """
        try:
            entry = json.loads(entry_content)
        except json.JSONDecodeError as e:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="entry_content",
                        value=entry_content[:100],
                        issue=f"Invalid JSON: {e}",
                    )
                ],
                message="Parse failed",
            )

        # Validate entry structure
        try:
            LLMModelConfig(**entry)
        except Exception as e:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(field="entry", value=str(entry)[:100], issue=str(e))
                ],
                message="Schema validation failed",
            )

        llm_path = self.paths.llm_config_path
        if not llm_path.exists():
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="config",
                        value="llm_config.json",
                        issue="LLM config file not found",
                    )
                ],
                message="Config not found",
            )

        with open(llm_path, "r", encoding="utf-8") as f:
            llm_config = json.load(f)

        if name not in llm_config:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="name",
                        value=name,
                        issue=f"LLM endpoint '{name}' not found",
                    )
                ],
                message="Entry not found",
            )

        # Backup and write
        backup_path = self._backup_file(llm_path, "llm")
        llm_config[name] = entry
        llm_path.write_text(
            json.dumps(llm_config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._cleanup_old_backups("llm")

        return ConfigWriteResult(
            success=True,
            validation_passed=True,
            verification_passed=True,
            backup_path=backup_path,
            file_path=str(llm_path),
            message=f"LLM endpoint '{name}' updated successfully",
        )

    # ==================== Email Proxy User Mailbox ====================

    def add_user_mailbox(self, email: str) -> None:
        """
        Add a user mailbox to email proxy config.

        Args:
            email: Email address to add

        Raises:
            ValueError: If email already exists or config not found
        """
        import re

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise ValueError(f"Invalid email address: {email}")

        ep_path = self.paths.email_proxy_config_path
        if not ep_path.exists():
            raise FileNotFoundError("Email proxy config not found")

        content = ep_path.read_text(encoding="utf-8")
        config = yaml.safe_load(content) or {}

        # Support both single string and list
        current = config.get("user_mailbox", [])
        if isinstance(current, str):
            mailboxes = [current] if current else []
        elif isinstance(current, list):
            mailboxes = current[:]
        else:
            mailboxes = []

        if email in mailboxes:
            raise ValueError(f"Email '{email}' already exists in user_mailbox")

        mailboxes.append(email)

        # Keep as list if multiple, single string if one
        config["user_mailbox"] = (
            mailboxes if len(mailboxes) > 1 else (mailboxes[0] if mailboxes else "")
        )

        # Backup and write
        self._backup_file(ep_path, "email_proxy")
        ep_path.write_text(
            yaml.dump(
                config, allow_unicode=True, default_flow_style=False, sort_keys=False
            ),
            encoding="utf-8",
        )
        self._cleanup_old_backups("email_proxy")

    def remove_user_mailbox(self, email: str) -> None:
        """
        Remove a user mailbox from email proxy config.

        Args:
            email: Email address to remove

        Raises:
            ValueError: If email not found or config not found
        """
        ep_path = self.paths.email_proxy_config_path
        if not ep_path.exists():
            raise FileNotFoundError("Email proxy config not found")

        content = ep_path.read_text(encoding="utf-8")
        config = yaml.safe_load(content) or {}

        current = config.get("user_mailbox", [])
        if isinstance(current, str):
            mailboxes = [current] if current else []
        elif isinstance(current, list):
            mailboxes = current[:]
        else:
            mailboxes = []

        if email not in mailboxes:
            raise ValueError(f"Email '{email}' not found in user_mailbox")

        mailboxes.remove(email)

        # Keep as list if multiple, single string if one
        config["user_mailbox"] = (
            mailboxes if len(mailboxes) > 1 else (mailboxes[0] if mailboxes else "")
        )

        # Backup and write
        self._backup_file(ep_path, "email_proxy")
        ep_path.write_text(
            yaml.dump(
                config, allow_unicode=True, default_flow_style=False, sort_keys=False
            ),
            encoding="utf-8",
        )
        self._cleanup_old_backups("email_proxy")

    # ==================== Agent Lifecycle (runtime required) ====================

    def stop_agent(self, runtime, agent_name: str) -> str:
        """
        停止 Agent 当前的执行（中断当前 email 处理）。

        Agent 仍然在运行时中，可以继续接收和处理新邮件。
        只是当前正在执行的 MicroAgent 会被中断。

        Args:
            runtime: AgentMatrix runtime instance
            agent_name: Name of agent to stop

        Returns:
            str: Success/error message
        """
        if agent_name not in runtime.agents:
            return f"❌ Agent '{agent_name}' not found. Available: {list(runtime.agents.keys())}"

        agent = runtime.agents[agent_name]

        # Check if it's a User agent
        if agent_name == runtime.user_agent_name:
            return f"❌ Cannot stop User agent '{agent_name}'"

        try:
            agent.stop()
            return f"✅ Agent '{agent_name}' 的当前执行已中止"
        except Exception as e:
            return f"❌ Failed to stop agent '{agent_name}': {e}"

    async def clone_agent(self, runtime, from_name: str, new_name: str) -> str:
        """
        Clone an agent: copy profile, save as new name, load into runtime.

        Args:
            runtime: AgentMatrix runtime instance
            from_name: Source agent name
            new_name: New agent name

        Returns:
            str: Success/error message
        """
        # Check new_name doesn't exist
        if new_name in runtime.agents:
            return f"❌ Agent '{new_name}' already exists in runtime"

        if new_name.lower() in ("user", "用户"):
            return f"❌ Agent name cannot be '{new_name}'"

        try:
            # Read source profile
            source_profile = self.get_agent_profile(from_name)

            # Create new profile with new name
            new_profile = source_profile.copy()
            new_profile["name"] = new_name

            # Write new profile
            new_file_path = self.paths.agent_config_dir / f"{new_name}.yml"
            new_file_path.write_text(
                yaml.dump(
                    new_profile,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            # Load into runtime
            try:
                await runtime.load_and_register_agent(new_name)
                return f"✅ Agent '{new_name}' cloned from '{from_name}' and loaded into runtime"
            except Exception as e:
                return f"✅ Agent profile '{new_name}' cloned from '{from_name}', but runtime loading failed: {e}"
        except FileNotFoundError:
            return f"❌ Source agent '{from_name}' not found"
        except Exception as e:
            return f"❌ Clone failed: {e}"

    async def reload_agent(self, runtime, agent_name: str) -> str:
        """
        Reload an agent from its config file.

        Args:
            runtime: AgentMatrix runtime instance
            agent_name: Name of agent to reload

        Returns:
            str: Success/error message
        """
        if agent_name not in runtime.agents:
            return f"❌ Agent '{agent_name}' not found. Available: {list(runtime.agents.keys())}"

        try:
            import asyncio

            agent = runtime.agents[agent_name]

            # Pause and cancel workers
            await agent.pause()

            if hasattr(agent, "email_worker_task") and agent.email_worker_task:
                agent.email_worker_task.cancel()
            if hasattr(agent, "history_worker_task") and agent.history_worker_task:
                agent.history_worker_task.cancel()

            # Find config file
            agent_yml_path = runtime.paths.agent_config_dir / f"{agent_name}.yml"
            if not agent_yml_path.exists():
                return f"❌ Config file not found: {agent_yml_path}"

            # Load new agent
            new_agent = runtime.loader.load_from_file(str(agent_yml_path))
            new_agent.async_event_callback = runtime.async_event_callback
            new_agent.runtime = runtime

            # Replace in runtime
            runtime.agents[agent_name] = new_agent
            runtime.post_office.register(new_agent)

            # Start new agent
            agent_task = asyncio.create_task(new_agent.run())
            runtime.running_agent_tasks.append(agent_task)
            await new_agent.resume()

            return f"✅ Agent '{agent_name}' reloaded successfully"
        except Exception as e:
            return f"❌ Reload failed: {e}"

    def list_agents(self, runtime) -> str:
        """
        List all running agents (excluding User agent).

        Args:
            runtime: AgentMatrix runtime instance

        Returns:
            str: Formatted agent list
        """
        if not runtime.agents:
            return "No agents running"

        lines = [f"Running agents ({len(runtime.agents)}):\n"]
        for agent_name, agent in runtime.agents.items():
            # Skip user agent
            if agent_name == runtime.user_agent_name:
                continue

            status = "running" if not agent.is_paused else "paused"
            lines.append(f"  ** {agent_name} **")
            lines.append(f"     description: {getattr(agent, 'description', 'N/A')}")
            lines.append(f"     status: {status}")
            lines.append(f"     model: {getattr(agent, 'backend_model', 'N/A')}")
            skills = getattr(agent, "skills", [])
            lines.append(f"     skills: {', '.join(skills) if skills else 'none'}")
            lines.append("")

        return "\n".join(lines)

    # ==================== Email Proxy Control (runtime required) ====================

    async def enable_email_proxy(self, runtime) -> str:
        """
        Enable email proxy service.

        Args:
            runtime: AgentMatrix runtime instance

        Returns:
            str: Success/error message
        """
        import yaml

        # Update config
        result = self.read_config("email_proxy")
        if result.success:
            config = yaml.safe_load(result.content) or {}
        else:
            config = {}

        config["enabled"] = True
        yaml_content = yaml.dump(
            config, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
        write_result = await self.write_config(
            "email_proxy", yaml_content, skip_verification=True
        )

        if not write_result.success:
            return f"❌ Failed to update config: {write_result.message}"

        # Start service if runtime has email proxy
        if runtime.email_proxy:
            try:
                runtime.email_proxy_task = asyncio.ensure_future(
                    runtime.email_proxy.start()
                )
                return "✅ Email proxy enabled and started"
            except Exception as e:
                return f"✅ Email proxy config updated (enabled=true), but service start failed: {e}"
        else:
            # Re-initialize email proxy
            try:
                runtime._init_email_proxy()
                return "✅ Email proxy enabled and initialized"
            except Exception as e:
                return f"✅ Email proxy config updated (enabled=true), but initialization failed: {e}"

    async def disable_email_proxy(self, runtime) -> str:
        """
        Disable email proxy service.

        Args:
            runtime: AgentMatrix runtime instance

        Returns:
            str: Success/error message
        """
        import yaml

        # Stop service first
        if runtime.email_proxy:
            try:
                await runtime.email_proxy.stop()
            except Exception as e:
                logger.warning(f"Email proxy stop error: {e}")

        # Update config
        result = self.read_config("email_proxy")
        if result.success:
            config = yaml.safe_load(result.content) or {}
        else:
            config = {}

        config["enabled"] = False
        yaml_content = yaml.dump(
            config, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
        write_result = await self.write_config(
            "email_proxy", yaml_content, skip_verification=True
        )

        if not write_result.success:
            return f"❌ Failed to update config: {write_result.message}"

        return "✅ Email proxy disabled and stopped"

    # ==================== System Restart (placeholder) ====================

    async def restart_system(self, runtime) -> str:
        """
        Restart the system (placeholder - not yet implemented).

        Args:
            runtime: AgentMatrix runtime instance

        Returns:
            str: Status message
        """
        return "⚠️ System restart is not yet implemented. Please restart the server manually."

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
            from agentmatrix.core.skills.registry import SKILL_REGISTRY

            return SKILL_REGISTRY.list_registered_skills()
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

    # ==================== Agent Config (by agent_name) ====================

    def _find_agent_file_by_name(self, agent_name: str) -> Path:
        """
        根据 agent 的 name 属性找到对应的配置文件。
        遍历 agents 目录下的所有 .yml 文件，找到 name 字段匹配的那个。
        """
        agents_dir = self.paths.agent_config_dir
        if not agents_dir.exists():
            raise FileNotFoundError(f"Agents directory not found: {agents_dir}")

        for yml_file in agents_dir.glob("*.yml"):
            try:
                content = yml_file.read_text(encoding="utf-8")
                profile = yaml.safe_load(content)
                if profile and profile.get("name") == agent_name:
                    return yml_file
            except Exception:
                continue

        raise FileNotFoundError(f"Agent config not found for agent_name='{agent_name}'")

    def read_agent_config(self, agent_name: str) -> ConfigReadResult:
        """
        根据 agent 的 name 属性读取配置文件。

        Args:
            agent_name: Agent 的显示名（name 字段的值），如 "John", "SystemAdmin"
        """
        try:
            file_path = self._find_agent_file_by_name(agent_name)
            content = file_path.read_text(encoding="utf-8")
            return ConfigReadResult(
                success=True,
                content=content,
                config_type="agent",
                name=agent_name,
                file_path=str(file_path),
            )
        except FileNotFoundError as e:
            return ConfigReadResult(
                success=False,
                content="",
                config_type="agent",
                name=agent_name,
                file_path="",
                error=str(e),
            )
        except Exception as e:
            return ConfigReadResult(
                success=False,
                content="",
                config_type="agent",
                name=agent_name,
                file_path="",
                error=str(e),
            )

    async def write_agent_config(
        self,
        agent_name: str,
        content: str,
        skip_verification: bool = False,
    ) -> ConfigWriteResult:
        """
        根据 agent 的 name 属性更新配置文件。

        Args:
            agent_name: Agent 的显示名（name 字段的值），如 "John", "SystemAdmin"
            content: 完整的 YAML 配置内容
            skip_verification: 是否跳过连接测试
        """
        try:
            file_path = self._find_agent_file_by_name(agent_name)
            # 使用 write_config 的验证和备份逻辑
            return await self.write_config(
                "agent",
                content,
                file_path.stem,  # 传入文件名（不含后缀）
                skip_verification,
            )
        except FileNotFoundError as e:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[ConfigError(field="agent_name", issue=str(e))],
            )
        except Exception as e:
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[ConfigError(field="agent_name", issue=str(e))],
            )

    async def create_agent_config(
        self,
        agent_name: str,
        content: str,
        skip_verification: bool = False,
    ) -> ConfigWriteResult:
        """
        创建新的 Agent 配置文件。

        Args:
            agent_name: Agent 名称（用作文件名）
            content: 完整的 YAML 配置内容
            skip_verification: 是否跳过连接测试

        Returns:
            ConfigWriteResult - 如果文件已存在则返回错误
        """
        # 检查文件是否已存在
        file_path = self.paths.agent_config_dir / f"{agent_name}.yml"
        if file_path.exists():
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="agent_name",
                        value=agent_name,
                        issue=f"配置文件 '{agent_name}.yml' 已存在",
                        suggestion="请使用 update_agent_profile 更新已有配置，或使用其他名称",
                    )
                ],
                message="Agent config already exists",
            )

        # 检查 name 是否是保留名
        if agent_name.lower() in ("user", "用户"):
            return ConfigWriteResult(
                success=False,
                validation_passed=False,
                verification_passed=False,
                errors=[
                    ConfigError(
                        field="agent_name",
                        value=agent_name,
                        issue=f"'{agent_name}' 是保留名称，不能使用",
                    )
                ],
                message="Reserved name",
            )

        # 使用 write_config 的验证和备份逻辑
        return await self.write_config("agent", content, agent_name, skip_verification)

    def delete_agent_config(self, agent_name: str) -> str:
        """
        删除 Agent 配置文件。

        Args:
            agent_name: Agent 名称

        Returns:
            str: 成功/失败消息
        """
        import os

        file_path = self.paths.agent_config_dir / f"{agent_name}.yml"
        if not file_path.exists():
            return f"配置文件 '{agent_name}.yml' 不存在"

        os.remove(file_path)
        return f"配置文件 '{agent_name}.yml' 已删除"

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
            from ..config_verifier import verify_email_proxy_config

            results = await verify_email_proxy_config(parsed)
            return [r.to_dict() for r in results]

        if config_type == "llm":
            from ..config_verifier import verify_llm_connection

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
