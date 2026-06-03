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
from urllib.parse import urlparse

from .base_agent import BaseAgent
from .signals import BrowserSignal

from ..core.signals import CoreEvent

logger = logging.getLogger(__name__)

# ── Site Knowledge tag patterns for message-level injection ──

_SITE_KNOWLEDGE_RE = re.compile(r'<site-knowledge>.*?</site-knowledge>\n*', re.DOTALL)
_SITE_KNOWLEDGE_HINT_RE = re.compile(r'\s*<site-knowledge-hint>.*?</site-knowledge-hint>\s*', re.DOTALL)


# ==========================================
# Site Knowledge Loader
# ==========================================

class _SiteKnowledgeLoader:
    """根据当前 tab URL 加载匹配的 site knowledge。

    读取 ~/site_knowledge/index.txt，按 hostname 匹配当前 URL。

    新架构下：
    - load() 返回 agent 主动加载的站点知识内容（用于 <site-knowledge> tag 包裹）
    - build_tab_hint() 根据当前 URL 和已加载状态生成动态提示（用于 tab 变化时注入）
    """

    def __init__(self, agent_name: str, home_dir: str, agent):
        self.agent_name = agent_name
        self.home_dir = home_dir
        self.agent = agent  # BrowserCollabAgent 实例，读写 _current_site_url 等

    def load(self, current_url: str) -> str:
        """生成 agent 主动加载的站点知识内容（不含 tag 包裹）。

        仅返回 _build_agent_section 的结果，不再包含系统自动注入区。
        """
        current_site = getattr(self.agent, '_loaded_site_key', None)
        loaded_process = getattr(self.agent, '_loaded_process_dir', None)

        if not current_site:
            return ""

        entries = self._parse_index()
        entry = next((e for e in entries if self._entry_key(e) == current_site), None)
        if not entry:
            return ""

        ep, desc, dirname = entry
        sk_dir = os.path.join(self.home_dir, "site_knowledge")
        site_dir = os.path.join(sk_dir, dirname)

        if loaded_process:
            return self._build_process_section(ep, desc, dirname, site_dir, loaded_process)

        # Site-only loading
        full_key = self._entry_key(entry)
        lines = [
            f"已加载：{full_key}",
            "",
        ]
        readme_path = os.path.join(site_dir, "readme.md")
        content = self._read_file_lines(readme_path, 500)
        if content:
            lines.append(content)
            if self._file_has_more(readme_path, 500):
                lines.append("(read more from readme.md)")

        self._append_flow_list(lines, site_dir)
        return "\n".join(lines)

    def build_tab_hint(self, current_url: str) -> str:
        """根据当前 URL 与已加载 SK 的关系，生成动态提示文字。

        返回空字符串表示无需提示（已加载且匹配，或已加载但当前页面无匹配）。
        返回提示文字时，调用方应注入到 MicroAgent 的 user message 中。
        """
        hostname = self._parse_hostname(current_url) if current_url else ""
        matches = self._get_hostname_matches(hostname) if hostname else []
        current_site = getattr(self.agent, '_loaded_site_key', None)

        if current_site:
            loaded_in_matches = any(self._entry_key(m) == current_site for m in matches)
            if loaded_in_matches:
                return ""  # 已加载且匹配，无需提示
            if matches:
                lines = ["当前页面与已加载的站点知识不一致。"]
                lines.append("以下站点知识匹配当前页面：")
                for ep, desc, dirname in matches:
                    full_key = self._entry_key((ep, desc, dirname))
                    lines.append(f"- {full_key}: {desc}")
                lines.append("是否要加载新的站点知识？调用 load_site_knowledge(site_key)")
                return "\n".join(lines)
            return ""  # 已加载 SK，当前页面无匹配，不干扰
        else:
            if matches:
                lines = ["检测到匹配的站点知识："]
                for ep, desc, dirname in matches:
                    full_key = self._entry_key((ep, desc, dirname))
                    lines.append(f"- {full_key}: {desc}")
                lines.append("是否要加载？调用 load_site_knowledge(site_key)")
                return "\n".join(lines)
            return ""

    # ------------------------------------------------------------------
    # Agent 主动加载区
    # ------------------------------------------------------------------

    def _build_process_section(self, ep: str, desc: str, dirname: str,
                                site_dir: str, process_dir_name: str) -> str:
        """生成具体自动化流程的知识注入内容。"""
        full_key = f"{ep}:{desc}:{dirname}"
        process_dir = os.path.join(site_dir, process_dir_name)

        if not os.path.isdir(process_dir):
            return (f"已加载: {full_key}\n\n"
                    f"⚠️ 流程目录不存在: {process_dir_name}")

        lines = [
            f"已加载: {full_key}",
            f"Automation Process: {process_dir_name}",
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
        import re as _re
        step_pattern = _re.compile(r'^step-(\d+)-(.+)\.md$', _re.IGNORECASE)
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

    def set_current_site(self, site_url_prefix: str, process_dir_name: str = None) -> str:
        """LLM 调用 load_site_knowledge 时设置 current_site_url 和可选的 process_dir。

        site_url_prefix 为 index.txt 中的整行 key（url_prefix:desc:dir_name），
        使用 startswith 匹配。
        """
        entries = self._parse_index()
        key = site_url_prefix.strip()
        match = next((e for e in entries if self._entry_key(e).startswith(key)), None)
        if not match:
            return json.dumps({"error": f"未找到站点: {site_url_prefix}"})
        full_key = self._entry_key(match)
        self.agent._current_site_url = full_key
        self.agent._loaded_site_key = full_key

        # Validate process_dir if provided
        if process_dir_name:
            ep, desc, dirname = match
            site_dir = os.path.join(self.home_dir, "site_knowledge", dirname)
            process_dir = os.path.join(site_dir, process_dir_name)
            if not os.path.isdir(process_dir):
                return json.dumps({"error": f"流程目录不存在: {process_dir_name}"})

        self.agent._loaded_process_dir = process_dir_name if process_dir_name else None

        # Persist to session metadata
        self._sync_session_metadata()

        result = {"status": "ok", "site_url_prefix": full_key}
        if process_dir_name:
            result["process_dir"] = process_dir_name
        return json.dumps(result, ensure_ascii=False)

    def _sync_session_metadata(self):
        """将当前加载状态同步到 session metadata 以便持久化。"""
        session = getattr(self.agent, 'current_session', None)
        if session:
            metadata = session.setdefault("metadata", {})
            metadata["sk_site_key"] = self.agent._loaded_site_key
            metadata["sk_process_dir"] = self.agent._loaded_process_dir

    # ------------------------------------------------------------------
    # 内部 helpers
    # ------------------------------------------------------------------

    def _parse_hostname(self, url: str) -> str:
        if not url:
            return ""
        return urlparse(url).hostname or ""

    def _get_hostname_matches(self, hostname: str) -> list:
        """按 hostname 匹配 index.txt 条目，最长前缀优先。"""
        if not hostname:
            return []
        entries = self._parse_index()
        matches = [
            (ep, desc, dirname)
            for ep, desc, dirname in entries
            if ep.split("/")[0] == hostname
        ]
        matches.sort(key=lambda x: -len(x[0]))
        return matches

    def _append_flow_list(self, lines: list, site_dir: str):
        """列出站点目录中的自动化流程子目录。"""
        if not os.path.isdir(site_dir):
            return
        subdirs = sorted(
            d for d in os.listdir(site_dir)
            if os.path.isdir(os.path.join(site_dir, d))
            and not d.startswith('.') and d != 'scripts'
        )
        if subdirs:
            lines.append("")
            lines.append("# Automation Processes")
            lines.append("This site has following automation process")
            for d in subdirs:
                lines.append(f"- {d}")
            lines.append("")
            lines.append("To use a specific process, call load_site_knowledge(site_key, process_dir_name)")

    @staticmethod
    def _entry_key(entry):
        """将 (url_prefix, desc, dirname) 拼成 index.txt 原始行作为唯一 key。"""
        return f"{entry[0]}:{entry[1]}:{entry[2]}"

    def _parse_index(self) -> list:
        """解析 index.txt → [(url_prefix, desc, dirname), ...]"""
        index_path = os.path.join(self.home_dir, "site_knowledge", "index.txt")
        if not os.path.isfile(index_path):
            return []
        entries = []
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(":", 2)
                    if len(parts) == 3:
                        entries.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
        except Exception as e:
            logger.warning(f"[SiteKnowledge] Failed to parse index.txt: {e}")
        return entries

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
            logger.warning(f"[SiteKnowledge] Failed to read {path}: {e}")
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
    - Site knowledge 通过 <site-knowledge> tag 注入到 user message 上下文
    - Tab 变化时通过 BrowserSignal 注入 <site-knowledge-hint> 提示

    浏览器端通过 __bh_emit__ 发送事件（indicator_result, range_result 等），
    Agent 通过 CDP 调用 __bh_show_indicator__ / __bh_show_range__ 触发交互。

    使用 BaseAgent 的 session_type='local'（默认）直接操作宿主机文件。
    """

    # Site knowledge：跨 execute 保持，load_site_knowledge action 设置
    _current_site_url: str = None
    _loaded_site_key: str = None
    _loaded_process_dir: str = None

    # ==========================================
    # Site Knowledge 静态工具方法
    # ==========================================

    @staticmethod
    def _purge_sk_from_messages(messages):
        """从消息历史中移除所有 <site-knowledge> 块。"""
        for msg in messages:
            c = msg.get("content")
            if isinstance(c, str):
                msg["content"] = _SITE_KNOWLEDGE_RE.sub('', c).strip()

    @staticmethod
    def _purge_sk_hints(messages):
        """从消息历史中移除所有 <site-knowledge-hint> 块。"""
        for msg in messages:
            c = msg.get("content")
            if isinstance(c, str):
                msg["content"] = _SITE_KNOWLEDGE_HINT_RE.sub('\n', c).strip()

    @staticmethod
    def _extract_current_sk(messages):
        """从消息历史中提取最新的 <site-knowledge> 内容块（含 tag）。"""
        pattern = re.compile(r'<site-knowledge>.*?</site-knowledge>', re.DOTALL)
        for msg in reversed(messages):
            c = msg.get("content", "")
            if isinstance(c, str):
                match = pattern.search(c)
                if match:
                    return match.group(0)
        return None

    @staticmethod
    def _inject_sk_to_first_user_msg(messages, sk_content):
        """将 SK 内容注入到第一条 user message 的开头。"""
        for msg in messages:
            if msg.get("role") == "user":
                msg["content"] = f"{sk_content}\n\n{msg['content']}"
                return True
        return False

    # ==========================================
    # BaseAgent overrides
    # ==========================================

    async def _route_signal(self, signal):
        """BrowserSignal 处理：过滤 orphan 信号 + 注入 SK hint。"""
        if isinstance(signal, BrowserSignal):
            session_id = signal.agent_session_id
            if not session_id:
                if self.current_session:
                    signal.agent_session_id = self.current_session["session_id"]
                else:
                    return  # 无 session context，丢弃 orphan 信号

            # Tab URL 变化时注入 site-knowledge hint
            if signal.event_type == "page_navigated" and signal.url:
                self._inject_sk_hint(signal.url)

        await super()._route_signal(signal)

    def _inject_sk_hint(self, current_url: str):
        """Tab URL 变化时注入 SK hint 到 MicroAgent messages。"""
        ma = self.active_micro_agent
        if not ma or not hasattr(ma, '_site_knowledge_loader'):
            return
        hint = ma._site_knowledge_loader.build_tab_hint(current_url)
        if not hint:
            return

        # 清除旧的 <site-knowledge-hint> 块
        self._purge_sk_hints(ma.messages)

        # 注入到最后一条 user message
        tagged = f"<site-knowledge-hint>\n{hint}\n</site-knowledge-hint>"
        for i in range(len(ma.messages) - 1, -1, -1):
            if ma.messages[i].get("role") == "user":
                ma.messages[i]["content"] += "\n\n" + tagged
                return
        # 没有找到 user message，创建一条新的
        ma.messages.append({"role": "user", "content": tagged})

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

        # 明确切换到不同 session 时，恢复 site knowledge 状态
        session_id = session["session_id"]
        if self._last_deactivated_session_id != session_id:
            metadata = session.get("metadata", {})
            self._current_site_url = metadata.get("sk_site_key")
            self._loaded_site_key = metadata.get("sk_site_key")
            self._loaded_process_dir = metadata.get("sk_process_dir")
            from .skills.browser_automation._shared import _agent_env_callbacks
            _agent_env_callbacks.pop(self.name, None)
        try:
            if self.active_micro_agent and hasattr(self.active_micro_agent, '_ensure_browser'):
                await self.active_micro_agent._ensure_browser()
        except Exception as e:
            logger.warning(f"Auto CDP init failed (will retry in actions): {e}")

    def _create_micro_agent(self):
        """创建 MicroAgent，设置 site knowledge loader。"""
        from .skills.browser_automation._shared import _agent_current_tab

        # 如果之前设置过 work mode，用对应的 persona
        mode = getattr(self, '_current_work_mode', None)
        if mode:
            mode_content = self.profile.get(f"{mode}_mode")
            if mode_content:
                self.persona = mode_content

        home_dir = self.runtime.paths.get_agent_home_dir(self.name)
        sk_loader = _SiteKnowledgeLoader(self.name, home_dir, self)

        micro = super()._create_micro_agent()
        micro._site_knowledge_loader = sk_loader

        # 不再注入 site knowledge 到 system prompt
        # 不再注册 tab 变化回调（由 _route_signal 中的 BrowserSignal 处理）
        # 不再在 _before_think_hook 中刷新 SK

        return micro

    # ==========================================
    # 消息压缩保护
    # ==========================================

    async def compress_messages(self, agent) -> None:
        """压缩消息时，保护 site knowledge 内容。

        1. 提取当前 <site-knowledge> 内容块
        2. 清除 <site-knowledge> 和 <site-knowledge-hint> 块（节省压缩 token）
        3. 调用父类压缩
        4. 将 SK 重新注入到压缩后的第一条 user message
        """
        # 1. 提取当前 SK（压缩前）
        current_sk = self._extract_current_sk(agent.messages)

        # 2. 清除 SK 和 SK hint 块（压缩前，避免 LLM 混淆）
        for msg in agent.messages:
            c = msg.get("content")
            if isinstance(c, str):
                c = _SITE_KNOWLEDGE_RE.sub('[站点自动化知识已加载]', c)
                c = _SITE_KNOWLEDGE_HINT_RE.sub('', c).strip()
                msg["content"] = c

        # 3. 调用父类压缩
        await super().compress_messages(agent)

        # 4. 压缩后将 SK 重新注入到第一条 user message
        if current_sk:
            self._inject_sk_to_first_user_msg(agent.messages, current_sk)

    async def generate_working_notes(self, messages, focus_hint=""):
        """生成 Working Notes 时，告知 LLM 不需详细记录 SK 内容。"""
        # 替换 SK 内容为简短占位（节省 token）
        working_copy = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                cleaned = _SITE_KNOWLEDGE_RE.sub('[站点自动化知识已加载]', content)
                cleaned = _SITE_KNOWLEDGE_HINT_RE.sub('', cleaned).strip()
                msg_copy = dict(msg)
                msg_copy["content"] = cleaned
                working_copy.append(msg_copy)
            else:
                working_copy.append(msg)

        sk_hint_text = (
            "注意：<site-knowledge> 中的站点自动化知识会在压缩后自动注入到消息上下文中，"
            "不需要在 Working Notes 中详细记录这些内容，只需记住'已加载了某某站点的知识'即可。"
        )
        enhanced_focus = (focus_hint + "\n" + sk_hint_text) if focus_hint else sk_hint_text

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