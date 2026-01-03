# core/cerebellum.py
import json
import textwrap
from core.log_util import AutoLoggerMixin
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

    async def negotiate(self, initial_intent: str, tools_manifest: str, contacts,  brain_callback) -> dict:
        """
        谈判循环：如果意图不清晰，Cerebellum 会反问 Brain。
        
        Args:
            initial_intent: Brain 最初的想法
            tools_manifest: 工具列表
            brain_callback: 一个异步函数，允许 Cerebellum 向 Brain 提问 (param: question_str) -> answer_str
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
        # 维护一个临时的谈判历史，避免 Brain 忘记自己刚才要做什么
        negotiation_history =[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": initial_intent}
        ]
        
        self.logger.debug(f"开始谈判：{initial_intent}")
        
        #print(f"准备分析大脑意图：{initial_intent}")
        
        max_turns = 5 # 防止两个模型在那儿没完没了地聊天
        
        for i in range(max_turns):
            # 1. 小脑思考：我现在还需要什么？
            # 这是一个特殊的 Prompt，要求小脑检查参数完整性
            
            
            # 小脑进行推理（这里用 fast model）
            response = await self.backend.think(messages=negotiation_history)
            reasoning_str= response['reasoning']
            reply_str= response['reply']
            
            #loop = asyncio.get_running_loop()
            # 把同步的 logger.debug 扔到线程池执行
            self.logger.debug(f"小脑思考：{reasoning_str}")
            self.logger.debug(f"小脑回复：{reply_str}")



            raw_content = response['reply'].replace("```json", "").replace("```", "").strip()
            
            try:
                decision = json.loads(raw_content)
                status = decision.get("status")
                
                if status == "READY":
                    return decision["action_json"]
                
                elif status == "NOT_FEASIBLE":
                    # 彻底放弃，返回错误动作
                    question = "Intent is not feasible."
                    # 记录这一轮对话
                    self.logger.debug(question)
                    answer = await brain_callback(question)
                    negotiation_history.append({"role": "assistant", "content": "Need clarification."})
                    negotiation_history.append({"role": "user", "content": answer})
                
                elif status == "ASK":
                    # === 关键点：反问 Brain ===
                    question = decision.get("question")
                    self.logger.debug(question)
                    
                    # 记录这一轮对话
                    
                    
                    # 调用回调函数，让 Brain 回答
                    # Brain 会基于它原始的 Context + 这里的 Question 来回答
                    answer = await brain_callback(question)
                    
                    self.logger.debug(question)
                    self.logger.debug('[Brain Reply]:' + answer)
                    negotiation_history.append({"role": "assistant", "content": question})
                    negotiation_history.append({"role": "user", "content": answer})
                    
                    # 继续下一轮循环
                    continue
                    
            except json.JSONDecodeError:
                if len(negotiation_history)>2:
                    negotiation_history.pop()
                
        return {"action": "_parse_failed", "params": {"error": "Negotiation timeout"}}