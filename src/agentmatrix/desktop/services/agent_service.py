import re
import yaml
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from agentmatrix.core.log_util import AutoLoggerMixin
from ..config_schemas import AgentProfile
from ..utils.backup import backup_file, cleanup_old_backups

RESERVED_AGENT_NAMES = {"user", "用户"}


@dataclass
class AgentInfo:
    name: str
    description: str
    backend_model: str
    status: str
    skills: List[str]
    persona: str = ""


class AgentService(AutoLoggerMixin):
    """Agent lifecycle and configuration management service."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.paths = runtime.paths

    def _agent_yml_path(self, name: str) -> Path:
        return self.paths.agent_config_dir / f"{name}.yml"

    def _validate_agent_name(self, name: str) -> None:
        if not name or not name.strip():
            raise ValueError("Agent name cannot be empty")
        if name.lower() in RESERVED_AGENT_NAMES:
            raise ValueError(f"Agent name '{name}' is reserved")
        if not re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$', name):
            raise ValueError(
                f"Agent name '{name}' contains invalid characters. "
                "Use letters, numbers, underscores, hyphens, or CJK characters."
            )

    def _write_agent_yml(self, name: str, profile: dict) -> None:
        yml_path = self._agent_yml_path(name)
        yml_path.write_text(
            yaml.dump(profile, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def _read_agent_yml(self, name: str) -> Optional[dict]:
        yml_path = self._agent_yml_path(name)
        if not yml_path.exists():
            return None
        with open(yml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _backup_agent_yml(self, name: str) -> Optional[Path]:
        yml_path = self._agent_yml_path(name)
        return backup_file(yml_path, self.paths.agent_backup_dir, name)

    def _agent_to_info(self, agent) -> AgentInfo:
        status = "paused" if getattr(agent, '_paused', False) else "running"
        return AgentInfo(
            name=agent.name,
            description=getattr(agent, 'description', ''),
            backend_model=getattr(agent, 'backend_model', ''),
            status=status,
            skills=getattr(agent, 'skills', []),
            persona=getattr(agent, 'persona', ''),
        )

    # ── Profile / Config file operations ──

    def list_profiles(self) -> List[str]:
        if not self.paths.agent_config_dir.exists():
            return []
        return sorted(
            p.stem for p in self.paths.agent_config_dir.glob("*.yml")
        )

    def read_profile(self, name: str) -> Optional[dict]:
        return self._read_agent_yml(name)

    def read_profile_raw(self, name: str) -> Optional[str]:
        yml_path = self._agent_yml_path(name)
        if not yml_path.exists():
            return None
        return yml_path.read_text(encoding="utf-8")

    def validate_profile(self, profile: dict) -> AgentProfile:
        return AgentProfile(**profile)

    async def create_agent(self, name: str, profile: dict):
        self._validate_agent_name(name)
        yml_path = self._agent_yml_path(name)
        if yml_path.exists():
            raise FileExistsError(f"Agent '{name}' already exists")
        validated = self.validate_profile(profile)
        self._write_agent_yml(name, validated.model_dump())
        agent = await self.runtime.load_and_register_agent(name)
        self.echo(f"✅ Agent '{name}' created and registered")
        return agent

    async def update_agent(self, name: str, profile: dict):
        if name not in self.runtime.agents:
            raise ValueError(f"Agent '{name}' not found in runtime")
        validated = self.validate_profile(profile)
        self._backup_agent_yml(name)
        self._write_agent_yml(name, validated.model_dump())
        agent = await self.reload_agent(name)
        return agent

    async def delete_agent(self, name: str):
        if name not in self.runtime.agents:
            raise ValueError(f"Agent '{name}' not found in runtime")
        if name == self.runtime.user_agent_name:
            raise ValueError(f"Cannot delete User agent '{name}'")

        agent = self.runtime.agents[name]
        try:
            agent.stop()
        except Exception as e:
            self.logger.warning(f"Error stopping agent '{name}': {e}")

        if hasattr(agent, 'email_worker_task') and agent.email_worker_task:
            agent.email_worker_task.cancel()
        if hasattr(agent, 'history_worker_task') and agent.history_worker_task:
            agent.history_worker_task.cancel()

        self.runtime.post_office.unregister(agent)
        del self.runtime.agents[name]
        self.runtime.agent_name_set.discard(name)

        if hasattr(self.runtime, 'container_manager') and self.runtime.container_manager:
            try:
                self.runtime.container_manager.remove_user(name)
            except Exception as e:
                self.logger.warning(f"Error removing container user for '{name}': {e}")

        self._backup_agent_yml(name)
        yml_path = self._agent_yml_path(name)
        if yml_path.exists():
            yml_path.unlink()
        self.echo(f"✅ Agent '{name}' deleted")

    async def clone_agent(self, from_name: str, new_name: str):
        self._validate_agent_name(new_name)
        if new_name in self.runtime.agents:
            raise ValueError(f"Agent '{new_name}' already exists in runtime")
        source = self._read_agent_yml(from_name)
        if source is None:
            raise FileNotFoundError(f"Source agent '{from_name}' config not found")
        new_profile = source.copy()
        new_profile["name"] = new_name
        self._write_agent_yml(new_name, new_profile)
        agent = await self.runtime.load_and_register_agent(new_name)
        self.echo(f"✅ Agent '{new_name}' cloned from '{from_name}'")
        return agent

    async def reload_agent(self, name: str):
        if name not in self.runtime.agents:
            raise ValueError(f"Agent '{name}' not found in runtime")

        agent = self.runtime.agents[name]
        await agent.pause()

        if hasattr(agent, 'email_worker_task') and agent.email_worker_task:
            agent.email_worker_task.cancel()
        if hasattr(agent, 'history_worker_task') and agent.history_worker_task:
            agent.history_worker_task.cancel()

        yml_path = self._agent_yml_path(name)
        if not yml_path.exists():
            raise FileNotFoundError(f"Config file not found: {yml_path}")

        new_agent = self.runtime.loader.load_from_file(str(yml_path))
        new_agent.async_event_callback = self.runtime.async_event_callback
        new_agent.runtime = self.runtime

        self.runtime.agents[name] = new_agent
        self.runtime.post_office.register(new_agent)

        agent_task = asyncio.create_task(new_agent.run())
        self.runtime.running_agent_tasks.append(agent_task)
        await new_agent.resume()

        self.echo(f"✅ Agent '{name}' reloaded")
        return new_agent

    # ── Runtime operations ──

    def list_running_agents(self) -> List[AgentInfo]:
        result = []
        for name, agent in self.runtime.agents.items():
            if name == self.runtime.user_agent_name:
                continue
            result.append(self._agent_to_info(agent))
        return result

    def get_agent(self, name: str) -> Optional[AgentInfo]:
        if name not in self.runtime.agents:
            return None
        return self._agent_to_info(self.runtime.agents[name])

    async def pause_agent(self, name: str):
        if name not in self.runtime.agents:
            raise ValueError(f"Agent '{name}' not found")
        await self.runtime.agents[name].pause()

    async def resume_agent(self, name: str):
        if name not in self.runtime.agents:
            raise ValueError(f"Agent '{name}' not found")
        await self.runtime.agents[name].resume()

    async def stop_agent(self, name: str):
        if name not in self.runtime.agents:
            raise ValueError(f"Agent '{name}' not found")
        if name == self.runtime.user_agent_name:
            raise ValueError(f"Cannot stop User agent '{name}'")
        self.runtime.agents[name].stop()

    def toggle_collab(self, name: str, enabled: bool):
        if name not in self.runtime.agents:
            raise ValueError(f"Agent '{name}' not found")
        self.runtime.agents[name].collab_mode = enabled

    # ── Backup ──

    def list_backups(self, name: str) -> List[str]:
        if not self.paths.agent_backup_dir.exists():
            return []
        return sorted(
            p.name for p in self.paths.agent_backup_dir.glob(f"{name}_*")
        )

    def read_backup(self, backup_filename: str) -> Optional[str]:
        backup_path = self.paths.agent_backup_dir / backup_filename
        if not backup_path.exists():
            return None
        return backup_path.read_text(encoding="utf-8")