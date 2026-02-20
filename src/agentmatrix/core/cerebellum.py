# core/cerebellum.py
import json
import textwrap
from ..core.log_util import AutoLoggerMixin
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.log_config import LogConfig

class Cerebellum(AutoLoggerMixin):
    _custom_log_level = logging.DEBUG

    def __init__(self, backend_client, agent_name: str,
                 parent_logger: Optional[logging.Logger] = None,
                 log_config: Optional['LogConfig'] = None):
        """
        小脑 - 负责参数解析和协商

        Args:
            backend_client: LLM客户端
            agent_name: 所属Agent的名称
            parent_logger: 父组件的logger（用于共享日志）
            log_config: 日志配置
        """
        self.backend = backend_client
        self.agent_name = agent_name

        # 使用父 logger（不创建独立日志文件）
        self._parent_logger = parent_logger
        self._log_config = log_config
        self._log_prefix_template = log_config.prefix if log_config else ""

    async def think(self, messages):
        return await self.backend.think(messages)

    async def parse_action_params(
        self,
        intent: str,
        action_name: str,
        param_schema: dict,
        brain_callback,
        task_context: str = ""
    ) -> dict:
        """
        解析单个 action 的参数

        Args:
            intent: Brain 的原始意图（thought）
            action_name: 要执行的 action 名称（已知）
            param_schema: 这个 action 的参数定义 {param_name: description}
            brain_callback: 向 Brain 提问的回调函数
            task_context: 任务上下文信息（第几个 action，共几个等）

        Returns:
            {"action": action_name, "params": {...}}
        """
        # 格式化参数定义
        param_list = []
        for param_name, param_desc in param_schema.items():
            param_list.append(f"- {param_name}: {param_desc}")
        param_def = "\n".join(param_list)
        
        system_prompt = textwrap.dedent(f"""
            You are the Parameter Parser. Your job is to :
            1. Determine if user really wants to execute action "{action_name}"
            2. If yes, extract parameters for action "{action_name}" from the user's intent.

            [IMPORTANT] The user's intent may contain multiple actions. You should ONLY focus on:
            {task_context}

            [Required Parameters for {action_name}]:
            {param_def}

            [Instructions]:
            0. Always judge first, if user wants to run "{action_name}"
            1. Look at the intent and find information related to "{action_name}"
            2. IGNORE information for other actions
            3. Extract ALL required parameters for "{action_name}"
            4. DECISION:
               - If NOT TO run: Output JSON {{"status": "NOT_TO_RUN", "reason": "reason_for_not_running"}}
               - If READY: Output JSON {{"status": "READY", "params": {{"param1": "value1", "param2": "value2", ...}}}}
               - If MISSING: Output JSON {{"status": "ASK", "question": "What is the value for [param_name] of {action_name}?"}}
               - If AMBIGUOUS: Output JSON {{"status": "ASK", "question": "Clarification needed for [param_name] of {action_name}..."}}

            Output ONLY valid JSON.
        """)

        negotiation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"[Intent]\n{intent}"}
        ]

        self.logger.debug(f"开始解析参数，action={action_name}")

        max_turns = 5

        for i in range(max_turns):
            response = await self.backend.think(messages=negotiation_history)
            reasoning_str = response['reasoning']
            reply_str = response['reply']

            #self.logger.debug(f"小脑思考：{reasoning_str}")
            #self.logger.debug(f"小脑回复：{reply_str}")

            raw_content = response['reply'].replace("```json", "").replace("```", "").strip()

            try:
                decision = json.loads(raw_content)
                status = decision.get("status")

                if status == "READY":
                    params = decision.get("params", {})
                    #self.logger.debug(f"参数解析成功：{params}")
                    return {
                        "action": action_name,
                        "params": params
                    }
                elif status == "NOT_TO_RUN":
                    reason = decision.get("reason", "Action not to be executed")
                    self.logger.debug(f"Action 不执行：{reason}")
                    return {
                        "action": action_name,
                        "params": "NOT_TO_RUN",
                        "reason": reason
                    }

                elif status == "ASK":
                    # 反问 Brain
                    question = decision.get("question")
                    self.logger.debug(f"需要澄清：{question}")

                    answer = await brain_callback(question)

                    self.logger.debug(f"[Brain Reply]: {answer}")
                    negotiation_history.append({"role": "assistant", "content": question})
                    negotiation_history.append({"role": "user", "content": answer})

                    # 继续下一轮循环
                    continue

            except json.JSONDecodeError:
                self.logger.warning(f"JSON 解析失败，尝试恢复")
                if len(negotiation_history) > 2:
                    negotiation_history.pop()

        return {"action": action_name, "params": {}}

    
