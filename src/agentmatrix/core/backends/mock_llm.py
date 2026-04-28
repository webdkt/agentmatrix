import asyncio
import json

class MockLLM:
    """模拟 LLM，根据输入关键词决定输出，方便测试流程"""
    
    async def chat(self, role: str, history: list) -> str:
        await asyncio.sleep(1.0) # 模拟思考时间
        
        last_msg = history[-1]["content"].lower()
        
        # === 模拟 Planner 的逻辑 ===
        if role == "Planner":
            if "start_task" in last_msg:
                # 收到用户新任务 -> 派活给 Coder
                return "[Action: EMAIL] To: Coder | Subject: Task | Body: 请帮我读取 data.csv 并分析数据。"
            elif "done" in last_msg:
                # 收到 Coder 回复 -> 汇报给 User
                return "[Action: REPLY] 任务已完成，数据分析结果如下..."

        # === 模拟 Coder 的逻辑 ===
        elif role == "Coder":
            if "读取" in last_msg and "secretary" not in last_msg:
                # 收到任务，发现需要读文件 -> 问秘书
                return "[Action: EMAIL] To: Secretary | Subject: Help | Body: 请帮我读取文件 data.csv"
            elif "file_content" in last_msg:
                # 收到秘书回信 -> 完成任务
                return "[Action: REPLY] 我已读取文件，分析完毕，结果是 Done。"
                
        # === 模拟 Secretary (SLM) 的逻辑 ===
        elif role == "Secretary":
            if "读取文件" in last_msg:
                return json.dumps({"tool": "read_file", "args": {"path": "data.csv"}})
            
        return "[Action: REPLY] I am thinking..."