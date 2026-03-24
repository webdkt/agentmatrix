"""
Matrix Admin Skill - AgentMatrix System Configuration

Content-first approach:
- read_agent_profile: return raw YAML content
- update_agent_profile: accept raw content, validate, verify, backup, write
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
        "系统配置管理：管理 Agent Profile（创建/读取/更新/删除）、系统配置（LLM、邮件代理等）。"
        "所有配置操作都通过此技能完成，系统会自动进行配置备份和验证，无需手工备份。"
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

    # ==================== Agent Profile ====================

    @register_action(
        short_desc="读取 Agent Profile",
        description=(
            "读取指定 Agent 的配置文件内容（YAML 格式）。\n"
            "参数：agent_name - Agent 的显示名（name 字段的值），如 'SystemAdmin', 'John'\n"
            "返回：完整的 YAML 配置内容，可直接修改后用于 update_agent_profile\n"
            "\n"
            "Agent Profile YAML 格式：\n"
            "  name: Agent名称（必填，这是显示名和邮箱地址）\n"
            "  description: 一句话描述（必填）\n"
            "  class_name: 类名（可选，默认 agentmatrix.agents.base.BaseAgent）\n"
            "  backend_model: LLM模型名（可选，默认 default_llm，需在 llm_config 中存在）\n"
            '  skills: 技能列表（可选），如 ["base", "email"]\n'
            "  persona: 角色定义 prompt（可选），直接是字符串\n"
            "  logging: 日志配置（可选）"
        ),
        param_infos={
            "agent_name": "Agent 的显示名（name 字段），如 'SystemAdmin', 'John'"
        },
    )
    async def read_agent_profile(self, agent_name: str) -> str:
        try:
            cs = self._get_config_service()
            result = cs.read_agent_config(agent_name)
            if result.success:
                return result.content
            else:
                return f"❌ {result.error}"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="创建 Agent Profile",
        description=(
            "创建一个新的 Agent Profile 配置文件。\n"
            "参数：\n"
            "  - file_name: 配置文件名（不含 .yml 后缀），如 'MyNewAgent'\n"
            "  - content: Agent Profile 的完整 YAML 内容\n"
            "创建前会自动验证格式和依赖。\n"
            "\n"
            "Agent Profile YAML 示例：\n"
            "  name: MyAgent\n"
            "  description: 我的自定义 Agent\n"
            "  skills:\n"
            "    - base\n"
            "    - email\n"
            "  persona: |\n"
            "    # Role\n"
            "    你是一个助手...\n"
            "\n"
            "注意：file_name 是文件名，name 是 Agent 的显示名。通常相同，但可以不同。"
        ),
        param_infos={
            "file_name": "配置文件名（不含 .yml 后缀），如 'MyNewAgent'",
            "content": "Agent Profile 的完整 YAML 内容",
        },
    )
    async def create_agent_profile(self, file_name: str, content: str) -> str:
        try:
            cs = self._get_config_service()
            existing = cs.read_config("agent", file_name)
            if existing.success:
                return f"❌ 配置文件 '{file_name}.yml' 已存在。"

            result = await cs.write_config("agent", content, file_name)
            if result.success:
                return (
                    self._format_result(result.to_dict())
                    + "\n\n💡 配置文件已创建。需要重启系统或调用 reload_agent 来加载新 Agent。"
                )
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="更新 Agent Profile",
        description=(
            "更新现有 Agent 的配置文件。\n"
            "参数：\n"
            "  - agent_name: Agent 的显示名（name 字段），如 'SystemAdmin', 'John'\n"
            "  - content: Agent Profile 的完整 YAML 内容\n"
            "建议先用 read_agent_profile 读取当前配置，修改后再调用此方法。\n"
            "更新前会自动备份旧配置，自动验证格式。\n"
            "\n"
            "Agent Profile YAML 格式：\n"
            "  name: Agent名称\n"
            "  description: 一句话描述\n"
            "  class_name: 类名（默认 BaseAgent）\n"
            "  backend_model: LLM模型名（默认 default_llm）\n"
            '  skills: 技能列表，如 ["base", "email"]\n'
            "  persona: 角色定义 prompt（直接是字符串）"
        ),
        param_infos={
            "agent_name": "Agent 的显示名（name 字段），如 'SystemAdmin', 'John'",
            "content": "Agent Profile 的完整 YAML 内容",
        },
    )
    async def update_agent_profile(self, agent_name: str, content: str) -> str:
        try:
            cs = self._get_config_service()
            result = await cs.write_agent_config(agent_name, content)
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="删除 Agent",
        description=(
            "从运行时移除 Agent，可选是否同时删除配置文件。\n"
            "参数：\n"
            "  - agent_name: Agent 名称\n"
            "  - delete_config: 是否同时删除配置文件（默认 false）\n"
            "高风险操作，会先暂停 Agent 再删除。"
        ),
        param_infos={
            "agent_name": "要删除的 Agent 名称",
            "delete_config": "是否同时删除配置文件（true/false，默认 false）",
        },
    )
    async def delete_agent(self, agent_name: str, delete_config: bool = False) -> str:
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
                    return f"✅ Agent '{agent_name}' 已删除（配置文件已删除）"
                else:
                    return f"✅ Agent '{agent_name}' 已删除（配置文件不存在）"
            else:
                return f"✅ Agent '{agent_name}' 已删除（配置文件保留）"
        except Exception as e:
            return f"❌ Delete failed: {e}"

    # ==================== System Config ====================

    @register_action(
        short_desc="读取系统配置",
        description=(
            "读取系统配置文件内容。\n"
            "参数：config_name - 配置名称：llm, system, email_proxy\n"
            "返回：完整的配置内容（YAML 或 JSON 格式）\n"
            "\n"
            "配置说明：\n"
            "  - llm: LLM 模型配置（JSON 格式）\n"
            '    格式：{"model_name": {"url": "...", "API_KEY": "ENV_VAR", "model_name": "gpt-4o"}}\n'
            "    必须包含 default_slm 条目\n"
            "  - system: 系统配置（YAML 格式）\n"
            "    字段：user_agent_name, matrix_version, description, timezone\n"
            "  - email_proxy: 邮件代理配置（YAML 格式）\n"
            "    字段：enabled, matrix_mailbox, user_mailbox, smtp, imap"
        ),
        param_infos={"config_name": "配置名称：llm, system, email_proxy"},
    )
    async def read_config(self, config_name: str) -> str:
        try:
            cs = self._get_config_service()
            result = cs.read_config(config_name)
            if result.success:
                return result.content
            else:
                return f"❌ {result.error}\n💡 可用配置: llm, system, email_proxy"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="更新系统配置",
        description=(
            "更新系统配置文件。\n"
            "参数：\n"
            "  - config_name: 配置名称：llm, system, email_proxy\n"
            "  - content: 配置文件的完整内容（YAML 或 JSON 格式）\n"
            "建议先用 read_config 读取当前配置，修改后再调用此方法。\n"
            "更新前会自动备份旧配置，自动验证格式和连接。\n"
            "\n"
            "email_proxy 配置格式（YAML）：\n"
            "  enabled: true\n"
            "  matrix_mailbox: matrix@example.com\n"
            "  user_mailbox: user@example.com\n"
            "  smtp:\n"
            "    host: smtp.example.com\n"
            "    port: 587\n"
            "    user: user@example.com\n"
            "    password: your-password\n"
            "  imap:\n"
            "    host: imap.example.com\n"
            "    port: 993\n"
            "    user: user@example.com\n"
            "    password: your-password\n"
            "\n"
            "system 配置格式（YAML）：\n"
            "  user_agent_name: User\n"
            '  matrix_version: "1.0.0"\n'
            "  description: My System\n"
            "  timezone: Asia/Shanghai\n"
            "\n"
            "llm 配置格式（JSON）：\n"
            '  {"default_llm": {"url": "...", "API_KEY": "ENV_VAR", "model_name": "gpt-4o"},\n'
            '   "default_slm": {"url": "...", "API_KEY": "ENV_VAR", "model_name": "gpt-4o-mini"}}'
        ),
        param_infos={
            "config_name": "配置名称：llm, system, email_proxy",
            "content": "配置文件的完整内容（YAML 或 JSON 格式）",
        },
    )
    async def update_config(self, config_name: str, content: str) -> str:
        try:
            cs = self._get_config_service()
            result = await cs.write_config(config_name, content)
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    # ==================== Config History ====================

    @register_action(
        short_desc="列出配置历史",
        description=(
            "列出指定配置的所有历史备份。按时间倒序排列，最新的在前面。\n"
            "参数：config_name - 配置名称：llm, system, email_proxy\n"
            "Agent Profile 备份请使用 list_agent_profile_history。"
        ),
        param_infos={"config_name": "配置名称：llm, system, email_proxy"},
    )
    async def list_config_history(self, config_name: str) -> str:
        try:
            cs = self._get_config_service()
            backups = cs.list_backups(config_name)
            if not backups:
                return f"No history found for {config_name}"

            lines = [f"配置历史 {config_name}（共 {len(backups)} 条）:\n"]
            for b in backups:
                lines.append(f"  • {b.name} ({b.size} bytes, {b.modified})")
            lines.append("\n使用 read_config_history(history_name) 查看历史内容")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="列出 Agent Profile 历史",
        description=(
            "列出指定 Agent 的所有配置历史备份。\n"
            "参数：agent_name - Agent 的显示名（name 字段）\n"
            "用于回滚 Agent 配置。"
        ),
        param_infos={
            "agent_name": "Agent 的显示名（name 字段），如 'SystemAdmin', 'John'"
        },
    )
    async def list_agent_profile_history(self, agent_name: str) -> str:
        try:
            cs = self._get_config_service()
            backups = cs.list_agent_backups(agent_name)
            if not backups:
                return f"No history found for agent '{agent_name}'"

            lines = [f"Agent '{agent_name}' 配置历史（共 {len(backups)} 条）:\n"]
            for b in backups:
                lines.append(f"  • {b.name} ({b.size} bytes, {b.modified})")
            lines.append(
                f"\n使用 read_config_history('{backups[0].name}') 查看历史内容"
            )
            return "\n".join(lines)
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="读取配置历史内容",
        description=(
            "读取指定历史备份文件的内容。可用于回滚配置。\n"
            "参数：history_name - 历史文件名\n"
            "回滚流程：\n"
            "  1. list_config_history 或 list_agent_profile_history 获取历史文件名\n"
            "  2. read_config_history(history_name) 读取历史内容\n"
            "  3. update_config 或 update_agent_profile 恢复配置"
        ),
        param_infos={
            "history_name": "历史文件名，如 'llm_config_20260324_120000.json'"
        },
    )
    async def read_config_history(self, history_name: str) -> str:
        try:
            cs = self._get_config_service()
            # 尝试从 agent 备份目录读取
            try:
                content = cs.read_backup("agent", history_name)
                return content
            except FileNotFoundError:
                pass

            # 尝试从通用备份目录读取
            for config_type in ["llm", "system", "email_proxy"]:
                try:
                    content = cs.read_backup(config_type, history_name)
                    return content
                except FileNotFoundError:
                    continue

            return f"❌ 历史文件不存在: {history_name}"
        except Exception as e:
            return f"❌ {e}"

    # ==================== Agent Lifecycle ====================

    @register_action(
        short_desc="列出所有运行中的 Agent",
        description="列出系统中当前运行的所有 Agent 及其状态、技能、模型等信息。",
        param_infos={},
    )
    async def list_agents(self) -> str:
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
        short_desc="重载 Agent",
        description=(
            "从配置文件重新加载指定的 Agent。会停止当前任务并重新启动。\n"
            "参数：agent_name - 要重载的 Agent 名称\n"
            "用于配置更新后立即生效。"
        ),
        param_infos={"agent_name": "要重载的 Agent 名称"},
    )
    async def reload_agent(self, agent_name: str) -> str:
        try:
            runtime = self.root_agent.runtime
            if not runtime:
                return "❌ runtime not available"

            if agent_name not in runtime.agents:
                return f"❌ Agent '{agent_name}' not found. Available: {list(runtime.agents.keys())}"

            agent = runtime.agents[agent_name]
            await agent.pause()

            if hasattr(agent, "email_worker_task") and agent.email_worker_task:
                agent.email_worker_task.cancel()
            if hasattr(agent, "history_worker_task") and agent.history_worker_task:
                agent.history_worker_task.cancel()

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
