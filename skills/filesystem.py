# skills/filesystem.py
import os
import shutil
from core.action import register_action, ActionType

class FileSkillMixin:
    """
    文件系统技能包。
    需要宿主类 (Agent) 提供 self.workspace_root 属性。
    """

    def _resolve_path(self, filename: str) -> str:
        """安全路径解析，防止 ../../ 越权访问"""
        if not hasattr(self, 'workspace_root') or not self.workspace_root:
            # 如果 Agent 没有被分配 workspace，默认使用当前目录下的 workspace
            self.workspace_root = os.path.abspath("./matrix_workspace")
        
        os.makedirs(self.workspace_root, exist_ok=True)
        
        # 拼接并获取绝对路径
        full_path = os.path.abspath(os.path.join(self.workspace_root, filename))
        
        # 安全检查：确保解析后的路径依然在 workspace_root 内部
        if not full_path.startswith(os.path.abspath(self.workspace_root)):
            raise ValueError(f"Security Alert: Access denied for path {filename}")
        
        return full_path

    @register_action("列出当前工作区的文件。用于查看有哪些文件可用。", ActionType.SYNC, param_infos={
        "directory": "子目录名称，默认为空字符串表示根目录"
    })
    async def list_files(self, directory: str = ""):
        try:
            target_dir = self._resolve_path(directory)
            if not os.path.exists(target_dir):
                return "Directory not found."
            
            items = os.listdir(target_dir)
            # 区分文件和文件夹
            result = []
            for item in items:
                path = os.path.join(target_dir, item)
                msg = f"[DIR]  {item}" if os.path.isdir(path) else f"[FILE] {item}"
                result.append(msg)
            
            return "\n".join(result) if result else "(Empty Directory)"
        except Exception as e:
            return f"Error listing files: {str(e)}"

    @register_action("读取文件内容。注意：只读取文本文件。", ActionType.SYNC, param_infos={
        "filename": "文件名 (相对路径)"
    })
    async def read_file(self, filename: str):
        try:
            file_path = self._resolve_path(filename)
            if not os.path.exists(file_path):
                return f"Error: File '{filename}' does not exist."
            
            # 简单的防爆读取：限制最大读取 50KB，防止 Context 爆炸
            MAX_SIZE = 50 * 1024 
            if os.path.getsize(file_path) > MAX_SIZE:
                return f"Error: File is too large ({os.path.getsize(file_path)} bytes). Please define a 'head' or 'tail' tool to read partial content."

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            return "Error: Binary file detected. Cannot read as text."
        except Exception as e:
            return f"Error reading file: {str(e)}"

    @register_action("写入内容到文件。如果文件存在则覆盖。", ActionType.SYNC, param_infos={
        "filename": "文件名 (相对路径)",
        "content": "要写入的文本内容"
    })
    async def write_file(self, filename: str, content: str):
        try:
            file_path = self._resolve_path(filename)
            # 自动创建父目录
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Success: Written to {filename}"
        except Exception as e:
            return f"Error writing file: {str(e)}"