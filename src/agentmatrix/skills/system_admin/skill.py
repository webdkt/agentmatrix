"""
System Admin Skill - System Configuration Management

Thin wrapper around ConfigService for system configuration operations.
Includes LLM config, Email Proxy config, System config, and system controls.
"""

from typing import Optional
from ...core.action import register_action
from ...services.config_service import ConfigService


class System_adminSkillMixin:
    """System Configuration Management - LLM, Email Proxy, System config"""

    _skill_description = (
        "系统配置管理：管理 LLM 配置（添加/删除/修改 endpoint）、"
        "邮件代理配置（启用/禁用/更新）、系统配置、配置历史。\n"
        "所有操作通过系统自动完成配置验证和备份。"
    )
    _skill_dependencies = ["base"]

    def _get_cs(self):
        """Get ConfigService instance."""
        return ConfigService(self.root_agent.runtime.paths)

    def _format_result(self, result) -> str:
        """Format a result object into LLM-friendly text."""
        if isinstance(result, dict):
            if result.get("success"):
                lines = [f"✅ {result.get('message', 'Success')}"]
                if result.get("backup_path"):
                    lines.append(f"📦 Backup: {result['backup_path']}")
                if result.get("file_path"):
                    lines.append(f"📄 File: {result['file_path']}")
                return "\n".join(lines)
            else:
                lines = [f"❌ {result.get('message', 'Failed')}"]
                if result.get("errors"):
                    lines.append("\nErrors:")
                    for err in result["errors"]:
                        lines.append(f"  • [{err['field']}] {err['issue']}")
                        if err.get("suggestion"):
                            lines.append(f"    💡 {err['suggestion']}")
                return "\n".join(lines)
        return str(result)

    # ==================== Manuals ====================

    @register_action(
        short_desc="LLM 配置格式说明",
        description="返回 LLM 配置文件的完整格式说明和示例。",
        param_infos={},
    )
    async def llm_config_manual(self) -> str:
        return """# LLM 配置格式说明 (llm_config.json)

## 格式

JSON 格式，key 是模型名称，value 是配置对象。

```json
{
  "default_llm": {
    "url": "https://api.openai.com/v1/chat/completions",
    "API_KEY": "OPENAI_API_KEY",
    "model_name": "gpt-4o"
  },
  "default_slm": {
    "url": "https://api.openai.com/v1/chat/completions",
    "API_KEY": "OPENAI_API_KEY",
    "model_name": "gpt-4o-mini"
  }
}
```

## 必需条目

- **default_slm**: 小语言模型，用于快速简单任务

## 每个条目的字段

| 字段 | 类型 | 说明 |
|------|------|------|
| url | string | API endpoint URL |
| API_KEY | string | 环境变量名（不是实际的 key）|
| model_name | string | 模型标识符 |

## 操作方法

- add_llm_endpoint(name, entry) - 添加新 endpoint
- delete_llm_endpoint(name) - 删除 endpoint（不能删除 default_llm/default_slm）
- update_llm_endpoint(name, entry) - 修改已有 endpoint
- read_llm_config() - 读取完整配置
- update_llm_config(content) - 全文更新
"""

    @register_action(
        short_desc="邮件代理配置格式说明",
        description="返回邮件代理配置文件的完整格式说明和示例。",
        param_infos={},
    )
    async def email_proxy_config_manual(self) -> str:
        return """# 邮件代理配置格式说明 (email_proxy_config.yml)

## 格式

YAML 格式。

```yaml
enabled: true
matrix_mailbox: matrix@example.com
user_mailbox: user@example.com
smtp:
  host: smtp.gmail.com
  port: 587
  user: user@example.com
  password: your-app-password
imap:
  host: imap.gmail.com
  port: 993
  user: user@example.com
  password: your-app-password
```

## 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| enabled | bool | 是否启用邮件代理 |
| matrix_mailbox | string | Matrix 系统邮箱地址 |
| user_mailbox | string/list | 用户邮箱地址 |
| smtp | dict | SMTP 配置 (host, port, user, password) |
| imap | dict | IMAP 配置 (host, port, user, password) |

## 操作方法

- read_email_proxy_config() - 读取配置
- update_email_proxy_config(content) - 全文更新
- enable_email_proxy() - 启用并启动服务
- disable_email_proxy() - 停止并禁用服务
"""

    # ==================== LLM Config ====================

    @register_action(
        short_desc="读取 LLM 配置",
        description="读取完整的 LLM 配置文件内容（JSON 格式）。",
        param_infos={},
    )
    async def read_llm_config(self) -> str:
        try:
            cs = self._get_cs()
            result = cs.read_config("llm")
            if result.success:
                return result.content
            else:
                return f"❌ {result.error}"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="更新 LLM 配置（全文）",
        description="全文更新 LLM 配置文件。建议先用 read_llm_config 读取当前配置。",
        param_infos={"content": "LLM 配置的完整 JSON 内容"},
    )
    async def update_llm_config(self, content: str) -> str:
        try:
            cs = self._get_cs()
            result = await cs.write_config("llm", content)
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="添加 LLM endpoint（name, entry_content）",
        description=(
            "添加新的 LLM endpoint。\n"
            "参数：name（endpoint 名称）, entry_content（JSON 格式的配置）\n"
            'entry_content 示例: \'{"url": "...", "API_KEY": "ENV_VAR", "model_name": "gpt-4o"}\''
        ),
        param_infos={
            "name": "Endpoint 名称",
            "entry_content": "JSON 格式的配置内容",
        },
    )
    async def add_llm_endpoint(self, name: str, entry_content: str) -> str:
        try:
            cs = self._get_cs()
            result = cs.add_llm_endpoint(name, entry_content)
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="删除 LLM endpoint（name）",
        description="删除指定的 LLM endpoint。不能删除 default_llm 和 default_slm。",
        param_infos={"name": "要删除的 Endpoint 名称"},
    )
    async def delete_llm_endpoint(self, name: str) -> str:
        try:
            cs = self._get_cs()
            result = cs.delete_llm_endpoint(name)
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="修改 LLM endpoint（name, entry_content）",
        description="修改指定 LLM endpoint 的配置。",
        param_infos={
            "name": "要修改的 Endpoint 名称",
            "entry_content": "新的 JSON 格式配置内容",
        },
    )
    async def update_llm_endpoint(self, name: str, entry_content: str) -> str:
        try:
            cs = self._get_cs()
            result = cs.update_llm_endpoint(name, entry_content)
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    # ==================== Email Proxy Config ====================

    @register_action(
        short_desc="读取邮件代理配置",
        description="读取邮件代理配置文件内容（YAML 格式）。",
        param_infos={},
    )
    async def read_email_proxy_config(self) -> str:
        try:
            cs = self._get_cs()
            result = cs.read_config("email_proxy")
            if result.success:
                return result.content
            else:
                return f"❌ {result.error}"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="更新邮件代理配置（全文）",
        description="全文更新邮件代理配置文件。建议先用 read_email_proxy_config 读取当前配置。",
        param_infos={"content": "邮件代理配置的完整 YAML 内容"},
    )
    async def update_email_proxy_config(self, content: str) -> str:
        try:
            cs = self._get_cs()
            result = await cs.write_config("email_proxy", content)
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="启用邮件代理",
        description="启用邮件代理服务。更新配置并启动服务。",
        param_infos={},
    )
    async def enable_email_proxy(self) -> str:
        try:
            cs = self._get_cs()
            return await cs.enable_email_proxy(self.root_agent.runtime)
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="禁用邮件代理",
        description="禁用邮件代理服务。停止服务并更新配置。",
        param_infos={},
    )
    async def disable_email_proxy(self) -> str:
        try:
            cs = self._get_cs()
            return await cs.disable_email_proxy(self.root_agent.runtime)
        except Exception as e:
            return f"❌ {e}"

    # ==================== System Config ====================

    @register_action(
        short_desc="读取系统配置",
        description="读取系统配置文件内容（YAML 格式）。",
        param_infos={},
    )
    async def read_system_config(self) -> str:
        try:
            cs = self._get_cs()
            result = cs.read_config("system")
            if result.success:
                return result.content
            else:
                return f"❌ {result.error}"
        except Exception as e:
            return f"❌ {e}"

    @register_action(
        short_desc="更新系统配置（content）",
        description="更新系统配置文件。",
        param_infos={"content": "系统配置的完整 YAML 内容"},
    )
    async def update_system_config(self, content: str) -> str:
        try:
            cs = self._get_cs()
            result = await cs.write_config("system", content)
            return self._format_result(result.to_dict())
        except Exception as e:
            return f"❌ {e}"

    # ==================== System Control ====================

    @register_action(
        short_desc="重启系统",
        description="重启整个系统（重新加载所有配置和 Agent）。",
        param_infos={},
    )
    async def restart_system(self) -> str:
        try:
            cs = self._get_cs()
            return await cs.restart_system(self.root_agent.runtime)
        except Exception as e:
            return f"❌ {e}"

    # ==================== Config History ====================

    @register_action(
        short_desc="列出配置历史（config_name）",
        description="列出指定配置的所有历史备份。config_name: llm, system, email_proxy",
        param_infos={"config_name": "配置名称：llm, system, email_proxy"},
    )
    async def list_config_history(self, config_name: str) -> str:
        try:
            cs = self._get_cs()
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
        short_desc="读取配置历史内容（history_name）",
        description="读取指定历史备份文件的内容。可用于回滚配置。",
        param_infos={"history_name": "历史文件名"},
    )
    async def read_config_history(self, history_name: str) -> str:
        try:
            cs = self._get_cs()
            # Try agent backup dir
            try:
                return cs.read_backup("agent", history_name)
            except FileNotFoundError:
                pass
            # Try config backup dirs
            for config_type in ["llm", "system", "email_proxy"]:
                try:
                    return cs.read_backup(config_type, history_name)
                except FileNotFoundError:
                    continue
            return f"❌ 历史文件不存在: {history_name}"
        except Exception as e:
            return f"❌ {e}"
