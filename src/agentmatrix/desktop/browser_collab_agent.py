"""
BrowserCollabAgent — 支持浏览器内嵌聊天的 Agent。

继承 BaseAgent，自动将状态更新和事件输出转发到浏览器前端。
浏览器中的聊天组件可以实时显示 Agent 状态和输出，用户也可以直接在浏览器中输入。

使用方式：
    class MyAgent(BrowserCollabAgent):
        ...
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional

from .base_agent import BaseAgent
from .signals import BrowserSignal

from ..core.signals import CoreEvent

logger = logging.getLogger(__name__)

# ── Automation spec tag pattern for message-level injection ──

_AUTOMATION_SPEC_RE = re.compile(r'<automation-spec>.*?</automation-spec>\n*', re.DOTALL)


# ==========================================
# Automation Spec Loader
# ==========================================

class _AutomationSpecLoader:
    """加载自动化系统/流程知识。

    读取 ~/automation_knowledge/{system_name}/ 下的 readme.md 和流程子目录。
    """

    def __init__(self, agent_name: str, home_dir: str, agent):
        self.agent_name = agent_name
        self.home_dir = home_dir
        self.agent = agent  # BrowserCollabAgent 实例，读写 _loaded_system_name 等

    def load(self) -> str:
        """生成 agent 主动加载的自动化知识内容（不含 tag 包裹）。"""
        system_name = getattr(self.agent, '_loaded_system_name', None)
        process_name = getattr(self.agent, '_loaded_process_name', None)

        if not system_name:
            return ""

        base_dir = os.path.join(self.home_dir, "automation_knowledge", system_name)
        if not os.path.isdir(base_dir):
            return ""

        if process_name:
            return self._build_process_section(system_name, process_name, base_dir)

        # System-only loading
        lines = [
            f"已加载：{system_name}",
            "",
        ]
        readme_path = os.path.join(base_dir, "readme.md")
        content = self._read_file_lines(readme_path, 500)
        if content:
            lines.append(content)
            if self._file_has_more(readme_path, 500):
                lines.append("(read more from readme.md)")

        # List process subdirectories
        subdirs = sorted(
            d for d in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, d))
            and not d.startswith('.') and d != 'scripts'
        )
        if subdirs:
            lines.append("")
            lines.append("# Automation Processes")
            for d in subdirs:
                lines.append(f"- {d}")
            lines.append("")
            lines.append("To load a specific process, call load_spec(system_name, process_name)")

        return "\n".join(lines)

    def _build_process_section(self, system_name: str, process_name: str,
                                base_dir: str) -> str:
        """生成具体自动化流程的知识注入内容。"""
        process_dir = os.path.join(base_dir, process_name)

        if not os.path.isdir(process_dir):
            return (f"已加载: {system_name}\n\n"
                    f"⚠️ 流程目录不存在: {process_name}")

        lines = [
            f"已加载: {system_name}",
            f"Automation Process: {process_name}",
            "",
        ]

        # Process readme
        readme_path = os.path.join(process_dir, "readme.md")
        content = self._read_file_lines(readme_path, 500)
        if content:
            lines.append(content)
            if self._file_has_more(readme_path, 500):
                lines.append("(read more from readme.md)")
            lines.append("")

        # List steps
        steps = self._list_process_steps(process_dir)
        if steps:
            lines.append("Process has following steps:")
            for i, (step_name, has_script) in enumerate(steps, 1):
                suffix = " (script exists)" if has_script else ""
                lines.append(f" {i}. {step_name}{suffix}")

        return "\n".join(lines)

    def _list_process_steps(self, process_dir: str) -> list:
        """列出流程目录中的步骤，返回 [(step_name, has_script), ...]。"""
        step_pattern = re.compile(r'^step-(\d+)-(.+)\.md$', re.IGNORECASE)
        steps = []

        if not os.path.isdir(process_dir):
            return steps

        for filename in sorted(os.listdir(process_dir)):
            m = step_pattern.match(filename)
            if m:
                step_name = m.group(2)
                py_file = f"step-{m.group(1)}-{step_name}.py"
                has_script = os.path.isfile(os.path.join(process_dir, py_file))
                steps.append((step_name, has_script))

        return steps

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def set_current(self, system_name: str, process_name: str = None) -> str:
        """LLM 调用 load_spec 时设置当前系统和可选的流程。"""
        base_dir = os.path.join(self.home_dir, "automation_knowledge", system_name)
        if not os.path.isdir(base_dir):
            return json.dumps({"error": f"未找到自动化系统: {system_name}"})

        if process_name:
            process_dir = os.path.join(base_dir, process_name)
            if not os.path.isdir(process_dir):
                return json.dumps({"error": f"流程目录不存在: {process_name}"})

        self.agent._loaded_system_name = system_name
        self.agent._loaded_process_name = process_name if process_name else None

        # Persist to session metadata
        self._sync_session_metadata()

        result = {"status": "ok", "system_name": system_name}
        if process_name:
            result["process_name"] = process_name
        return json.dumps(result, ensure_ascii=False)

    def _sync_session_metadata(self):
        """将当前加载状态同步到 session metadata 以便持久化。"""
        session = getattr(self.agent, 'current_session', None)
        if session:
            metadata = session.setdefault("metadata", {})
            metadata["sk_system_name"] = self.agent._loaded_system_name
            metadata["sk_process_name"] = self.agent._loaded_process_name

    # ------------------------------------------------------------------
    # 内部 helpers
    # ------------------------------------------------------------------

    def _read_file_lines(self, path: str, max_lines: int) -> str:
        """读文件前 max_lines 行，返回文本。"""
        if not os.path.isfile(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                result_lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    result_lines.append(line.rstrip())
                return "\n".join(result_lines)
        except Exception as e:
            logger.warning(f"[AutomationSpec] Failed to read {path}: {e}")
            return ""

    def _file_has_more(self, path: str, threshold: int) -> bool:
        """检查文件是否超过 threshold 行。"""
        if not os.path.isfile(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                for i, _ in enumerate(f):
                    if i >= threshold:
                        return True
            return False
        except Exception:
            return False


class BrowserCollabAgent(BaseAgent):
    """支持浏览器协作的 Agent。

    在 BaseAgent 基础上，提供：
    - 通过 CDP 触发浏览器内的 indicator（十字准星）和 range selector（范围选择器）
    - 自动解析 BrowserSignal 的 session
    - 自动确保 CDP 浏览器基础设施就绪
    - Automation spec 通过 <automation-spec> tag 注入到 user message 上下文

    浏览器端通过 __bh_emit__ 发送事件（indicator_result, range_result 等），
    Agent 通过 CDP 调用 __bh_show_indicator__ / __bh_show_range__ 触发交互。

    使用 BaseAgent 的 session_type='local'（默认）直接操作宿主机文件。
    """

    # Automation spec：跨 execute 保持，load_spec action 设置
    _loaded_system_name: str = None
    _loaded_process_name: str = None

    # Exit status check: skip if no actions executed since last check
    _actions_executed_since_status_check: bool = False

    # ==========================================
    # Automation Spec 静态工具方法
    # ==========================================

    @staticmethod
    def _purge_spec_from_messages(messages):
        """从消息历史中移除所有 <automation-spec> 块。"""
        for msg in messages:
            c = msg.get("content")
            if isinstance(c, str):
                msg["content"] = _AUTOMATION_SPEC_RE.sub('', c).strip()

    @staticmethod
    def _extract_current_spec(messages):
        """从消息历史中提取最新的 <automation-spec> 内容块（含 tag）。"""
        pattern = re.compile(r'<automation-spec>.*?</automation-spec>', re.DOTALL)
        for msg in reversed(messages):
            c = msg.get("content", "")
            if isinstance(c, str):
                match = pattern.search(c)
                if match:
                    return match.group(0)
        return None

    @staticmethod
    def _inject_spec_to_first_user_msg(messages, spec_content):
        """将 spec 内容注入到第一条 user message 的开头。"""
        for msg in messages:
            if msg.get("role") == "user":
                msg["content"] = f"{spec_content}\n\n{msg['content']}"
                return True
        return False

    # ==========================================
    # BaseAgent overrides
    # ==========================================

    async def _route_signal(self, signal):
        """BrowserSignal 处理：过滤 orphan 信号。"""
        if isinstance(signal, BrowserSignal):
            session_id = signal.agent_session_id
            if not session_id:
                if self.current_session:
                    signal.agent_session_id = self.current_session["session_id"]
                else:
                    return  # 无 session context，丢弃 orphan 信号

        await super()._route_signal(signal)

    async def _resolve_session(self, signal) -> dict:
        """BrowserSignal 由本类处理，其余委托 BaseAgent。"""
        if isinstance(signal, BrowserSignal):
            return await self._resolve_browser_session(signal)
        return await super()._resolve_session(signal)

    async def _resolve_browser_session(self, signal: BrowserSignal) -> dict:
        """BrowserSignal → 从前端元数据解析 session。"""
        session_id = signal.agent_session_id
        if not session_id:
            # Tab 还没有 agent 元数据（如刚打开的 orphan tab），
            # 回退到当前 session
            if self.current_session:
                signal.agent_session_id = self.current_session["session_id"]
                signal._desktop_resolved = True
                signal._resolved_session = self.current_session
                return self.current_session
            raise ValueError(
                f"BrowserSignal ({signal.event_type}) has no agent_session_id "
                f"and no current session"
            )

        session = await self.session_manager.get_session_by_id(session_id)

        # 标记已解析（避免 waiting_signals 重路由时重复处理）
        signal._desktop_resolved = True
        signal._resolved_session = session

        return session

    async def _on_activate_session(self, session: dict, first_signal=None):
        """Session 激活时自动确保 CDP 浏览器基础设施就绪。

        对 Agent 完全透明：无需手动调用 open_browser，
        CDP 连接、tab 恢复、agent queue 注册全部自动完成。
        """
        await super()._on_activate_session(session, first_signal)

        # 明确切换到不同 session 时，恢复 automation spec 状态
        session_id = session["session_id"]
        if self._last_deactivated_session_id != session_id:
            metadata = session.get("metadata", {})
            self._loaded_system_name = metadata.get("sk_system_name") or metadata.get("sk_site_key")
            self._loaded_process_name = metadata.get("sk_process_name") or metadata.get("sk_process_dir")
            from .skills.browser_automation._shared import _agent_env_callbacks
            _agent_env_callbacks.pop(self.name, None)

        # Reset action tracking for exit status check
        self._actions_executed_since_status_check = False
        try:
            if self.active_micro_agent and hasattr(self.active_micro_agent, '_ensure_browser'):
                await self.active_micro_agent._ensure_browser()
        except Exception as e:
            logger.warning(f"Auto CDP init failed (will retry in actions): {e}")

    def _start_session_task(self, session: dict):
        """Override: reset action tracking for exit status check."""
        self._actions_executed_since_status_check = False
        super()._start_session_task(session)

    def _create_micro_agent(self):
        """创建 MicroAgent，设置 automation spec loader。"""
        # 如果之前设置过 work mode，用对应的 persona
        mode = getattr(self, '_current_work_mode', None)
        if mode:
            mode_content = self.profile.get(f"{mode}_mode")
            if mode_content:
                self.persona = mode_content

        home_dir = self.runtime.paths.get_agent_home_dir(self.name)
        spec_loader = _AutomationSpecLoader(self.name, home_dir, self)

        micro = super()._create_micro_agent()
        micro._automation_spec_loader = spec_loader
        micro._before_action_hook = self._on_before_action
        micro._after_action_hook = self._on_after_action

        return micro

    async def _on_before_action(self, action_name: str, params: dict):
        """Called before each micro agent action executes. Return False to skip."""
        pass

    async def _on_after_action(self, action_name: str, params: dict, result):
        """Called after each micro agent action completes."""
        self._actions_executed_since_status_check = True
        readme_dir = self._detect_readme_write(action_name, params)
        if readme_dir:
            asyncio.create_task(self._update_meta_yml(readme_dir))

    def _detect_readme_write(self, action_name: str, params: dict) -> str | None:
        """Check if action wrote to a README in the current system/process dir.
        Returns the directory path containing the README, or None."""
        session = self.current_session
        if not session:
            return None
        metadata = session.get("metadata", {})
        system_name = metadata.get("sk_system_name")
        process_name = metadata.get("sk_process_name")
        if not system_name:
            return None

        root = f"{self.runtime.paths.workspace_dir}/agent_files/{self.name}/home/automation_knowledge"
        system_dir = f"{root}/{system_name}"
        process_dir = f"{root}/{system_name}/{process_name}" if process_name else None

        target_path = None

        if action_name in ("file.write", "write"):
            target_path = params.get("file_path", "")

        elif action_name in ("file.bash", "bash"):
            # Extract file from first line redirect: echo/cat/tee ... > file
            first_line = (params.get("command") or "").split("\n")[0]
            m = re.search(r'>\s*(\S+)', first_line)
            if m:
                target_path = m.group(1)

        if not target_path:
            return None

        target_lower = target_path.lower()
        if not (target_lower.endswith("/readme.md") or target_lower == "readme.md"):
            return None

        # Normalize: resolve relative paths against system dir
        if not target_path.startswith("/"):
            target_path = f"{system_dir}/{target_path}"

        # Determine which directory this readme belongs to
        target_dir = target_path.rsplit("/", 1)[0]
        if process_dir and target_dir == process_dir:
            return process_dir
        if target_dir == system_dir:
            return system_dir
        return None

    @staticmethod
    def _parse_meta_response(raw: str) -> dict:
        """Parser for think_with_retry: extract JSON with required fields."""
        # Find first {...} block in the response
        m = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if not m:
            raise ValueError("No JSON object found in response")
        data = json.loads(m.group())
        for key in ("display_name", "description", "icon"):
            if key not in data or not data[key]:
                raise ValueError(f"Missing required key: {key}")
        return {
            "display_name": str(data["display_name"])[:30],
            "description": str(data["description"])[:80],
            "icon": str(data["icon"]),
        }

    async def _update_meta_yml(self, target_dir: str):
        """Read README in target_dir, use cerebellum to generate/update meta.yml."""
        from pathlib import Path
        try:
            readme_path = Path(target_dir) / "readme.md"
            if not readme_path.exists():
                readme_path = Path(target_dir) / "README.md"
            if not readme_path.exists():
                return

            content = readme_path.read_text(encoding="utf-8")
            if not content.strip():
                return

            prompt = (
                "Based on the following README, generate a short metadata summary.\n"
                "Return a JSON object with these keys:\n"
                '- "display_name": a concise display name (max 30 chars)\n'
                '- "description": a one-line description (max 80 chars)\n'
                '- "icon": an icon name from Lucide Icons (lucide.dev)\n\n'
                f"[README content]\n{content[:3000]}"
            )

            result = await self.cerebellum.backend.think_with_retry(
                prompt, self._parse_meta_response
            )
            if not result:
                return

            # Write as YAML for meta.yml format
            import yaml
            meta_path = Path(target_dir) / "meta.yml"
            meta_path.write_text(yaml.dump(result, allow_unicode=True, default_flow_style=False), encoding="utf-8")
            logger.info(f"Auto-generated meta.yml for {target_dir}")

        except Exception as e:
            logger.warning(f"Failed to auto-update meta.yml for {target_dir}: {e}")

    # ==========================================
    # 消息压缩保护
    # ==========================================

    async def compress_messages(self, agent) -> None:
        """压缩消息时，保护 automation spec 内容。

        1. 提取当前 <automation-spec> 内容块
        2. 清除 <automation-spec> 块（节省压缩 token）
        3. 调用父类压缩
        4. 将 spec 重新注入到压缩后的第一条 user message
        """
        # 1. 提取当前 spec（压缩前）
        current_spec = self._extract_current_spec(agent.messages)

        # 2. 清除 spec 块（压缩前，避免 LLM 混淆）
        for msg in agent.messages:
            c = msg.get("content")
            if isinstance(c, str):
                c = _AUTOMATION_SPEC_RE.sub('[自动化流程知识已加载]', c)
                msg["content"] = c

        # 3. 调用父类压缩
        await super().compress_messages(agent)

        # 4. 压缩后将 spec 重新注入到第一条 user message
        if current_spec:
            self._inject_spec_to_first_user_msg(agent.messages, current_spec)

    async def generate_working_notes(self, messages, focus_hint=""):
        """生成 Working Notes 时，告知 LLM 不需详细记录 spec 内容。"""
        # 替换 spec 内容为简短占位（节省 token）
        working_copy = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                cleaned = _AUTOMATION_SPEC_RE.sub('[自动化流程知识已加载]', content)
                msg_copy = dict(msg)
                msg_copy["content"] = cleaned
                working_copy.append(msg_copy)
            else:
                working_copy.append(msg)

        spec_hint_text = (
            "注意：<automation-spec> 中的自动化流程知识会在压缩后自动注入到消息上下文中，"
            "不需要在 Working Notes 中详细记录这些内容，只需记住'已加载了某某系统的知识'即可。"
        )
        enhanced_focus = (focus_hint + "\n" + spec_hint_text) if focus_hint else spec_hint_text

        return await super().generate_working_notes(working_copy, focus_hint=enhanced_focus)

    def update_status(self, new_status=None):
        """状态更新。"""
        super().update_status(new_status)

    async def _handle_core_event(self, event: CoreEvent, session_id: str):
        """CoreEvent 处理。"""
        await super()._handle_core_event(event, session_id)

    # ==========================================
    # UI Actions — 工作模式切换
    # ==========================================

    async def _switch_work_mode(self, mode: str) -> dict:
        """通用模式切换。如果有活跃 MicroAgent 则立即生效，否则在下次创建时生效。"""
        # 始终存储模式（供 _create_micro_agent 使用）
        self._current_work_mode = mode
        mode_content = self.profile.get(f"{mode}_mode")
        if not mode_content:
            return {"error": f"未知模式: {mode}"}

        ma = self.active_micro_agent
        if ma:
            action_fn = ma.action_registry.get("_flat", {}).get("set_work_mode")
            if action_fn:
                result_str = await action_fn(mode)
                result = json.loads(result_str)
                return result

        # 无活跃 MicroAgent — 模式已存储，下次任务启动时自动生效
        self.persona = mode_content
        return {"status": "ok", "mode": mode}

    # ---- UI Schema ----

    def get_ui_schema(self):
        base = super().get_ui_schema()
        browser_group = {
            "name": "browser",
            "icon": "globe",
            "children": [
                {"action": "show_indicator", "icon": "crosshair", "display_mode": "toast"},
                {"action": "show_range_selector", "icon": "square-dashed", "display_mode": "toast"},
            ]
        }
        mode_group = {
            "name": "mode",
            "icon": "sliders",
            "children": [
                {"action": "set_develop_mode", "icon": "wand", "requires_idle": True, "display_mode": "toast"},
                {"action": "set_execute_mode", "icon": "robot", "requires_idle": True, "display_mode": "toast"},
            ]
        }
        return [browser_group, mode_group] + base

    # ---- UI Action 方法 ----

    async def show_indicator(self):
        """触发浏览器内的indicator（十字准星）"""
        from .skills.browser_automation._shared import infra, _agent_current_tab
        tab = _agent_current_tab.get(self.name)
        if not tab or not tab.session_id:
            return {"error": "No active browser tab"}

        agent_name = json.dumps(self.name)
        session_id = json.dumps(self.active_session_id or "")
        js = f"window.__bh_show_indicator__ ? window.__bh_show_indicator__({agent_name}, {session_id}) : null"
        await infra["cdp_client"].send(
            "Runtime.evaluate", {"expression": js},
            session_id=tab.session_id, timeout=5,
        )
        return {"status": "ok"}

    async def show_range_selector(self):
        """触发浏览器内的range selector"""
        from .skills.browser_automation._shared import infra, _agent_current_tab
        tab = _agent_current_tab.get(self.name)
        if not tab or not tab.session_id:
            return {"error": "No active browser tab"}

        agent_name = json.dumps(self.name)
        session_id = json.dumps(self.active_session_id or "")
        js = f"window.__bh_show_range__ ? window.__bh_show_range__({agent_name}, {session_id}) : null"
        await infra["cdp_client"].send(
            "Runtime.evaluate", {"expression": js},
            session_id=tab.session_id, timeout=5,
        )
        return {"status": "ok"}

    async def set_develop_mode(self):
        return await self._switch_work_mode("develop")

    async def set_execute_mode(self):
        return await self._switch_work_mode("execute")

    # ==========================================
    # Exit Hook — Project Status Confirmation
    # ==========================================

    _STATUS_PROMPT = (
        "You are a bystander observing a conversation between a user and an automation agent. "
        "Based on the conversation below, what is the most likely current project status?\n\n"
        "Valid statuses:\n"
        "- COMPLETED: All requested work is done successfully\n"
        "- WAITING_FOR_USER: Agent is waiting for user input or decision\n"
        "- IN_PROGRESS: Work is still ongoing\n"
        "- STOPPED: Work was intentionally stopped\n"
        "- FAILED: Work encountered an unrecoverable error\n"
        "- UNKNOWN: Cannot determine from the conversation\n\n"
        "Choose the status that best fits the evidence. "
        "Only use UNKNOWN if the conversation truly provides no clue.\n\n"
        "Respond with ONLY a JSON object: {\"status\": \"<STATUS>\", \"reason\": \"<brief reason>\"}"
    )

    @staticmethod
    def _parse_status_response(text: str) -> dict | None:
        """Extract status JSON from LLM response."""
        m = re.search(r'\{[^{}]+\}', text)
        if not m:
            return None
        try:
            obj = json.loads(m.group())
            status = obj.get("status", "").upper().strip()
            valid = ("COMPLETED", "WAITING_FOR_USER", "IN_PROGRESS", "STOPPED", "FAILED", "UNKNOWN")
            if status in valid:
                return {"status": status, "reason": obj.get("reason", "")}
        except (json.JSONDecodeError, AttributeError):
            pass
        return None

    @staticmethod
    def _format_messages_for_status(messages: list, max_count: int = 10) -> str:
        """Format last N messages as plain text conversation."""
        recent = messages[-max_count:] if len(messages) > max_count else messages
        lines = []
        for msg in recent:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            # Strip system tags and spec blocks for cleaner context
            content = re.sub(r'<automation-spec>.*?</automation-spec>', '', content, flags=re.DOTALL).strip()
            content = re.sub(r'<system-[^>]+>.*?</system-[^>]+>', '', content, flags=re.DOTALL).strip()
            if not content:
                continue
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            label = "User" if role == "user" else "Agent"
            lines.append(f"{label}: {content}")
        return "\n\n".join(lines)

    async def _on_before_exit(self) -> bool:
        """Override: infer project status via LLM before exiting automation sessions."""
        # 1. Run parent check first (reply_tracker)
        if not await super()._on_before_exit():
            return False

        # 2. Skip if no actions executed this loop — nothing to judge
        if not self._actions_executed_since_status_check:
            return True

        # 3. Check if this is an automation session
        session = self.current_session
        if not session:
            return True

        metadata = session.get("metadata", {})
        system_name = metadata.get("sk_system_name")
        process_name = metadata.get("sk_process_name")

        if not system_name or not process_name:
            return True  # Not an automation session

        # 4. Get messages from active micro agent
        micro = self.active_micro_agent
        if not micro or not micro.messages:
            return True

        # 5. Infer status via LLM (offline, no signal injection)
        self._actions_executed_since_status_check = False
        try:
            conversation = self._format_messages_for_status(micro.messages)
            prompt = f"{self._STATUS_PROMPT}\n\n---\n{conversation}"
            result = await self.cerebellum.backend.think_with_retry(
                initial_messages=[{"role": "user", "content": prompt}],
                parser=self._parse_status_response,
                max_retries=3,
            )
            if result and result.get("status") and result["status"] != "UNKNOWN":
                new_status = result["status"]
                reason = result.get("reason", "")
                logger.info(f"Exit status inferred: {new_status} ({reason})")

                # Write to session metadata
                metadata["project_status"] = new_status

                # Write to DB
                try:
                    db = self.runtime.post_office.email_db
                    session_id = session.get("session_id", "")
                    await db.update_automation_task_status(session_id, new_status)
                except Exception as e:
                    logger.warning(f"Failed to sync status to DB: {e}")
        except Exception as e:
            logger.warning(f"Exit status inference failed: {e}")

        return True