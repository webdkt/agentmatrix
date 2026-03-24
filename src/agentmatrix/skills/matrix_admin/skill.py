"""
Matrix Admin Skill - AgentMatrix System Configuration

Content-first approach:
- read_config: return raw YAML/JSON content
- write_config: accept raw content, validate, verify, backup, write
- Agent reads config → thinks → provides modified content → service validates & writes

This skill is the ONLY way agents should interact with system configuration.
Agents never touch config files directly.
"""

from typing import Optional, Dict, Any, List
from ...core.action import register_action
import yaml


class Matrix_adminSkillMixin:
    """AgentMatrix system configuration management"""

    _skill_description = (
        "系统配置管理：读取/修改 Agent profile、LLM 配置、系统配置、Email Proxy 配置。"
        "支持配置验证、连接测试、备份管理。"
    )
    _skill_dependencies = ["base"]

    def _get_config_service(self):
        """Get ConfigService from runtime."""
        runtime = self.root_agent.runtime
        if not runtime:
            raise RuntimeError("Runtime not available. ConfigService requires runtime.")
        return runtime.config_service

    def _format_result(self, result) -> str:
        """Format a result object into LLM-friendly text."""
        if isinstance(result, dict):
            if result.get("success"):
                lines = [f"✅ {result.get('message', 'Success')}"]
                if result.get("backup_path"):
                    lines.append(f"📦 Backup: {result['backup_path']}")
                if result.get("file_path"):
                    lines.append(f"📄 File: {result['file_path']}")
                if result.get("verification"):
                    lines.append("\nVerification results:")
                    for v in result["verification"]:
                        icon = "✅" if v.get("success") else "❌"
                        lines.append(f"  {icon} {v['test_type']}: {v['message']}")
                return "\n".join(lines)
            else:
                lines = [f"❌ {result.get('message', 'Failed')}"]
                if result.get("errors"):
                    lines.append("\nErrors:")
                    for err in result["errors"]:
                        lines.append(f"  • [{err['field']}] {err['issue']}")
                        if err.get("suggestion"):
                            lines.append(f"    💡 {err['suggestion']}")
                if result.get("verification"):
                    lines.append("\nVerification results:")
                    for v in result["verification"]:
                        icon = "✅" if v.get("success") else "❌"
                        lines.append(f"  {icon} {v['test_type']}: {v['message']}")
                if result.get("hint"):
                    lines.append(f"\n💡 {result['hint']}")
                return "\n".join(lines)
        return str(result)

    # ==================== Discovery ====================

    @register_action(
        short_desc="列出配置类型",
        description="列出所有可用的配置类型。每个类型对应一个独立的配置文件。",
        param_infos={},
    )
    async def list_config_types(self) -> str:
        """List available config types."""
        try:
            cs = self._get_config_service()
            types = cs.list_config_types()
            lines = ["可用的配置类型:\n"]
            for t in types:
                lines.append(f"  • {t}")
            lines.append("\n使用 get_config_schema(type) 查看每种类型的结构")
            lines.append("使用 read_config(type, name?) 读取配置内容")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="获取配置Schema",
        description="获取指定配置类型的 JSON Schema，了解配置的合法结构和字段说明。",
        param_infos={"config_type": "配置类型：agent, llm, system, email_proxy"},
    )
    async def get_config_schema(self, config_type: str) -> str:
        """Get JSON Schema for a config type."""
        try:
            cs = self._get_config_service()
            schema = cs.get_schema(config_type)
            return yaml.dump(
                schema, allow_unicode=True, default_flow_style=False, sort_keys=False
            )
        except ValueError as e:
            return f"❌ {e}\n💡 可用类型: {', '.join(self._get_config_service().list_config_types())}"
        except Exception as e:
            return f"❌ {e}"

    # ==================== Read ====================

    @register_action(
        short_desc="读取配置内容",
        description="读取指定配置的原始内容（YAML或JSON格式）。返回的是文件的完整文本，可以直接修改后用于 write_config。",
        param_infos={
            "config_type": "配置类型：agent, llm, system, email_proxy",
            "name": "Agent名称（仅 agent 类型需要，如 'SystemAdmin'）",
        },
    )
    async def read_config(self, config_type: str, name: str = None) -> str:
        """Read config and return raw content."""
        try:
            cs = self._get_config_service()
            result = cs.read_config(config_type, name)
            if result.success:
                return result.content
            else:
                return f"❌ {result.error}"
        except Exception as e:
            return f"❌ {e}"

    # ==================== Write ====================

    @register_action(
        short_desc="写入配置（验证+测试+备份）",
        description=(
            "写入配置内容。流程：解析 → Schema验证 → 内容验证 → 连接测试 → 备份旧文件 → 写入新文件。"
            "先用 read_config 读取当前配置，修改后用此方法写入。"
            "如果只是想验证不写入，用 validate_config。"
        ),
        param_infos={
            "config_type": "配置类型：agent, llm, system, email_proxy",
            "content": "完整的配置内容（YAML或JSON格式的字符串）",
            "name": "Agent名称（仅 agent 类型需要，如 'SystemAdmin'）",
            "skip_verification": "是否跳过连接测试（true/false，默认false）",
        },
    )
    async def write_config(
        self,
        config_type: str,
        content: str,
        name: str = None,
        skip_verification: bool = False,
    ) -> str:
        """Write config: validate → verify → backup → write."""
        try:
            cs = self._get_config_service()
            result = await cs.write_config(
                config_type, content, name, skip_verification
            )
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    # ==================== Validate Only ====================

    @register_action(
        short_desc="验证配置（不写入）",
        description="验证配置内容是否合法，但不实际写入文件。用于在写入前检查配置是否正确。",
        param_infos={
            "config_type": "配置类型：agent, llm, system, email_proxy",
            "content": "要验证的配置内容（YAML或JSON格式的字符串）",
            "name": "Agent名称（仅 agent 类型需要）",
        },
    )
    async def validate_config(
        self, config_type: str, content: str, name: str = None
    ) -> str:
        """Validate config without writing."""
        try:
            cs = self._get_config_service()
            result = cs.validate_config(config_type, content, name)
            if result.success:
                msg = f"✅ {result.message}"
                if result.parsed_content:
                    msg += f"\nParsed successfully: {len(str(result.parsed_content))} chars"
                return msg
            else:
                lines = [f"❌ {result.message}"]
                for err in result.errors:
                    lines.append(f"  • [{err.field}] {err.issue}")
                    if err.suggestion:
                        lines.append(f"    💡 {err.suggestion}")
                return "\n".join(lines)
        except Exception as e:
            return f"❌ {e}"

    # ==================== Backup ====================

    @register_action(
        short_desc="列出备份",
        description="列出指定配置类型的所有可用备份。备份按时间倒序排列，最新的在前面。",
        param_infos={
            "config_type": "配置类型：agent, llm, system, email_proxy",
            "name": "Agent名称（仅 agent 类型需要）",
        },
    )
    async def list_backups(self, config_type: str, name: str = None) -> str:
        """List available backups."""
        try:
            cs = self._get_config_service()
            backups = cs.list_backups(config_type, name)
            if not backups:
                return f"No backups found for {config_type}" + (
                    f" ({name})" if name else ""
                )

            lines = [
                f"Backups for {config_type}"
                + (f" ({name})" if name else "")
                + f" (total {len(backups)}):\n"
            ]
            for b in backups:
                lines.append(f"  • {b.name} ({b.size} bytes, {b.modified})")
            lines.append("\n使用 read_backup(config_type, backup_name) 查看备份内容")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="读取备份内容",
        description="读取指定备份文件的原始内容。",
        param_infos={
            "config_type": "配置类型：agent, llm, system, email_proxy",
            "backup_name": "备份文件名（如 'SystemAdmin_20260324_120000.yml'）",
            "name": "Agent名称（仅 agent 类型需要，用于定位备份目录）",
        },
    )
    async def read_backup(
        self, config_type: str, backup_name: str, name: str = None
    ) -> str:
        """Read a specific backup file."""
        try:
            cs = self._get_config_service()
            content = cs.read_backup(config_type, backup_name, name)
            return content
        except FileNotFoundError as e:
            # List available backups as hint
            backups = cs.list_backups(config_type, name)
            hint = (
                f"\nAvailable backups: {[b.name for b in backups[:5]]}"
                if backups
                else ""
            )
            return f"❌ {e}{hint}"
        except Exception as e:
            return f"❌ {e}"

    # ==================== Agent Lifecycle ====================

    @register_action(
        short_desc="列出所有Agent",
        description="列出系统中当前运行的所有Agent及其状态。",
        param_infos={},
    )
    async def list_agents(self) -> str:
        """List all running agents."""
        try:
            runtime = self.root_agent.runtime
            if not runtime:
                return "❌ runtime not available"

            if not runtime.agents:
                return "No agents running"

            lines = [f"Running agents ({len(runtime.agents)}):\n"]
            for agent_name, agent in runtime.agents.items():
                status = "running" if not agent.is_paused else "paused"
                lines.append(f"  ** {agent_name} **")
                lines.append(
                    f"     description: {getattr(agent, 'description', 'N/A')}"
                )
                lines.append(f"     status: {status}")
                lines.append(f"     model: {getattr(agent, 'backend_model', 'N/A')}")
                skills = getattr(agent, "skills", [])
                lines.append(f"     skills: {', '.join(skills) if skills else 'none'}")
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="重载Agent",
        description="从配置文件重新加载指定的Agent。会停止当前任务并重新启动。",
        param_infos={"agent_name": "要重载的Agent名称"},
    )
    async def reload_agent(self, agent_name: str) -> str:
        """Reload agent from config file."""
        try:
            runtime = self.root_agent.runtime
            if not runtime:
                return "❌ runtime not available"

            if agent_name not in runtime.agents:
                return f"❌ Agent '{agent_name}' not found. Available: {list(runtime.agents.keys())}"

            # Pause and reload
            agent = runtime.agents[agent_name]
            await agent.pause()

            # Stop tasks
            if hasattr(agent, "email_worker_task") and agent.email_worker_task:
                agent.email_worker_task.cancel()
            if hasattr(agent, "history_worker_task") and agent.history_worker_task:
                agent.history_worker_task.cancel()

            # Reload from file
            agent_yml_path = runtime.paths.agent_config_dir / f"{agent_name}.yml"
            if not agent_yml_path.exists():
                return f"❌ Config file not found: {agent_yml_path}"

            import asyncio

            new_agent = runtime.loader.load_from_file(str(agent_yml_path))
            new_agent.async_event_callback = runtime.async_event_callback
            new_agent.runtime = runtime

            runtime.agents[agent_name] = new_agent
            runtime.post_office.register(new_agent)
            agent_task = asyncio.create_task(new_agent.run())
            runtime.running_agent_tasks.append(agent_task)
            await new_agent.resume()

            return f"✅ Agent '{agent_name}' reloaded successfully"
        except Exception as e:
            return f"❌ Reload failed: {e}"

    @register_action(
        short_desc="删除Agent",
        description="从系统中移除指定的Agent。",
        param_infos={
            "agent_name": "要删除的Agent名称",
            "delete_config": "是否同时删除配置文件（true/false，默认false）",
        },
    )
    async def delete_agent(self, agent_name: str, delete_config: bool = False) -> str:
        """Remove agent from system."""
        try:
            runtime = self.root_agent.runtime
            if not runtime:
                return "❌ runtime not available"

            if agent_name not in runtime.agents:
                return f"❌ Agent '{agent_name}' not found"

            agent = runtime.agents[agent_name]
            await agent.pause()

            if hasattr(agent, "email_worker_task") and agent.email_worker_task:
                agent.email_worker_task.cancel()
            if hasattr(agent, "history_worker_task") and agent.history_worker_task:
                agent.history_worker_task.cancel()

            del runtime.agents[agent_name]

            if delete_config:
                config_file = runtime.paths.agent_config_dir / f"{agent_name}.yml"
                if config_file.exists():
                    config_file.unlink()
                    return f"✅ Agent '{agent_name}' removed (config file deleted)"
                else:
                    return f"✅ Agent '{agent_name}' removed (config file not found)"
            else:
                return f"✅ Agent '{agent_name}' removed (config file preserved)"
        except Exception as e:
            return f"❌ Delete failed: {e}"
