"""
Micro Agent: 临时任务专用的轻量级 Agent

设计理念：
- 每个子任务都是一个临时的 Micro Agent
- 简单的 think-negotiate-act 循环
- 无 Session 概念，每次执行都是独立的
- 类似函数调用：输入任务 -> 执行 -> 返回结果
- 可重复使用：一次初始化组件，多次执行不同任务
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Callable, Any
import json
import logging

from ..core.log_util import AutoLoggerMixin


class MicroAgent(AutoLoggerMixin):
    """
    临时任务专用的轻量级 Agent

    特点：
    1. 简单的 think-negotiate-act 循环
    2. 直接从 think 输出中识别 action 名字
    3. 通过 cerebellum 协商参数
    4. LLM 自主决定何时返回
    5. 可重复使用：一次设置组件，多次执行不同任务
    """

    _log_from_attr = "name"
    _custom_log_level = logging.DEBUG

    def __init__(
        self,
        brain: Any,
        cerebellum: Any,
        action_registry: Dict[str, Callable],
        name: Optional[str] = None,
        default_max_steps: int = 50
    ):
        """
        初始化 Micro Agent（一次性设置核心组件）

        Args:
            brain: LLM 接口（需要有 think 方法）
            cerebellum: 参数协商器（需要有 negotiate 方法）
            action_registry: action 注册表 {name: method}
            name: Agent 名称（可选，自动生成）
            default_max_steps: 默认最大步数
        """
        self.name = name or f"MicroAgent_{uuid.uuid4().hex[:8]}"

        # 核心组件（一次性设置，可重复使用）
        self.brain = brain
        self.cerebellum = cerebellum
        self.action_registry = action_registry

        # 默认配置
        self.default_max_steps = default_max_steps

        # 日志
        self.logger.info(f"Micro Agent {self.name} initialized")

    async def execute(
        self,
        persona: str,
        task: str,
        available_actions: List[str],
        task_context: Optional[Dict[str, Any]] = None,
        max_steps: Optional[int] = None
    ) -> str:
        """
        执行任务（可重复调用）

        Args:
            persona: 角色/身份描述（作为 system prompt）
            task: 任务描述
            available_actions: 可用的 action 名称列表
            task_context: 任务上下文（可选）
            max_steps: 最大步数（可选，默认使用 default_max_steps）

        Returns:
            str: 最终结果
        """
        # 设置本次执行的参数
        self.persona = persona
        self.task = task
        self.task_context = task_context or {}
        self.available_actions = available_actions
        self.max_steps = max_steps or self.default_max_steps

        # 重置执行状态
        self.messages = []
        self.step_count = 0
        self.result = None

        self.logger.info(f"Micro Agent {self.name} executing task: {task[:50]}...")

        try:
            # 1. 初始化对话
            self._initialize_conversation()

            # 2. 执行 think-negotiate-act 循环
            await self._run_loop()

            # 3. 返回结果
            self.logger.info(f"Micro Agent {self.name} completed in {self.step_count} steps")
            return self.result or "Task completed without explicit result"

        except Exception as e:
            self.logger.exception(f"Micro Agent {self.name} failed")
            return f"Error: {str(e)}"

    def _initialize_conversation(self):
        """初始化对话历史"""
        # 1. System Prompt
        system_prompt = self._build_system_prompt()
        self.messages.append({"role": "system", "content": system_prompt})

        # 2. 任务描述
        task_message = self._format_task_message()
        self.messages.append({"role": "user", "content": task_message})

    def _build_system_prompt(self) -> str:
        """构建 System Prompt"""
        prompt = f"""{self.persona}

You have access to the following actions:
{self._format_actions_list()}

Instructions:
1. Think step by step about what needs to be done
2. When you need to use an action, include the action name in your response
3. The system will negotiate parameters with you if needed
4. When you have completed the task, use the action: finish_task
5. Provide your final result when calling finish_task

Available actions: {', '.join(self.available_actions)}
"""
        return prompt

    def _format_actions_list(self) -> str:
        """格式化可用 actions 列表"""
        lines = []
        for action_name in self.available_actions:
            if action_name in self.action_registry:
                method = self.action_registry[action_name]
                # 尝试获取描述
                desc = getattr(method, "_action_desc", "No description")
                lines.append(f"- {action_name}: {desc}")
        return "\n".join(lines)

    def _format_task_message(self) -> str:
        """格式化任务消息"""
        msg = f"[TASK]\n{self.task}\n"

        if self.task_context:
            msg += f"\n[CONTEXT]\n"
            msg += json.dumps(self.task_context, ensure_ascii=False, indent=2)

        msg += "\n\nPlease complete this task step by step."
        return msg

    async def _run_loop(self):
        """执行主循环"""
        for self.step_count in range(1, self.max_steps + 1):
            self.logger.debug(f"Step {self.step_count}/{self.max_steps}")

            # 1. Think
            thought = await self._think()
            self.logger.debug(f"Thought: {thought[:200]}...")

            # 2. 识别 action
            action_name = self._detect_action(thought)

            if action_name == "finish_task":
                # 任务完成，提取结果并退出
                self.result = self._extract_final_result(thought)
                break

            elif action_name:
                # 执行 action
                try:
                    result = await self._execute_action(action_name, thought)
                    self._add_message("assistant", thought)
                    self._add_message("user", f"Action '{action_name}' executed. Result: {result}")
                except Exception as e:
                    self.logger.exception(f"Action {action_name} failed")
                    self._add_message("assistant", thought)
                    self._add_message("user", f"Action '{action_name}' failed with error: {str(e)}")

            else:
                # 没有检测到 action，只是思考
                self._add_message("assistant", thought)
                # 提示需要采取行动
                self._add_message("user", "Please use an available action to proceed.")

        else:
            # 超过最大步数
            self.logger.warning(f"Reached max steps ({self.max_steps})")
            self.result = f"Task exceeded maximum steps ({self.max_steps})"

    async def _think(self) -> str:
        """调用 Brain 进行思考"""
        response = await self.brain.think(self.messages)
        return response['reply']

    def _detect_action(self, thought: str) -> Optional[str]:
        """
        从思考内容中检测 action

        策略：
        1. 查找可用的 action 名字
        2. 返回第一个匹配到的 action
        3. 如果没有匹配，返回 None
        """
        thought_lower = thought.lower()

        # 按优先级检查（避免部分匹配问题）
        # 先检查较长的名字
        sorted_actions = sorted(
            self.available_actions,
            key=lambda x: len(x),
            reverse=True
        )

        for action_name in sorted_actions:
            if action_name.lower() in thought_lower:
                return action_name

        return None

    async def _execute_action(self, action_name: str, thought: str) -> Any:
        """
        执行 action

        流程：
        1. 获取 action 方法和参数 schema
        2. 通过 cerebellum 协商参数
        3. 调用方法
        """
        # 1. 获取方法
        if action_name not in self.action_registry:
            raise ValueError(f"Action '{action_name}' not found in registry")

        method = self.action_registry[action_name]

        # 2. 获取参数信息
        param_schema = getattr(method, "_action_param_infos", {})

        # 3. 如果有参数，通过 cerebellum 协商
        if param_schema:
            # 构造参数 schema 给 cerebellum
            action_def = {
                "action": action_name,
                "params": param_schema
            }

            # 通过 cerebellum 协商参数
            async def brain_clarification(question: str) -> str:
                temp_msgs = self.messages.copy()
                temp_msgs.append({"role": "assistant", "content": thought})
                temp_msgs.append({"role": "user", "content": f"[PARAMETER CLARIFICATION] {question}"})
                response = await self.brain.think(temp_msgs)
                return response['reply']

            action_json = await self.cerebellum.negotiate(
                initial_intent=thought,
                tools_manifest=json.dumps(action_def),
                contacts="",  # Micro Agent 不发邮件
                brain_callback=brain_clarification
            )

            params = action_json.get("params", {})
        else:
            params = {}

        # 4. 执行方法
        self.logger.debug(f"Executing {action_name} with params: {params}")
        result = await method(**params)

        return result

    def _extract_final_result(self, thought: str) -> str:
        """
        从 finish_task 的思考中提取最终结果

        策略：
        1. 如果有 "Result:" 标记，提取后面的内容
        2. 否则返回整个 thought
        """
        if "Result:" in thought:
            return thought.split("Result:", 1)[1].strip()
        elif "result:" in thought:
            return thought.split("result:", 1)[1].strip()
        return thought

    def _add_message(self, role: str, content: str):
        """添加消息到对话历史"""
        self.messages.append({"role": role, "content": content})


# ============================================================================
# 通用的 finish_task action
# ============================================================================

def finish_task_action(result: str = "") -> str:
    """
    通用的"完成任务"action

    Micro Agent 调用此 action 表示任务完成，并返回结果
    """
    return result if result else "Task completed"


# finish_task 的注册信息（用于添加到 action_registry）
FINISH_TASK_INFO = {
    "description": "完成任务并返回最终结果。当你觉得任务已经完成时，调用此 action。",
    "param_infos": {
        "result": "最终结果的描述（可选）"
    },
    "method": finish_task_action
}
