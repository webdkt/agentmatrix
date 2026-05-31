"""
SubAgent — 轻量 Shell 实现，给嵌套 MicroAgent 提供运行环境。

SubAgent = SubAgentShell (Shell) + MicroAgent (Core)

职责：
1. Prompt 组装（system_prompt + core_prompt 自动注入）
2. 退出决策（result_params 校验、格式重试）
3. 资源代理（从 parent BaseAgent 获取 brain/cerebellum/runtime）

SubAgent 自身的 root_agent 指向 parent (BaseAgent)，
内部 MicroAgent 的 root_agent 指向 SubAgent 自身。
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any

from .signals import TextSignal


logger = logging.getLogger(__name__)


class SubAgentShell:
    """
    轻量 Shell —— 嵌套 MicroAgent 的运行环境。

    实现 AgentShell 协议（duck typing），使 MicroAgent 的
    self.root_agent 指向本实例而非 BaseAgent。

    所有协议方法委托给 parent (BaseAgent)。
    """

    def __init__(
        self,
        parent,                        # AgentShell 实例（BaseAgent 等）
        name: str,
        available_skills: List[str],
        system_prompt: str = "",       # 已组装好的 prompt（调用方负责）
        result_params: Dict[str, str] = None,  # 返回值 schema
        max_result_retries: int = 3,
        micro_agent_attrs: Dict[str, Any] = None,  # 注入到 MicroAgent 的属性
        md_skill_names: List[str] = None,
    ):
        self.name = name
        self._parent = parent
        self._available_skills = available_skills
        self._system_prompt = system_prompt
        self._result_params = result_params
        self._max_result_retries = max_result_retries
        self._micro_agent_attrs = micro_agent_attrs or {}
        self._md_skill_names = md_skill_names or []

        # 运行时状态
        self._micro_agent = None
        self._validated_result = None
        self._retries = 0
        self._last_exit_action = None

    # ============================================================
    # AgentShell 协议 —— 属性代理
    # ============================================================

    @property
    def root_agent(self):
        """SubAgent 的 root_agent 是 parent (BaseAgent)。"""
        return self._parent

    @property
    def brain(self):
        return self._parent.brain

    @property
    def cerebellum(self):
        return self._parent.cerebellum

    @property
    def logger(self):
        return self._parent.logger

    @property
    def event_queue(self):
        return self._parent.event_queue

    @property
    def runtime(self):
        return self._parent.runtime

    # ============================================================
    # AgentShell 协议 —— 方法代理
    # ============================================================

    async def checkpoint(self):
        await self._parent.checkpoint()

    async def compress_messages(self, agent):
        await self._parent.compress_messages(agent)

    def notify_llm_unavailable(self):
        self._parent.notify_llm_unavailable()

    async def wait_for_llm_recovery(self):
        await self._parent.wait_for_llm_recovery()

    def get_prompt_template(self, name: str) -> str:
        return self._parent.get_prompt_template(name)

    def get_md_skill_prompt(self, names) -> str:
        return ""

    def is_llm_available(self) -> bool:
        return self._parent.is_llm_available()

    # ============================================================
    # Prompt 组装
    # ============================================================

    def _build_system_prompt(self) -> str:
        """组装传给 MicroAgent 的 system_prompt。

        调用方负责组装完整 prompt，这里只做 result_params 注入。
        core_prompt 由 MicroAgent._finalize_system_prompt() 自动追加。
        """
        prompt = self._system_prompt

        # 注入 result_params schema 到 prompt
        if self._result_params:
            schema_desc = ", ".join(
                f'"{k}": "{v}"' for k, v in self._result_params.items()
            )
            prompt += (
                f"\n\n## 输出要求\n"
                f"任务完成后，使用 return_result 返回结果：\n"
                f"return_result(result={{{schema_desc}}})\n"
            )

        return prompt

    # ============================================================
    # 退出决策
    # ============================================================

    async def _should_exit(self) -> bool:
        """Shell 层退出决策，绑定到 MicroAgent._before_exit_hook。

        - 无 result_params → 允许退出
        - 有 result_params 且已校验通过 → 允许退出
        - 有 result_params 但未通过 → 注入反馈，继续循环
        - 重试耗尽 → 允许退出
        """
        if not self._result_params:
            return True

        if self._validated_result is not None:
            self._micro_agent.result = self._validated_result
            return True

        # 尝试从最后一条 assistant 消息提取结构化结果
        if self._retries < self._max_result_retries:
            parsed = await self._try_parse_result()
            if parsed:
                self._micro_agent.result = parsed
                return True

            # parse 失败 → 注入格式提示，继续循环
            self._retries += 1
            hint = self._build_format_hint()
            self._micro_agent.signal_queue.put_nowait(
                TextSignal(text=hint, type_name="result_format_error")
            )
            return False

        # 重试耗尽
        return True

    async def _try_parse_result(self) -> Optional[dict]:
        """用 brain 从最后一条消息提取结构化结果。"""
        if not self._micro_agent or not self._micro_agent.messages:
            return None

        last_content = ""
        for msg in reversed(self._micro_agent.messages):
            if msg.get("role") == "assistant":
                last_content = msg.get("content", "")
                break

        if not last_content:
            return None

        schema_desc = json.dumps(self._result_params, ensure_ascii=False)
        extraction_prompt = (
            f"从以下对话输出中提取结果，返回 JSON。\n"
            f"预期字段：{schema_desc}\n\n"
            f"对话输出：\n{last_content[-3000:]}\n\n"
            f"只返回 JSON，不要解释。如果无法提取，返回 {{}}。"
        )

        try:
            result = await self.brain.think_with_retry(
                initial_messages=[{"role": "user", "content": extraction_prompt}],
                parser=self._parse_json_from_text,
                max_retries=2,
            )
            if result and all(k in result for k in self._result_params):
                return result
        except Exception as e:
            logger.debug(f"Result extraction failed: {e}")

        return None

    @staticmethod
    def _parse_json_from_text(text: str) -> dict:
        """从文本中提取 JSON 对象。"""
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("No JSON found")

    def _build_format_hint(self) -> str:
        """构建格式提示消息。"""
        params = ", ".join(
            f"{k}=<{v}>" for k, v in self._result_params.items()
        )
        return (
            f"[System] 请使用 return_result({params}) 返回结构化结果。"
            f"所有参数必填。"
        )

    # ============================================================
    # MicroAgent 创建与执行
    # ============================================================

    def _create_micro_agent(self):
        """创建并配置内部 MicroAgent。"""
        from .micro_agent import MicroAgent

        system_prompt = self._build_system_prompt()

        # 自动注入 sub_agent skill（提供 return_result/return_error）
        skills = ["sub_agent"] + list(self._available_skills)

        micro = MicroAgent(
            parent=self,
            name=self.name,
            available_skills=skills,
            system_prompt=system_prompt,
            md_skill_names=self._md_skill_names,
        )

        # 注入调用方指定的属性（如 _pinned_tab_id, notes, answer）
        for attr, value in self._micro_agent_attrs.items():
            setattr(micro, attr, value)

        # 绑定退出决策 hook
        micro._before_exit_hook = self._should_exit

        self._micro_agent = micro
        return micro

    async def execute(
        self,
        task: str,
        **kwargs,
    ) -> Any:
        """执行任务并返回结果。

        Args:
            task: 任务描述
            **kwargs: 透传给 MicroAgent.execute (persona, simple_mode 等)

        Returns:
            result_params 存在时返回 dict
            否则返回 MicroAgent 的原始结果
        """
        self._retries = 0
        self._validated_result = None

        micro = self._create_micro_agent()

        result = await micro.execute(
            run_label=self.name,
            task=task,
            **kwargs,
        )

        self._last_exit_action = getattr(micro, 'return_action_name', None)

        # 优先返回校验通过的结果，否则返回原始结果
        if self._validated_result is not None:
            return self._validated_result
        return result
