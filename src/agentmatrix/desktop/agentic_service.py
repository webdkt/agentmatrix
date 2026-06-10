"""
AgenticServiceInterface — 内置 Agent 能力的后台服务基类

实现 AgentShell 协议，使后台服务可以拥有自己的 MicroAgent 循环。
服务不是 Agent，但它是一种 Shell——可以作为 MicroAgent 的 parent。

继承此类的服务可以在需要时创建 MicroAgent 执行 LLM 任务。
"""

import logging
from typing import Any, Dict, List, Optional

from ..core.log_util import AutoLoggerMixin
from ..core.micro_agent import MicroAgent

logger = logging.getLogger(__name__)


class AgenticServiceInterface(AutoLoggerMixin):
    """内置 Agent 能力的后台服务基类。

    实现 AgentShell 协议，使服务可以创建和运行 MicroAgent。
    子类只需实现 _get_service_skills() 和具体的业务逻辑。

    使用方式：
        class MyService(AgenticServiceInterface):
            def _get_service_skills(self):
                return ["knowledge_base", "file"]

            async def do_work(self):
                result = await self.execute(
                    task="处理某项任务",
                    system_prompt="你是一个...",
                )
    """

    def __init__(self, runtime):
        self._runtime = runtime
        self.persona = ""

    def _get_service_skills(self) -> List[str]:
        """子类返回此服务需要的技能列表。"""
        return []

    # ============================================================
    # AgentShell 协议实现
    # ============================================================

    @property
    def root_agent(self):
        return self

    @property
    def brain(self):
        return self._runtime.brain

    @property
    def cerebellum(self):
        return self._runtime.cerebellum

    @property
    def runtime(self):
        return self._runtime

    @property
    def logger(self):
        return logger

    @property
    def event_queue(self):
        return self._runtime.event_queue

    async def checkpoint(self):
        pass

    async def compress_messages(self, agent):
        if not hasattr(agent, 'messages') or len(agent.messages) <= 4:
            return

        working_notes = await self._generate_working_notes(agent.messages)

        has_system = agent.messages and agent.messages[0].get("role") == "system"
        new_user_content = f"[WORKING NOTES]\n{working_notes}\n\n请继续执行当前任务。"

        if has_system:
            agent.messages = [agent.messages[0], {"role": "user", "content": new_user_content}]
        else:
            agent.messages = [{"role": "user", "content": new_user_content}]

    async def _generate_working_notes(self, messages: list) -> str:
        conversation = ""
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                conversation += f"[{role}]: {content[:500]}\n\n"

        prompt = (
            "请从以下对话中提取关键信息，生成简洁的工作笔记。\n"
            "保留：任务目标、已完成的操作、关键发现、待处理事项。\n"
            "去除：客套话、重复信息、格式细节。\n"
            "直接输出笔记内容，不要加标题或解释。\n\n"
            f"{conversation[-8000:]}"
        )

        result = await self.brain.think_with_retry(
            [{"role": "user", "content": prompt}],
            lambda raw, **kw: {"status": "success", "content": raw},
            max_retries=1,
        )
        return result if isinstance(result, str) else str(result)

    async def generate_working_notes(self, messages, focus_hint=""):
        return ""

    def notify_llm_unavailable(self):
        pass

    async def wait_for_llm_recovery(self):
        pass

    def get_prompt_template(self, name: str) -> str:
        if hasattr(self._runtime, 'prompt_registry'):
            return self._runtime.prompt_registry.get(name, "")
        return ""

    def get_md_skill_prompt(self, names) -> str:
        return ""

    def is_llm_available(self) -> bool:
        if hasattr(self._runtime, 'llm_monitor') and self._runtime.llm_monitor:
            return self._runtime.llm_monitor.is_available()
        return True

    # ============================================================
    # MicroAgent 执行
    # ============================================================

    def _create_micro_agent(
        self,
        name: str,
        system_prompt: str,
        available_skills: Optional[List[str]] = None,
    ) -> MicroAgent:
        """创建一个以本服务为 parent 的 MicroAgent。"""
        skills = available_skills or self._get_service_skills()
        return MicroAgent(
            parent=self,
            name=name,
            available_skills=skills,
            system_prompt=system_prompt,
        )

    async def execute(
        self,
        task: str,
        system_prompt: str = "",
        name: str = "service-task",
        available_skills: Optional[List[str]] = None,
        simple_mode: bool = True,
        **kwargs,
    ) -> Any:
        """创建 MicroAgent 执行一次性任务。

        Args:
            task: 任务描述
            system_prompt: system prompt（为空时使用任务描述）
            name: 任务名称（用于日志）
            available_skills: 技能列表（为空时使用 _get_service_skills()）
            simple_mode: 是否使用简单模式
            **kwargs: 传给 MicroAgent.execute 的额外参数

        Returns:
            MicroAgent 的执行结果
        """
        if not system_prompt:
            system_prompt = task

        micro = self._create_micro_agent(
            name=name,
            system_prompt=system_prompt,
            available_skills=available_skills,
        )

        return await micro.execute(
            run_label=name,
            task=task,
            simple_mode=simple_mode,
            **kwargs,
        )