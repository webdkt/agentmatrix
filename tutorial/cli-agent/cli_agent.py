"""
CLI Agent — BasicAgent 的 CLI 实现。

继承 BasicAgent 的信号驱动架构，提供终端 Agent 交互。

特点：
- 用户输入通过 input_queue 异步投递，不阻塞
- MicroAgent 持久化（创建一次，复用）
- /new 命令切换 session_id，触发 session 切换
- 事件输出通过 _handle_core_event 格式化到终端
"""

import asyncio
import logging
import uuid
from typing import List, Optional

from agentmatrix.desktop.browser_collab_agent import BrowserCollabAgent
from agentmatrix.core.micro_agent import MicroAgent
from agentmatrix.core.signals import CoreEvent, TextSignal
from agentmatrix.core.cerebellum import Cerebellum
from agentmatrix.core.backends.llm_client import LLMClient

from cli_session import InMemorySessionStore
from cli_config import CLIConfig


class CLIAgent(BrowserCollabAgent):
    """BasicAgent 的 CLI 实现。

    用户输入通过 input_queue 异步投递，MicroAgent 持久化复用。
    /new 命令切换 session_id，触发 BasicAgent 的 session 切换机制。
    """

    _log_from_attr = "name"

    def __init__(self, config: CLIConfig, output_cb=None):
        profile = {
            "name": config.agent_name,
            "description": "CLI Agent",
            "skills": config.skills or ["base", "file", "shell"],
        }
        super().__init__(profile)

        self.config = config
        self._output_cb = output_cb

        # LLM
        self.brain = LLMClient(
            url=config.llm_url,
            api_key=config.llm_api_key,
            model_name=config.llm_model,
            parent_logger=self.logger,
        )
        self.cerebellum = Cerebellum(
            backend_client=self.brain,
            agent_name=self.name,
            parent_logger=self.logger,
        )

        # Session
        self.session_store = InMemorySessionStore()
        self._current_session_id = f"cli-{uuid.uuid4().hex[:8]}"

    # ==========================================
    # BasicAgent overrides
    # ==========================================

    async def _on_activate_session(self, session: dict, first_signal=None):
        """CLI: 无需 desktop 的 workspace/container 初始化。"""
        pass

    async def _on_deactivate_session(self, session: dict):
        """CLI: 无需 desktop 的 session 持久化。"""
        pass

    async def _route_signal(self, signal):
        """CLI: 显示收到的信号，然后路由。"""
        await self._print_signal(signal)
        await super()._route_signal(signal)

    async def _print_signal(self, signal):
        """在输出区域显示收到的信号（不同类型用不同颜色）。"""
        cb = self._output_cb
        if not cb:
            return

        # TextSignal 是用户自己输入的，不需要再显示
        if isinstance(signal, TextSignal) and signal.type_name == "user_input":
            return

        try:
            text = signal.to_text()
            sig_type = getattr(signal, "signal_type", "unknown")
            target_id = getattr(signal, "target_id", "")
            header = f"[signal:{sig_type}]"
            if target_id:
                header += f"  tab:{target_id[:8]}"
            await cb(f"\n{header}", "bold yellow")
            if text:
                await cb(text, "yellow")
        except Exception:
            await cb(f"[signal] {type(signal).__name__}", "yellow")

    async def _resolve_session(self, signal) -> dict:
        """CLI: 所有输入路由到当前 session。/new 时切换 session_id。"""
        return {"session_id": self._current_session_id}

    def _get_system_prompt(self) -> str:
        return self.config.system_prompt

    def _get_run_label(self, session: dict) -> str:
        return "CLI Chat"

    def _create_session_store(self, session: dict):
        return self.session_store

    def _create_micro_agent(self) -> MicroAgent:
        return MicroAgent(
            parent=self,
            name=self.name,
            available_skills=self.skills if self.skills else None,
            system_prompt=self.config.system_prompt,
            compression_token_threshold=self.config.compression_token_threshold,
        )

    async def _handle_core_event(self, event: CoreEvent, session_id: str):
        """CLI: 格式化事件输出到终端 + 广播到浏览器。"""
        et, en, d = event.event_type, event.event_name, event.detail

        # 状态更新（触发 BrowserCollabAgent.update_status → 浏览器广播）
        if et == "status":
            self.update_status(new_status=en.upper())
            return

        # 浏览器广播（BrowserCollabAgent 的逻辑，跳过 BaseAgent）
        if et == "think" and en == "brain":
            thought = d.get("thought", "")
            if thought:
                self._fire_broadcast('agent_output', {'type': 'think', 'text': thought})
        elif et == "action" and en == "detected":
            actions = d.get("actions", [])
            if actions:
                self._fire_broadcast('agent_output', {'type': 'action_detected', 'text': ', '.join(actions)})
        elif et == "action" and en == "started":
            self._fire_broadcast('agent_output', {'type': 'action_started', 'text': d.get('action_name', '?')})
        elif et == "action" and en == "completed":
            name = d.get('action_name', '?')
            status = d.get('status', 'ok')
            preview = d.get('result_preview', '')
            self._fire_broadcast('agent_output', {
                'type': 'action_completed',
                'text': f"{name} -> {preview[:200]}" if status == 'ok' else f"{name} 失败: {preview}",
            })

        # CLI 终端输出
        cb = self._output_cb
        if not cb:
            return

        if et == "think" and en == "brain":
            thought = d.get("thought", "")
            if thought:
                await cb(f"\n🤖 {thought}", "")

        elif et == "action" and en == "detected":
            await cb(f"[action] {', '.join(d.get('actions', []))}", "bold cyan")

        elif et == "action" and en == "started":
            await cb(f"[action] {d.get('action_name', '?')} ...", "cyan")

        elif et == "action" and en == "completed":
            name = d.get("action_name", "?")
            status = d.get("status", "ok")
            preview = d.get("result_preview", "")
            if status == "ok":
                await cb(f"[action] {name} -> {preview[:200]}", "green")
            elif status == "error":
                await cb(f"[action] {name} 失败: {preview}", "red")

        elif et == "action" and en == "error":
            await cb(
                f"[action] {d.get('action_name', '?')} "
                f"错误: {d.get('error_message', '')}",
                "red",
            )

    # ==========================================
    # AgentShell implementations
    # ==========================================

    def get_prompt_template(self, name: str) -> str:
        """CLI: 所有模板返回同一个 system_prompt。"""
        return self.config.system_prompt

    async def generate_working_notes(
        self,
        messages: list,
        focus_hint: str = "",
        scratchpad: list = None,
        is_top_level: bool = False,
    ) -> str:
        """CLI: 简化版 Working Notes。"""
        prompt = (
            "请将以下对话历史压缩为简洁的工作笔记（Markdown 格式）。\n"
            "保留关键信息：做了什么、得到了什么结果、还有什么未完成。\n"
            "丢弃客套话和重复内容。\n"
        )
        if focus_hint:
            prompt += f"\n重点关注：{focus_hint}\n"

        recent = messages[-20:] if len(messages) > 20 else messages
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                prompt += f"\n[{role}] {content[:500]}"

        response = await self.brain.think(
            messages=[{"role": "user", "content": prompt}]
        )
        return response.get("reply", "(无法生成工作笔记)")

    async def compress_messages(self, agent) -> None:
        """CLI: 简化版消息压缩。"""
        working_notes = await self.generate_working_notes(agent.messages)

        has_system = agent.messages and agent.messages[0].get("role") == "system"
        new_user_content = f"[WORKING NOTES]\n{working_notes}\n\n请继续执行。"

        if has_system:
            agent.messages = [
                agent.messages[0],
                {"role": "user", "content": new_user_content},
            ]
        else:
            agent.messages = [{"role": "user", "content": new_user_content}]

        agent.scratchpad.clear()
        self.logger.info(
            f"Messages compressed, {len(agent.messages)} messages remaining"
        )

    def get_md_skill_prompt(self, skill_names: List[str]) -> str:
        """CLI: 从 skill_dir 读取 SKILL.md。"""
        if not skill_names or not self.config.skill_dir:
            return ""

        from pathlib import Path

        skills_dir = Path(self.config.skill_dir)
        if not skills_dir.exists():
            return ""

        lines = [
            "#### B. 扩展技能 (Procedural Skills)",
            f"你有 {len(skill_names)} 个额外扩展技能。",
            "如果需要使用扩展技能，先读取对应目录下的 skill.md 了解用法。",
            "",
            "可用扩展技能：",
        ]

        for name in skill_names:
            skill_file = skills_dir / name / "skill.md"
            if skill_file.exists():
                desc = skill_file.read_text(encoding="utf-8")[:200]
                lines.append(f"- **{name}**: {desc}...")
            else:
                lines.append(f"- **{name}**: (请查看 skill 文件)")

        return "\n".join(lines)

    def is_llm_available(self) -> bool:
        return True

    async def wait_for_llm_recovery(self) -> None:
        self.logger.info("Waiting for LLM recovery...")
        await asyncio.sleep(5)

    # ==========================================
    # CLI-specific methods
    # ==========================================

    def rebuild_brain(self, config: CLIConfig):
        """更换 LLM 后重建 brain 和 cerebellum。"""
        self.config = config
        self.brain = LLMClient(
            url=config.llm_url,
            api_key=config.llm_api_key,
            model_name=config.llm_model,
            parent_logger=self.logger,
        )
        self.cerebellum = Cerebellum(
            backend_client=self.brain,
            agent_name=self.name,
            parent_logger=self.logger,
        )

    def new_session(self):
        """创建新 session（/new 命令调用）。

        生成新 session_id + 空 session_store。
        下一条输入触发 BasicAgent 的 session 切换：
        deactivate 旧 session → activate 新 session。
        """
        self._current_session_id = f"cli-{uuid.uuid4().hex[:8]}"
        self.session_store = InMemorySessionStore()
        # 清除 MicroAgent 的 scratchpad
        if self.active_micro_agent:
            self.active_micro_agent.scratchpad.clear()
        self.logger.info(f"New CLI session: {self._current_session_id}")
