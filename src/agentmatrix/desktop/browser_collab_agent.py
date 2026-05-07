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


# ==========================================
# Site Knowledge 标记区间
# ==========================================

SITE_KNOWLEDGE_MARKER_START = "=== 站点自动化知识 ==="
SITE_KNOWLEDGE_MARKER_END = "=== 站点自动化知识 END ==="


def update_site_knowledge_section(text: str, content: str) -> str:
    """在 text 中找到标记区间，替换其中的内容。"""
    pattern = re.escape(SITE_KNOWLEDGE_MARKER_START) + r".*?" + re.escape(SITE_KNOWLEDGE_MARKER_END)
    replacement = SITE_KNOWLEDGE_MARKER_START + "\n" + content + "\n" + SITE_KNOWLEDGE_MARKER_END
    return re.sub(pattern, replacement, text, flags=re.DOTALL)


# ==========================================
# Site Knowledge 自动注入
# ==========================================

class _SiteKnowledgeLoader:
    """根据当前 tab URL 加载匹配的 site knowledge。

    读取 ~/site_knowledge/index.txt，按 url_prefix 匹配当前 URL。
    """

    def __init__(self, agent_name: str, home_dir: str, agent):
        self.agent_name = agent_name
        self.home_dir = home_dir
        self.agent = agent  # BrowserCollabAgent 实例，读写 _current_site_url

    def load(self, current_url: str) -> str:
        """返回注入到 system prompt 的 site knowledge 文本。"""
        # 自动创建 ~/site_knowledge 目录
        sk_dir = os.path.join(self.home_dir, "site_knowledge")
        os.makedirs(sk_dir, exist_ok=True)

        if not current_url:
            return "=== 当前网站知识 ===\n当前页面未匹配到已记录的网站知识"

        # 解析 URL
        parsed = urlparse(current_url)
        hostname = parsed.hostname or ""
        path = parsed.path.rstrip("/")
        url_prefix = hostname + path  # e.g. "www.example.com/shop/item/123"

        # 解析 index.txt
        entries = self._parse_index()
        if not entries:
            return "=== 当前网站知识 ===\n当前页面未匹配到已记录的网站知识"

        # 匹配：url_prefix 以 entry 开头，或 entry 以 url_prefix 开头
        matches = [
            (ep, desc, dirname)
            for ep, desc, dirname in entries
            if url_prefix.startswith(ep) or ep.startswith(url_prefix)
        ]
        # 最长前缀优先
        matches.sort(key=lambda x: -len(x[0]))

        if not matches:
            self.agent._current_site_url = None
            return "=== 当前网站知识 ===\n当前页面未匹配到已记录的网站知识"

        # 检查 current_site_url 是否仍匹配
        current_site = getattr(self.agent, '_current_site_url', None)
        if current_site:
            still_match = any(self._entry_key(m).startswith(current_site) for m in matches)
            if not still_match:
                self.agent._current_site_url = None
                current_site = None

        # 生成文本
        if current_site:
            return self._format_single(current_url, matches, current_site)
        else:
            return self._format_multi(current_url, matches)

    def set_current_site(self, site_url_prefix: str) -> str:
        """LLM 调用 load_site_knowledge 时设置 current_site_url。

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
        return json.dumps({"status": "ok", "site_url_prefix": full_key})

    def reload_and_update_prompt(self, micro_agent):
        """重新加载 site knowledge 并即时更新 micro agent 的 system prompt。"""
        from .skills.cdp_browser.skill import _agent_current_tab

        tab = _agent_current_tab.get(self.agent_name)
        url = tab.url if tab else ""
        new_content = self.load(url)

        micro_agent.system_prompt = update_site_knowledge_section(
            micro_agent.system_prompt, new_content
        )
        if micro_agent.messages and micro_agent.messages[0]["role"] == "system":
            micro_agent.messages[0]["content"] = update_site_knowledge_section(
                micro_agent.messages[0]["content"], new_content
            )

    def _format_multi(self, current_url: str, matches: list) -> str:
        """多匹配模式：展示所有匹配站点，每个前 200 行。"""
        sk_dir = os.path.join(self.home_dir, "site_knowledge")
        lines = [
            "=== 当前网站知识 ===",
            f"当前URL: {current_url}",
            "",
            "匹配到以下已记录的网站知识：",
            "使用 load_site_knowledge(site_key) 加载特定站点的完整知识（site_key 为上方列出的完整 site_key）。",
        ]

        for i, (ep, desc, dirname) in enumerate(matches, 1):
            site_dir = os.path.join(sk_dir, dirname)
            full_key = self._entry_key((ep, desc, dirname))
            lines.append("")
            lines.append(f"=== site {i} ===")
            lines.append(f"site_key: {full_key}")
            lines.append(f"desc: {desc}")
            lines.append(f"目录: ~/site_knowledge/{dirname}")

            # readme.md 前 200 行
            readme_path = os.path.join(site_dir, "readme.md")
            content = self._read_file_lines(readme_path, 200)
            if content:
                lines.append(f"site knowledge:")
                lines.append(content)
                if self._file_has_more(readme_path, 200):
                    lines.append("(read more from readme.md)")

            # 列出其他 md 文件
            self._append_flow_list(lines, site_dir)

        return "\n".join(lines)

    def _format_single(self, current_url: str, matches: list, current_site: str) -> str:
        """已选择模式：展示选中站点完整 500 行。"""
        sk_dir = os.path.join(self.home_dir, "site_knowledge")
        entry = next((m for m in matches if self._entry_key(m).startswith(current_site)), None)
        if not entry:
            return "=== 当前网站知识 ===\n当前页面未匹配到已记录的网站知识"

        ep, desc, dirname = entry
        site_dir = os.path.join(sk_dir, dirname)

        lines = [
            "=== 当前网站知识 ===",
            f"当前URL: {current_url}",
            f"已选定站点: {ep} ({desc})",
            f"站点知识目录: ~/site_knowledge/{dirname}",
            "",
        ]

        # readme.md 前 500 行
        readme_path = os.path.join(site_dir, "readme.md")
        content = self._read_file_lines(readme_path, 500)
        if content:
            lines.append(content)
            if self._file_has_more(readme_path, 500):
                lines.append("(read more from readme.md)")

        # 列出其他 md 文件
        self._append_flow_list(lines, site_dir)

        return "\n".join(lines)

    def _append_flow_list(self, lines: list, site_dir: str):
        """列出站点目录中的流程 md 文件（排除 readme.md）。"""
        if not os.path.isdir(site_dir):
            return
        flows = sorted(
            f for f in os.listdir(site_dir)
            if f.endswith(".md") and f.lower() != "readme.md"
        )
        if flows:
            lines.append("")
            lines.append("已存储自动化流程:")
            for f in flows:
                lines.append(f"- {f}")

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
    """支持浏览器内嵌聊天的 Agent。

    在 BaseAgent 基础上，自动将以下信息转发到浏览器前端：
    - Agent 状态变化（IDLE / THINKING / WORKING 等）
    - CoreEvent（思考输出、action 执行结果等）

    前端通过 __bh_on_event__ 接收这些事件，在聊天组件中展示。
    用户在浏览器中输入的消息通过 __bh_emit__('chat_message') 发回 Agent。
    """

    # Site knowledge：跨 execute 保持，load_site_knowledge action 设置
    _current_site_url: str = None

    async def _broadcast_to_browser(self, event_type: str, data: dict):
        """转发事件到浏览器前端。fire-and-forget，不阻塞主流程。"""
        try:
            from .skills.cdp_browser.skill import _event_listener, _agent_current_tab
            if not _event_listener or not _event_listener.active:
                return
            tab = _agent_current_tab.get(self.name)
            if not tab or not tab.session_id:
                return
            await _event_listener.emit_to_browser(tab.session_id, event_type, data)
        except Exception as e:
            logger.debug(f"Browser broadcast failed: {e}")

    def _fire_broadcast(self, event_type: str, data: dict):
        """异步触发浏览器广播（fire-and-forget）。"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast_to_browser(event_type, data))
        except RuntimeError:
            pass

    # ==========================================
    # BaseAgent overrides
    # ==========================================

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

    def _create_micro_agent(self):
        """注入 site knowledge 后创建 MicroAgent。"""
        from .skills.cdp_browser.skill import _agent_current_tab

        home_dir = self.runtime.paths.get_agent_home_dir(self.name)
        sk_loader = _SiteKnowledgeLoader(self.name, home_dir, self)

        tab = _agent_current_tab.get(self.name)
        url = tab.url if tab else ""
        site_knowledge = sk_loader.load(url)

        micro = super()._create_micro_agent()
        micro._site_knowledge_loader = sk_loader

        # 直接注入 site knowledge 到标记区间
        micro.system_prompt = update_site_knowledge_section(
            micro.system_prompt, site_knowledge
        )

        return micro

    def update_status(self, new_status=None):
        """状态更新后转发到浏览器。"""
        super().update_status(new_status)
        if new_status is not None:
            self._fire_broadcast('agent_status', {
                'status': self._status,
            })

    async def _handle_core_event(self, event: CoreEvent, session_id: str):
        """CoreEvent 处理后转发到浏览器。"""
        await super()._handle_core_event(event, session_id)

        et, en, d = event.event_type, event.event_name, event.detail

        # 思考输出
        if et == "think" and en == "brain":
            thought = d.get("thought", "")
            if thought:
                self._fire_broadcast('agent_output', {
                    'type': 'think',
                    'text': thought,
                })

        # action 检测
        elif et == "action" and en == "detected":
            actions = d.get("actions", [])
            if actions:
                self._fire_broadcast('agent_output', {
                    'type': 'action_detected',
                    'text': ', '.join(actions),
                })

        # action 开始
        elif et == "action" and en == "started":
            self._fire_broadcast('agent_output', {
                'type': 'action_started',
                'text': d.get('action_name', '?'),
            })

        # action 完成
        elif et == "action" and en == "completed":
            name = d.get('action_name', '?')
            status = d.get('status', 'ok')
            preview = d.get('result_preview', '')
            self._fire_broadcast('agent_output', {
                'type': 'action_completed',
                'text': f"{name} -> {preview[:200]}" if status == 'ok' else f"{name} 失败: {preview}",
            })
