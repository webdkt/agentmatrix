import json
from agents.base import BaseAgent
from tools.basic import TOOL_MAP

class SecretaryAgent(BaseAgent):
    async def step(self, session):
        await self.emit("THINKING", "正在解析指令...")
        
        # SLM 应该返回 JSON
        response = await self.backend.chat(self.name, session.history)
        
        try:
            cmd = json.loads(response)
            tool_name = cmd.get("tool")
            args = cmd.get("args")
            
            await self.emit("TOOL_START", f"执行工具: {tool_name}", payload=args)
            
            # 执行工具
            if tool_name in TOOL_MAP:
                result = TOOL_MAP[tool_name](**args)
            else:
                result = "Tool not found"
                
            reply_body = f"Tool executed. Result: {result} (file_content)"
            
            # 秘书总是回复发起人，且这通常是任务终点(对于秘书而言)
            await self.send_email(session.original_sender, "Tool Result", reply_body, session, expect_reply=False)
            
        except Exception as e:
             await self.send_email(session.original_sender, "Error", str(e), session, expect_reply=False)