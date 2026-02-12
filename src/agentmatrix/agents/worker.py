"!!! 过时待删除!!!"
from ..agents.base import BaseAgent

class WorkerAgent(BaseAgent):
    async def step(self, session):
        await self.emit("THINKING", "正在思考...")
        
        # 调用 Mock LLM
        response = await self.brain.think(self.name, session.history)
        
        # 简单的协议解析 (Action Protocol)
        # 格式: [Action: EMAIL] To: X | Subject: Y | Body: Z
        # 格式: [Action: REPLY] Body
        
        if "[Action: EMAIL]" in response:
            # 解析 (简化版字符串操作)
            content = response.split("]", 1)[1].strip()
            parts = {p.split(":")[0].strip(): p.split(":")[1].strip() for p in content.split("|")}
            
            to = parts.get("To")
            subj = parts.get("Subject")
            body = parts.get("Body")
            
            session.history.append({"role": "assistant", "content": response})
            # 这里认为是中间步骤，expect_reply = True
            await self.send_email(to, subj, body, session, expect_reply=True)
            
        elif "[Action: REPLY]" in response:
            body = response.split("REPLY]", 1)[1].strip()
            # 最终回复
            await self.send_email(session.original_sender, "Re: Task", body, session, expect_reply=False)