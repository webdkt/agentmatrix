from agents.base import BaseAgent
from core.session import TaskSession
import json
class StatefulAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)
        # 这就是那个“动态文档”，可以是 JSON，也可以是 Markdown
        self.project_state = {
            "objective": "",
            "tasks": [],
            "key_findings": []
        }

    async def step(self, session: TaskSession):
        # 获取最新的一封信（导致这次激活的那封）
        incoming_mail = session.history[-1]['content']
        
        # === Phase 1: State Update (只更新记忆，不发信) ===
        update_prompt = f"""
        当前状态: {json.dumps(self.project_state)}
        收到消息: {incoming_mail}
        
        任务:
        1. 根据消息更新任务状态 (TODO -> DONE)。
        2. 将关键结果摘要写入 key_findings。
        3. 如果有新问题，添加到 tasks。
        
        输出: 仅输出更新后的 JSON 状态。
        """
        new_state_json = await self.backend.chat(self.name, [{"role": "user", "content": update_prompt}])
        
        # 更新内存
        try:
            self.project_state = json.loads(new_state_json)
            # 存入数据库快照，方便回溯
            self.save_state_snapshot() 
        except:
            print("State update failed")

        # === Phase 2: Action Decision (只看状态，不看历史邮件) ===
        action_prompt = f"""
        当前项目状态: {json.dumps(self.project_state)}
        
        任务:
        基于当前状态，判断下一步该做什么？
        - 如果所有任务完成，回复用户。
        - 如果有 OPEN 的任务，给相应的 Worker 发邮件。
        
        输出: [Action: EMAIL] ...
        """
        response = await self.backend.chat(self.name, [{"role": "user", "content": action_prompt}])
        
        # ... 解析 response 并发信 (同 WorkerAgent) ...
        
        # === Phase 3: Context Clearing ===
        # 极其激进的策略：清空 Session History，只保留最新的状态
        # 因为所有必要信息都已经“沉淀”到 project_state 里了
        session.history = [] 