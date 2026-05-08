"""
AgentShell — Agent 的外层壳接口。

Agent = AgentShell + AgentCore（一对一）
不同应用形态实现这个接口，Core 通过它与外部世界交互。
"""

from __future__ import annotations
import logging
from typing import List, Dict, Protocol, runtime_checkable

from .interfaces import BrainProtocol, CerebellumProtocol


@runtime_checkable
class AgentShell(Protocol):
    """
    AgentCore 的宿主接口。

    不同应用形态实现这个接口，Core 通过它与外部世界交互。
    """

    brain: BrainProtocol
    cerebellum: CerebellumProtocol
    logger: logging.Logger
    event_queue: "asyncio.Queue"  # Core → Shell 事件输出，所有 MicroAgent 共享

    def get_prompt_template(self, name: str) -> str:
        """获取 prompt 模板。

        Core 通过此方法访问模板，不直接接触文件系统或配置。
        不同 Shell 实现可以用不同方式加载模板（文件系统、数据库、内存等）。

        Args:
            name: 模板名称（如 "SYSTEM_PROMPT", "COLLAB_MODE"）

        Returns:
            模板文本
        """
        ...

    async def generate_working_notes(
        self, messages: List[Dict[str, str]], focus_hint: str = ""
    ) -> str:
        """从对话历史生成 Working Notes（工作笔记）。

        不同 Shell 实现可根据通信模式定制 prompt（邮件、聊天、纯任务等）。

        Args:
            messages: 当前对话历史
            focus_hint: 可选，指导 LLM 重点关注某方面

        Returns:
            Markdown 格式的 Working Notes
        """
        ...

    async def compress_messages(self, agent) -> None:
        """压缩 agent 的 messages（保留 system + 用 working notes 重建 user message）。

        Core 在 token 超阈值时调用此方法。默认实现：
        - 调用 generate_working_notes() 生成工作笔记
        - 保留 system message，用原始 user message + working notes 重建
        - 清空 scratchpad

        Shell 实现可覆盖此方法以自定义压缩策略（如保留邮件历史等）。

        Args:
            agent: MicroAgent 实例（可访问 messages, scratchpad, session 等）
        """
        ...

    async def checkpoint(self) -> None:
        """协作式检查点：Core 在关键位置调用，Shell 决定是否暂停/停止。

        典型实现：检查 paused/stopped 标志，必要时 await 等待恢复。
        """
        ...

    def get_md_skill_prompt(self, skill_names: List[str]) -> str:
        """获取 MD Skill 的 prompt 文本。

        Shell 决定如何读取 SKILL.md、如何组装 prompt。
        Core 只提供 skill 名字列表。

        Args:
            skill_names: skill 名字列表（如 ["git-workflow", "memory"]）

        Returns:
            完整的 MD Skill prompt 文本，用于注入 system prompt
        """
        ...

    def is_llm_available(self) -> bool:
        """检查 LLM 服务是否可用。"""
        ...

    def notify_llm_unavailable(self) -> None:
        """通知 monitor LLM 服务不可用，触发恢复轮询。"""
        ...

    async def wait_for_llm_recovery(self) -> None:
        """等待 LLM 服务恢复。"""
        ...
