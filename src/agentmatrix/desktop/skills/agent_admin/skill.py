"""
Agent Admin Skill - Agent Profile Management

Delegates to AgentService for all agent operations.
"""

import yaml
from agentmatrix.core.action import register_action


class Agent_adminSkillMixin:
    """Agent Profile Management - create, read, update, delete, clone, stop, reload agents"""

    _skill_description = (
        "Agent 管理：管理 Agent Profile（创建/读取/更新/删除/克隆）、"
        "Agent 生命周期（停止/重载）、列出运行中的 Agent。"
        "所有操作通过系统自动完成配置验证和备份。"
    )
    _skill_dependencies = ["base"]

    def _svc(self):
        return self.root_agent.runtime.agent_service

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
                    if isinstance(result["errors"], list):
                        lines.append("\nErrors:")
                        for err in result["errors"]:
                            if isinstance(err, dict):
                                lines.append(f"  • [{err.get('field', '?')}] {err.get('issue', err)}")
                                if err.get("suggestion"):
                                    lines.append(f"    💡 {err['suggestion']}")
                            else:
                                lines.append(f"  • {err}")
                return "\n".join(lines)
        return str(result)

    # ==================== readme ====================

    @register_action(
        short_desc="Agent Profile 格式说明",
        description=(
            "返回 Agent Profile 的完整格式说明，包括所有字段的含义和示例。\n"
            "在创建或修改 Agent Profile 前，建议先调用此方法了解格式要求。"
        ),
        param_infos={},
    )
    async def readme_first(self) -> str:
        return """# Agent Profile 格式说明

## 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | Agent 名称，唯一标识，也是显示名 |
| description | string | 一句话描述 |

## 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| class_name | string | agentmatrix.desktop.base_agent.BaseAgent | Agent 类名 |
| backend_model | string | default_llm | LLM 模型名（需在 llm_config 中存在）|
| skills | list | [] | 技能列表，如 ["base", "email"] |
| persona | string | - | 角色定义 prompt |
| cerebellum | dict | - | 小脑配置（SLM 模型）|
| logging | dict | - | 日志配置 |

## YAML 示例

```yaml
name: MyAgent
description: 我的自定义 Agent
class_name: agentmatrix.desktop.base_agent.BaseAgent
backend_model: default_llm
skills:
  - base
  - email
persona: |
  # Role
  你是一个助手，擅长回答问题。
  
  # Output Format
  请用简洁的语言回答。
```

## 注意事项

1. **name 必须唯一** - 不能与已有 Agent 重名
2. **name 不能是 "User" 或 "用户"** - 这是保留名
3. **skills 必须存在** - 技能需在系统中已注册
4. **backend_model 必须存在** - 需在 llm_config.json 中配置
"""

    # ==================== Agent Profile CRUD ====================

    @register_action(
        short_desc="读取 Agent Profile（agent_name）",
        description="读取指定 Agent 的配置文件内容（YAML 格式）。返回完整的 YAML 配置内容。",
        param_infos={"agent_name": "Agent 的显示名（name 字段），如 'SystemAdmin'"},
    )
    async def read_agent_profile(self, agent_name: str) -> str:
        try:
            content = self._svc().read_profile_raw(agent_name)
            if content is None:
                return f"❌ Agent '{agent_name}' not found"
            return content
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="创建 Agent Profile（agent_name, content）",
        description=(
            "创建一个新的 Agent Profile 配置文件。\n"
            "参数：agent_name（Agent 名称）, content（完整的 YAML 配置内容）\n"
            "创建前会自动验证格式和依赖，检查名称是否已存在。"
        ),
        param_infos={
            "agent_name": "Agent 名称，如 'MyNewAgent'",
            "content": "Agent Profile 的完整 YAML 内容",
        },
    )
    async def create_agent_profile(self, agent_name: str, content: str) -> str:
        try:
            profile = yaml.safe_load(content) or {}
            await self._svc().create_agent(agent_name, profile)
            return (
                f"✅ Agent '{agent_name}' created and registered successfully"
                "\n\n💡 配置文件已创建，Agent 已加载到运行时。"
            )
        except FileExistsError as e:
            return f"❌ {e}"
        except ValueError as e:
            return f"❌ {e}"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="更新 Agent Profile（agent_name, content）",
        description="更新现有 Agent 的配置文件并热重载。建议先用 read_agent_profile 读取当前配置，修改后再调用此方法。",
        param_infos={
            "agent_name": "Agent 的显示名（name 字段）",
            "content": "Agent Profile 的完整 YAML 内容",
        },
    )
    async def update_agent_profile(self, agent_name: str, content: str) -> str:
        try:
            profile = yaml.safe_load(content) or {}
            await self._svc().update_agent(agent_name, profile)
            return f"✅ Agent '{agent_name}' updated and reloaded successfully"
        except ValueError as e:
            return f"❌ {e}"
        except FileNotFoundError as e:
            return f"❌ {e}"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="删除 Agent（agent_name, delete_config=false）",
        description="停止 Agent、从运行时移除，并删除配置文件。高风险操作。",
        param_infos={
            "agent_name": "要删除的 Agent 名称",
            "delete_config": "是否同时删除配置文件（true/false，默认 true）",
        },
    )
    async def delete_agent(self, agent_name: str, delete_config: bool = True) -> str:
        try:
            runtime = self.root_agent.runtime
            if agent_name not in runtime.agents:
                return f"❌ Agent '{agent_name}' not found"
            if agent_name == runtime.user_agent_name:
                return f"❌ Cannot delete User agent"

            await self._svc().delete_agent(agent_name)

            msg = f"✅ Agent '{agent_name}' 已删除"
            if not delete_config:
                msg += "（配置文件保留）"
            return msg
        except ValueError as e:
            return f"❌ {e}"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="克隆 Agent（from_agent, new_agent_name）",
        description="完全复制一个 Agent 的 profile，使用不同的名字，并加载到运行时。",
        param_infos={
            "from_agent": "源 Agent 名称",
            "new_agent_name": "新 Agent 名称",
        },
    )
    async def clone_agent(self, from_agent: str, new_agent_name: str) -> str:
        try:
            await self._svc().clone_agent(from_agent, new_agent_name)
            return f"✅ Agent '{new_agent_name}' cloned from '{from_agent}' and loaded into runtime"
        except (ValueError, FileNotFoundError) as e:
            return f"❌ {e}"
        except Exception as e:
            return f"❌ {e}"

    # ==================== Agent Lifecycle ====================

    @register_action(
        short_desc="停止 Agent（agent_name）",
        description="暂停 Agent 并从运行时移除。Agent 的配置文件保留。",
        param_infos={"agent_name": "要停止的 Agent 名称"},
    )
    async def stop_agent(self, agent_name: str) -> str:
        try:
            await self._svc().stop_agent(agent_name)
            return f"✅ Agent '{agent_name}' 的当前执行已中止"
        except ValueError as e:
            return f"❌ {e}"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="重载 Agent（agent_name）",
        description="从配置文件重新加载指定的 Agent。会停止当前任务并重新启动。",
        param_infos={"agent_name": "要重载的 Agent 名称"},
    )
    async def reload_agent(self, agent_name: str) -> str:
        try:
            await self._svc().reload_agent(agent_name)
            return f"✅ Agent '{agent_name}' reloaded successfully"
        except (ValueError, FileNotFoundError) as e:
            return f"❌ {e}"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="列出所有运行中的 Agent",
        description="列出系统中当前运行的所有 Agent 及其状态、技能、模型等信息。",
        param_infos={},
    )
    async def list_agents(self) -> str:
        try:
            agents = self._svc().list_running_agents()
            if not agents:
                return "No agents running"

            lines = [f"Running agents ({len(agents)}):\n"]
            for info in agents:
                lines.append(f"  ** {info.name} **")
                lines.append(f"     description: {info.description}")
                lines.append(f"     status: {info.status}")
                lines.append(f"     model: {info.backend_model}")
                skills = info.skills or []
                lines.append(f"     skills: {', '.join(skills) if skills else 'none'}")
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            return f"❌ {e}"

    # ==================== Config History ====================

    @register_action(
        short_desc="列出 Agent Profile 历史（agent_name）",
        description="列出指定 Agent 的所有配置历史备份。",
        param_infos={"agent_name": "Agent 的显示名（name 字段）"},
    )
    async def list_agent_profile_history(self, agent_name: str) -> str:
        try:
            backups = self._svc().list_backups(agent_name)
            if not backups:
                return f"No history found for agent '{agent_name}'"

            lines = [f"Agent '{agent_name}' 配置历史（共 {len(backups)} 条）:\n"]
            for b in backups:
                lines.append(f"  • {b}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ {e}"