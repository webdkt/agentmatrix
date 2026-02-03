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
        default_max_steps: int = 50,
        return_action_name = None
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
        self.messages: List[Dict] = []  # 对话历史
        # 日志
        self.logger.info(f"Micro Agent {self.name} initialized")

    async def execute(
        self,
        persona: str,
        task: str,
        available_actions: List[str],
        max_steps: Optional[int] = None,
        initial_history: Optional[List[Dict]] = None,
        result_params: Optional[Dict[str, str]] = None,
        yellow_pages: Optional[str] = None
    ) -> Any:
        """
        执行任务（可重复调用）

        Args:
            persona: 角色/身份描述（作为 system prompt）
            task: 任务描述
            available_actions: 可用的 action 名称列表
            max_steps: 最大步数（可选，默认使用 default_max_steps）
            initial_history: 初始对话历史（用于恢复记忆，可选）
            result_params: 返回值参数描述（可选），用于指定 finish_task 的参数结构
            yellow_pages: 黄页信息（可选），包含其他agent的描述和如何调用它们

        Returns:
            Any: 最终结果
                 - 如果 result_params 为 None，返回字符串（向后兼容）
                 - 如果有 result_params，返回 Dict[str, Any]
                 - 如果出错或超时，返回 None 或 {"error": str}
        """
        # 设置本次执行的参数
        self.persona = persona
        self.task = task
        self.available_actions = available_actions
        self.yellow_pages = yellow_pages
        self.max_steps = max_steps or self.default_max_steps

        # 重置执行状态
        self.step_count = 0
        self.result = None

        # 确保 finish_task 在 action_registry 中
        if "finish_task" not in self.action_registry:
            self.action_registry["finish_task"] = finish_task

        # 动态更新 finish_task 的元数据
        if result_params:
            # 更新参数描述
            finish_task._action_param_infos = result_params

            # 动态生成 description，包含参数的自然语言描述
            param_descriptions = ", ".join(result_params.values())
            finish_task._action_desc = (
                f"完成任务并返回最终结果。需要提供：{param_descriptions}"
            )
        else:
            # 默认模式
            finish_task._action_param_infos = {"result": "最终结果的描述（可选）"}
            finish_task._action_desc = "完成任务并返回最终结果。当你觉得任务已经完成时，调用此 action。"

        # 确保 finish_task 在可用列表中
        if "finish_task" not in available_actions:
            available_actions.append("finish_task")

        # 恢复或初始化对话历史
        if initial_history:
            # 恢复记忆：复制历史记录
            self.messages = initial_history.copy()
            self.logger.info(f"Micro Agent {self.name} restoring memory with {len(initial_history)} messages")
            # 添加新的任务输入
            self._add_message("user", f"\n[NEW INPUT]\n{self._format_task_message()}")
        else:
            # 新对话：初始化
            self.messages = []
            self._initialize_conversation()

        self.logger.info(f"Micro Agent {self.name} executing task:")
        self.logger.debug(f"{self.messages}")

        try:
            # 执行 think-negotiate-act 循环
            await self._run_loop()

            # 返回结果
            self.logger.info(f"Micro Agent {self.name} completed in {self.step_count} steps")
            return self.result

        except Exception as e:
            self.logger.exception(f"Micro Agent {self.name} failed")
            return {"error": str(e)}

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
        prompt = f"""你是 {self.persona}

### 操作环境 (The Cockpit)

你目前在一个文本化的系统环境中存在。你是这个系统的意识部分，系统则是你的身体。

**基本物理规则:**
1. 你是**基于信号**的实体。你不会持续存在，你只会**接收到信号**时**醒来**。
2. 你需要**生成一个明确的动作信号**来**完成你的意图**。
3. 一旦你发出动作信号，你将**冻结**并等待**身体**返回执行结果的信号（反馈）。
4. 你的身体是强大的，但它**无法感知**你的对话历史或思考。除非你明确地告诉它。
5. 身体每次只能执行一个action, 需要你明确的告诉它是哪一个。
6. 你可以有复杂的思考和规划，但只会客观冷静的观察评估action的真实结果，根据动作的实际结果而不是期望来决定你的下一步计划。

### 你的工具箱 (可用action)

{self._format_actions_list()}

"""

        # 如果提供了黄页信息，添加黄页部分
        if self.yellow_pages:
            prompt += f"""### 黄页（你的同事）

{self.yellow_pages}
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
        msg = f"[NEW INPUT]\n{self.task}\n"

        return msg

    async def _run_loop(self):
        """执行主循环 - 支持批量 action 执行"""
        for self.step_count in range(1, self.max_steps + 1):
            self.logger.debug(f"Step {self.step_count}/{self.max_steps}")

            # 1. Think
            thought = await self._think()
            self.logger.debug(f"Thought: {thought[:200]}...")

            # 2. 检测 actions（多个，保持顺序）
            action_names = self._detect_actions(thought)

            # 3. 没有检测到 action
            if not action_names:
                self._add_message("assistant", thought)
                self._add_message("user", "Please use an available action to proceed.")
                continue

            self.logger.debug(f"Detected actions: {action_names}")

            # 4. 记录 assistant 的思考（只记录一次）
            self._add_message("assistant", thought)

            # 5. 顺序执行所有 actions
            execution_results = []
            should_break_loop = False  # 标记是否需要退出主循环

            for action_name in action_names:
                # === 处理特殊 actions ===
                if action_name == "finish_task":
                    # 执行 finish_task
                    result = await self._execute_action("finish_task", thought)
                    self.result = result
                    self.return_action_name = "finish_task"
                    should_break_loop = True
                    # 不记录 execution_results，直接退出
                    break  # ← 退出 for action_names 循环

                elif action_name == "rest_n_wait":
                    # rest_n_wait 不需要执行，直接等待
                    self.return_action_name = "rest_n_wait"
                    should_break_loop = True
                    break  # ← 退出 for action_names 循环

                # === 执行普通 actions ===
                else:
                    try:
                        result = await self._execute_action(action_name, thought)
                        execution_results.append(f"[{action_name} 执行成功]: {result}")
                        self.logger.debug(f"✅ {action_name} succeeded")
                    except Exception as e:
                        error_msg = str(e)
                        execution_results.append(f"[{action_name} 执行失败]: {error_msg}")
                        self.logger.warning(f"❌ {action_name} failed: {error_msg}")

            # 6. 反馈给 Brain（只有普通 actions 才反馈）
            if execution_results:
                combined_result = "\n".join(execution_results)
                self._add_message("user", combined_result)
                self.logger.debug(f"Batch execution result:\n{combined_result}")

            # 7. 检查是否需要退出主循环
            if should_break_loop:
                break

        else:
            # 超过最大步数
            self.logger.warning(f"Reached max steps ({self.max_steps})")
            self.result = None

    async def _think(self) -> str:
        """调用 Brain 进行思考"""
        response = await self.brain.think(self.messages)
        return response['reply']

    def _detect_actions(self, thought: str) -> List[str]:
        """
        使用正则表达式检测多个 action（完整单词匹配）

        即使 action name 前后有中文，也能正确匹配

        Example:
            "我要用web_search搜索" → ["web_search"]
            "使用send_email发送" → ["send_email"]
            "先搜索，然后完成" → ["web_search", "finish_task"]
        """
        import re

        # 正则：匹配连续的字母、下划线、数字（标识符格式）
        # [a-zA-Z_]: 必须以字母或下划线开头
        # [a-zA-Z0-9_]*: 后续可以是字母、数字、下划线
        action_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)'

        # 提取所有匹配的字符串
        matches = re.finditer(action_pattern, thought)

        # 按出现顺序记录 (position, action_name)
        detected = []
        seen = set()  # 去重（保留第一次出现）

        for match in matches:
            action_name = match.group(1)
            position = match.start()

            # 转小写（action names 通常是 snake_case）
            action_name_lower = action_name.lower()

            # 只保留有效的 action names
            if action_name_lower in self.available_actions:
                if action_name_lower not in seen:
                    detected.append((position, action_name_lower))
                    seen.add(action_name_lower)

        # 按出现位置排序
        detected.sort(key=lambda x: x[0])

        # 返回 action 名称列表
        return [action for _, action in detected]

    async def _execute_action(self, action_name: str, thought: str) -> Any:
        """
        执行 action

        流程：
        1. 获取 action 方法和参数 schema
        2. 通过 cerebellum 解析参数
        3. 调用方法
        """
        # 1. 获取方法
        if action_name not in self.action_registry:
            raise ValueError(f"Action '{action_name}' not found in registry")

        method = self.action_registry[action_name]

        # 2. 获取参数信息
        param_schema = getattr(method, "_action_param_infos", {})

        # 3. 如果有参数，通过 cerebellum 解析
        if param_schema:
            # 通过 cerebellum 解析参数
            async def brain_clarification(question: str) -> str:
                temp_msgs = self.messages.copy()
                temp_msgs.append({"role": "assistant", "content": thought})
                temp_msgs.append({"role": "user", "content": f"[PARAMETER CLARIFICATION] {question}"})
                response = await self.brain.think(temp_msgs)
                return response['reply']

            action_json = await self.cerebellum.parse_action_params(
                intent=thought,
                action_name=action_name,
                param_schema=param_schema,
                brain_callback=brain_clarification
            )

            params = action_json.get("params", {})
        else:
            params = {}

        # 4. 执行方法
        self.logger.debug(f"Executing {action_name} with params: {params}")
        result = await method(**params)

        return result

    def _add_message(self, role: str, content: str):
        """添加消息到对话历史"""
        self.messages.append({"role": role, "content": content})

    def get_history(self) -> List[Dict]:
        """
        获取完整的对话历史

        Returns:
            List[Dict]: 完整的对话历史（包括初始历史 + 新增对话）
        """
        return self.messages


# ============================================================================
# 通用的 finish_task action
# ============================================================================

async def finish_task(**kwargs):
    """
    [TERMINAL ACTION] 完成任务并返回最终结果

    当你认为任务已经完成时，调用此 action。
    根据提供的参数返回结构化结果。

    Returns:
        - 如果只有一个 result 参数：返回字符串（向后兼容）
        - 如果有多个参数：返回字典
    """
    # 如果是简单模式（只有一个 result），返回字符串以保持兼容
    if len(kwargs) == 1 and "result" in kwargs:
        return kwargs["result"]
    # 否则返回字典
    return kwargs


# 附加基础元数据
finish_task._is_action = True
finish_task._action_desc = "完成任务并返回最终结果。当你觉得任务已经完成时，调用此 action。"
finish_task._action_param_infos = {"result": "最终结果的描述（可选）"}


# finish_task 的注册信息（用于添加到 action_registry）
FINISH_TASK_INFO = {
    "description": finish_task._action_desc,
    "param_infos": finish_task._action_param_infos,
    "method": finish_task
}
