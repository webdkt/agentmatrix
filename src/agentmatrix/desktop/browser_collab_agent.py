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
from .ui_actions import ui_action
from ..core.signals import CoreEvent

logger = logging.getLogger(__name__)


# ==========================================
# Site Knowledge 标记区间
# ==========================================

SITE_KNOWLEDGE_MARKER_START = "=== 站点自动化知识 ==="
SITE_KNOWLEDGE_MARKER_END = "=== 站点自动化知识 END ==="
SYS_HINT_START = "**** 系统提示 ****"
SYS_HINT_END = "**** 系统提示结束 ****"


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

    读取 ~/site_knowledge/index.txt，按 hostname 匹配当前 URL。

    输出结构（注入到 === 站点自动化知识 === 标记区间内）：
        [agent 主动加载的站点知识 — load_site_knowledge 设置]
        **** 系统提示 ****
        [系统自动注入 — tab 变化时自动刷新，4 种场景]
        **** 系统提示结束 ****
    """

    def __init__(self, agent_name: str, home_dir: str, agent):
        self.agent_name = agent_name
        self.home_dir = home_dir
        self.agent = agent  # BrowserCollabAgent 实例，读写 _current_site_url

    def load(self, current_url: str) -> str:
        """生成完整的站点知识区块内容（不含外层 === 站点自动化知识 === 标记）。"""
        os.makedirs(os.path.join(self.home_dir, "site_knowledge"), exist_ok=True)

        hostname = self._parse_hostname(current_url)
        matches = self._get_hostname_matches(hostname)
        current_site = getattr(self.agent, '_current_site_url', None)

        agent_section = self._build_agent_section(current_url, current_site)
        system_section = self._build_system_hint(current_url, matches, current_site)

        parts = []
        if agent_section:
            parts.append(agent_section)
            parts.append("")
        parts.append(SYS_HINT_START)
        if system_section:
            parts.append(system_section)
        parts.append(SYS_HINT_END)
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Agent 主动加载区
    # ------------------------------------------------------------------

    def _build_agent_section(self, current_url: str, current_site: str) -> str:
        """Agent 通过 load_site_knowledge 主动加载的站点知识（500 行预览）。"""
        if not current_site:
            return ""
        entries = self._parse_index()
        entry = next((e for e in entries if self._entry_key(e).startswith(current_site)), None)
        if not entry:
            return ""

        ep, desc, dirname = entry
        sk_dir = os.path.join(self.home_dir, "site_knowledge")
        site_dir = os.path.join(sk_dir, dirname)

        lines = [
            f"=== 已加载站点知识: {ep} ({desc}) ===",
            f"站点知识目录: ~/site_knowledge/{dirname}",
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

    # ------------------------------------------------------------------
    # 系统自动注入区（4 种场景）
    # ------------------------------------------------------------------

    def _build_system_hint(self, current_url: str, matches: list, current_site: str) -> str:
        if not current_url:
            # 无 tab
            total = len(self._parse_index())
            return f"当前无打开的网页。index.txt中共有{total}条站点知识"

        if matches:
            if current_site:
                # (1) 有匹配 + agent 已加载 → 简短列表
                return self._format_system_brief(current_url, matches)
            else:
                # (2) 有匹配 + agent 未加载 → 200 行预览
                return self._format_system_preview(current_url, matches)
        else:
            if current_site:
                # (3) 无匹配 + agent 已加载 → 留白
                return ""
            else:
                # (4) 无匹配 + agent 未加载 → 提示
                total = len(self._parse_index())
                return f"目前无匹配的站点知识，index.txt中共有{total}条站点知识"

    def _format_system_brief(self, current_url: str, matches: list) -> str:
        """场景 1：有匹配且 agent 已加载 → 仅列出 site_key 概要。"""
        lines = [
            f"当前URL: {current_url}",
            "有以下站点知识可能匹配当前网页：",
        ]
        for ep, desc, dirname in matches:
            lines.append(f"- {ep} | {desc} | 目录: ~/site_knowledge/{dirname}")
        return "\n".join(lines)

    def _format_system_preview(self, current_url: str, matches: list) -> str:
        """场景 2：有匹配且 agent 未加载 → 展示每个匹配 200 行预览。"""
        sk_dir = os.path.join(self.home_dir, "site_knowledge")
        lines = [
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

            readme_path = os.path.join(site_dir, "readme.md")
            content = self._read_file_lines(readme_path, 200)
            if content:
                lines.append("site knowledge:")
                lines.append(content)
                if self._file_has_more(readme_path, 200):
                    lines.append("(read more from readme.md)")

            self._append_flow_list(lines, site_dir)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

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

    async def _on_activate_session(self, session: dict, first_signal=None):
        """Session 激活时自动确保 CDP 浏览器基础设施就绪。

        对 Agent 完全透明：无需手动调用 open_browser，
        CDP 连接、tab 恢复、agent queue 注册全部自动完成。
        """
        try:
            if self.active_micro_agent and hasattr(self.active_micro_agent, '_ensure_browser'):
                await self.active_micro_agent._ensure_browser()
        except Exception as e:
            logger.warning(f"Auto CDP init failed (will retry in actions): {e}")

    def _create_micro_agent(self):
        """注入 site knowledge 后创建 MicroAgent，并注册 tab 变化回调。"""
        from .skills.cdp_browser.skill import _agent_current_tab, _agent_sk_callbacks

        # 如果之前设置过 work mode，用对应的 persona
        mode = getattr(self, '_current_work_mode', None)
        if mode:
            mode_content = self.profile.get(f"{mode}_mode")
            if mode_content:
                self.persona = mode_content

        home_dir = self.runtime.paths.get_agent_home_dir(self.name)
        sk_loader = _SiteKnowledgeLoader(self.name, home_dir, self)

        tab = _agent_current_tab.get(self.name)
        url = tab.url if tab else ""
        site_knowledge = sk_loader.load(url)

        micro = super()._create_micro_agent()
        micro._site_knowledge_loader = sk_loader

        # 注入 site knowledge 到标记区间
        micro.system_prompt = update_site_knowledge_section(
            micro.system_prompt, site_knowledge
        )

        # 注册回调：tab 变化时自动刷新 system prompt
        _agent_sk_callbacks[self.name] = lambda: sk_loader.reload_and_update_prompt(micro)

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
                self._fire_broadcast('work_mode_changed', {"mode": mode})
                return result

        # 无活跃 MicroAgent — 模式已存储，下次任务启动时自动生效
        self.persona = mode_content
        self._fire_broadcast('work_mode_changed', {"mode": mode})
        return {"status": "ok", "mode": mode}

    @ui_action(
        name="set_learning_mode",
        label="学习模式",
        icon="school",
        tooltip="切换到学习模式：和用户协作学习网站自动化流程",
        placement="floating",
        requires_idle=True,
        display_mode="toast",
    )
    async def set_learning_mode(self):
        return await self._switch_work_mode("learning")

    @ui_action(
        name="set_automate_mode",
        label="自动化模式",
        icon="robot",
        tooltip="切换到自动化模式：执行已学会的自动化脚本",
        placement="floating",
        requires_idle=True,
        display_mode="toast",
    )
    async def set_automate_mode(self):
        return await self._switch_work_mode("automation")
