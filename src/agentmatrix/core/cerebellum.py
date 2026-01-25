# core/cerebellum.py
import json
import textwrap
from ..core.log_util import AutoLoggerMixin
import logging

class Cerebellum(AutoLoggerMixin):
    _log_from_attr = "log_name"  # 日志名字来自 self.log_name 属性
    _custom_log_level = logging.DEBUG

    def __init__(self, backend_client, agent_name):
        self.backend = backend_client
        self.agent_name = agent_name
        self.log_name = f"{agent_name}(Cerebellum)"

    async def think(self, messages):
        return await self.backend.think(messages)

    async def parse_action_params(
        self,
        intent: str,
        action_name: str,
        param_schema: dict,
        brain_callback
    ) -> dict:
        """
        解析单个 action 的参数

        Args:
            intent: Brain 的原始意图（thought）
            action_name: 要执行的 action 名称（已知）
            param_schema: 这个 action 的参数定义 {param_name: description}
            brain_callback: 向 Brain 提问的回调函数

        Returns:
            {"action": action_name, "params": {...}}
        """
        # 格式化参数定义
        param_list = []
        for param_name, param_desc in param_schema.items():
            param_list.append(f"- {param_name}: {param_desc}")
        param_def = "\n".join(param_list)

        system_prompt = textwrap.dedent(f"""
            You are the Parameter Parser. Your job is to extract parameters for a specific action from the user's intent.

            [Action to Execute]: {action_name}

            [Required Parameters]:
            {param_def}

            [Instructions]:
            1. Analyze the intent carefully and extract ALL required parameters
            2. If the intent contains all required parameters, format them as a JSON object
            3. DECISION:
               - If READY: Output JSON {{"status": "READY", "params": {{"param1": "value1", "param2": "value2", ...}}}}
               - If MISSING PARAM: Output JSON {{"status": "ASK", "question": "What is the value for [param_name]?"}}
               - If AMBIGUOUS: Output JSON {{"status": "ASK", "question": "Clarification needed for [param_name]..."}}

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

            self.logger.debug(f"小脑思考：{reasoning_str}")
            self.logger.debug(f"小脑回复：{reply_str}")

            raw_content = response['reply'].replace("```json", "").replace("```", "").strip()

            try:
                decision = json.loads(raw_content)
                status = decision.get("status")

                if status == "READY":
                    params = decision.get("params", {})
                    self.logger.debug(f"参数解析成功：{params}")
                    return {
                        "action": action_name,
                        "params": params
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

    async def negotiate_deprecated(self, initial_intent: str, tools_manifest: str, contacts, brain_callback) -> dict:
        """
        [DEPRECATED] 旧的协商方法，用于选择 action 并解析参数

        保留用于向后兼容，建议使用 parse_action_params 代替
        """
        system_prompt = textwrap.dedent(f"""
            You are the Interface Manager (Cerebellum). Your job is to convert User Intent into a Function Call JSON.

            [Available Tools]:
            {tools_manifest}

            [Available Email Receipients]:
            {contacts}

            [Instructions]:
            1. Identify the tool the user wants to use.
            2. Check if ALL required parameters for that tool are present in the Intent. Rview Intent carefully, find all required parameters and form a proper JSON as output.
            3. DECISION:
               - If READY: Output JSON `{{ "status": "READY", "action_json": {{ "action": "name", "params": {{...}} }} }}`
               - If MISSING PARAM: Output JSON `{{ "status": "ASK", "question": "What is the value for [param_name]?" }}`
               - If AMBIGUOUS: Output JSON `{{ "status": "ASK", "question": "whatever need to be clarified" }}`
               - If Not fesible: Output JSON `{{ "status": "NOT_FEASIBLE", "reason": "No matching tool found." }}`

            Output ONLY valid JSON.
            """)

        initial_intent = textwrap.dedent(f"""[User Intent]:
            {initial_intent}
        """)
        negotiation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_intent}
        ]

        self.logger.debug(f"开始谈判（已弃用）：{initial_intent}")

        max_turns = 5

        for i in range(max_turns):
            response = await self.backend.think(messages=negotiation_history)
            reasoning_str = response['reasoning']
            reply_str = response['reply']

            self.logger.debug(f"小脑思考：{reasoning_str}")
            self.logger.debug(f"小脑回复：{reply_str}")

            raw_content = response['reply'].replace("```json", "").replace("```", "").strip()

            try:
                decision = json.loads(raw_content)
                status = decision.get("status")

                if status == "READY":
                    return decision["action_json"]

                elif status == "NOT_FEASIBLE":
                    question = "Intent is not feasible."
                    self.logger.debug(question)
                    answer = await brain_callback(question)
                    negotiation_history.append({"role": "assistant", "content": "Need clarification."})
                    negotiation_history.append({"role": "user", "content": answer})

                elif status == "ASK":
                    question = decision.get("question")
                    self.logger.debug(question)

                    answer = await brain_callback(question)

                    self.logger.debug(question)
                    self.logger.debug('[Brain Reply]:' + answer)
                    negotiation_history.append({"role": "assistant", "content": question})
                    negotiation_history.append({"role": "user", "content": answer})

                    continue

            except json.JSONDecodeError:
                if len(negotiation_history) > 2:
                    negotiation_history.pop()

        return {"action": "_parse_failed", "params": {"error": "Negotiation timeout"}}
