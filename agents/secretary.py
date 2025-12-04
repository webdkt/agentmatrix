import json
from agents.base import BaseAgent
from tools.basic import TOOL_MAP

class SecretaryAgent(BaseAgent):
    def __init__(self, profile,project_context ):
        super().__init__(profile)
        self.project = project_context


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


    def read_file(self, file_path):
        # 1. 安全检查 & 路径转换
        try:
            safe_path = self.project.resolve_path(file_path)
        except PermissionError as e:
            return f"Error: {str(e)}"

        # 2. 执行操作
        try:
            with open(safe_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return "Error: File not found."

    def list_files(self, sub_dir="."):
        # 列出文件时，Agent 看到的应该是相对路径
        safe_path = self.project.resolve_path(sub_dir)
        files = []
        for p in Path(safe_path).glob("*"):
            files.append(p.name) # 或者 p.relative_to(self.project.root)
        return str(files)