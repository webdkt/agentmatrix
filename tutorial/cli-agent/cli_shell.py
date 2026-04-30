"""
CLI Shell — AgentShell 协议的 CLI 实现。

实现 AgentShell 的所有方法，让 MicroAgent 能在终端环境中运行。
"""

import asyncio
import logging
from typing import List, Optional

from agentmatrix.core.agent_shell import AgentShell
from agentmatrix.core.interfaces import BrainProtocol, CerebellumProtocol
from agentmatrix.core.cerebellum import Cerebellum
from agentmatrix.core.backends.llm_client import LLMClient

from cli_config import CLIConfig


class CLIShell:
    """AgentShell 的 CLI 实现。

    职责：
    - 管理 brain / cerebellum
    - 提供 prompt 模板
    - 处理 checkpoint（暂停/恢复）
    - 消息压缩（简化版）
    - LLM 可用性检查（简化版）
    """

    name: str
    brain: BrainProtocol
    cerebellum: CerebellumProtocol
    logger: logging.Logger
    persona: str = ""

    def __init__(self, config: CLIConfig):
        self.name = config.agent_name
        self.config = config
        self.logger = logging.getLogger("CLIShell")
        self.logger.setLevel(logging.INFO)

        # 创建 brain
        self.brain = LLMClient(
            url=config.llm_url,
            api_key=config.llm_api_key,
            model_name=config.llm_model,
            parent_logger=self.logger,
        )

        # 创建 cerebellum
        self.cerebellum = Cerebellum(
            backend_client=self.brain,
            agent_name=self.name,
            parent_logger=self.logger,
        )

        # 暂停/停止控制
        self._paused = False
        self._stopped = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始不暂停

        # 事件回调（供 TUI 使用）
        self.on_event = None  # async def on_event(event: CoreEvent)

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

    # ── AgentShell 协议实现 ──────────────────────────────────

    def get_prompt_template(self, name: str) -> str:
        """获取 prompt 模板。

        CLI 实现：直接返回配置中的 system_prompt。
        不同模板名都返回同一个（CLI 场景简单）。
        """
        return self.config.system_prompt

    async def generate_working_notes(
        self, messages: List[dict], focus_hint: str = ""
    ) -> str:
        """从对话历史生成 Working Notes（简化版）。

        CLI 实现：用 LLM 生成简短摘要。
        """
        prompt = """请将以下对话历史压缩为简洁的工作笔记（Markdown 格式）。
保留关键信息：做了什么、得到了什么结果、还有什么未完成。
丢弃客套话和重复内容。

"""
        if focus_hint:
            prompt += f"重点关注：{focus_hint}\n\n"

        # 取最近的消息（避免太长）
        recent = messages[-20:] if len(messages) > 20 else messages
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                prompt += f"[{role}] {content[:500]}\n"

        response = await self.brain.think(
            messages=[{"role": "user", "content": prompt}]
        )
        return response.get("reply", "(无法生成工作笔记)")

    async def compress_messages(self, agent) -> None:
        """压缩 agent 的 messages（简化版）。

        CLI 实现：生成 working notes，保留 system + 重建 user message。
        """
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
        self.logger.info(f"Messages compressed, {len(agent.messages)} messages remaining")

    async def checkpoint(self) -> None:
        """协作式检查点：暂停时阻塞等待。"""
        if self._stopped:
            raise asyncio.CancelledError("Agent stopped")
        if self._paused:
            self.logger.info("Agent paused, waiting for resume...")
            await self._pause_event.wait()

    def get_md_skill_prompt(self, skill_names: List[str]) -> str:
        """获取 MD Skill 的 prompt 文本。

        CLI 实现：从 skill_dir 读取 SKILL.md 文件。
        """
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
        """检查 LLM 服务是否可用（简化版：总是返回 True）。"""
        return True

    async def wait_for_llm_recovery(self) -> None:
        """等待 LLM 服务恢复（简化版：等 5 秒）。"""
        self.logger.info("Waiting for LLM recovery...")
        await asyncio.sleep(5)

    # ── 控制方法 ─────────────────────────────────────────────

    def pause(self):
        self._paused = True
        self._pause_event.clear()

    def resume(self):
        self._paused = False
        self._pause_event.set()

    def stop(self):
        self._stopped = True
        self._paused = False
        self._pause_event.set()
