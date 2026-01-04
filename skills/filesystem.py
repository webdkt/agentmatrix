# skills/filesystem.py
import os
from pathlib import Path
from core.action import register_action


class FileSkillMixin:
    """
    文件系统技能包。
    需要宿主类 (Agent) 提供 private_workspace 和 current_workspace 属性。
    """

    def _resolve_path(self, workspace_root: Path, relative_path: str = ".") -> Path:
        """
        安全路径解析，防止路径穿越攻击

        Args:
            workspace_root: workspace 根目录 (Path 对象)
            relative_path: 相对路径，默认 "." 表示根目录

        Returns:
            解析后的绝对路径 (Path 对象)

        Raises:
            ValueError: 路径穿越检测或 workspace_root 为 None
        """
        # 1. 检查 workspace_root
        if workspace_root is None:
            raise ValueError("Workspace is not initialized. Please set workspace_root first.")

        # 2. 规范化根目录
        workspace_root = workspace_root.resolve()

        # 3. 拼接并规范化目标路径
        target_path = (workspace_root / relative_path).resolve()

        # 4. 安全检查：确保目标路径在 workspace_root 内部
        try:
            target_path.relative_to(workspace_root)
        except ValueError:
            raise ValueError(
                f"Security Alert: Path traversal detected. "
                f"Attempted to access {relative_path}, which is outside workspace."
            )

        return target_path

    # ========== Private Workspace Methods ==========

    @register_action(
        "列出私有工作区的文件。用于查看有哪些文件可用。",
        param_infos={
            "relative_path": "子目录路径，默认 '.' 表示根目录"
        }
    )
    async def list_private_file(self, relative_path: str = ".") -> str:
        """列出私有工作区中的文件和目录"""
        try:
            workspace = self.private_workspace
            target_dir = self._resolve_path(workspace, relative_path)

            if not target_dir.exists():
                return f"Directory not found: {relative_path}"

            items = []
            for item in target_dir.iterdir():
                marker = "[DIR] " if item.is_dir() else "[FILE]"
                items.append(f"{marker}{item.name}")

            return "\n".join(items) if items else "(Empty Directory)"

        except Exception as e:
            return f"Error listing private files: {str(e)}"

    @register_action(
        "读取私有工作区的文件内容。仅支持文本文件。",
        param_infos={
            "relative_path": "文件相对路径"
        }
    )
    async def read_private_file(self, relative_path: str) -> str:
        """读取私有工作区中的文本文件"""
        try:
            workspace = self.private_workspace
            file_path = self._resolve_path(workspace, relative_path)

            if not file_path.exists():
                return f"Error: File '{relative_path}' does not exist."

            if not file_path.is_file():
                return f"Error: '{relative_path}' is not a file."

            # 文件大小限制：50KB
            MAX_SIZE = 50 * 1024
            if file_path.stat().st_size > MAX_SIZE:
                return f"Error: File too large ({file_path.stat().st_size} bytes). Limit: {MAX_SIZE} bytes."

            return file_path.read_text(encoding='utf-8')

        except UnicodeDecodeError:
            return "Error: Binary file detected. Cannot read as text."
        except Exception as e:
            return f"Error reading private file: {str(e)}"

    @register_action(
        "写入内容到私有工作区的文件。",
        param_infos={
            "relative_path": "文件相对路径",
            "content": "要写入的文本内容"
        }
    )
    async def write_private_file(self, relative_path: str, content: str) -> str:
        """写入内容到私有工作区的文件"""
        try:
            workspace = self.private_workspace
            file_path = self._resolve_path(workspace, relative_path)

            # 自动创建父目录
            file_path.parent.mkdir(parents=True, exist_ok=True)

            file_path.write_text(content, encoding='utf-8')
            return f"Success: Written to private workspace '{relative_path}'"

        except Exception as e:
            return f"Error writing private file: {str(e)}"

    # ========== Shared Workspace Methods ==========

    @register_action(
        "列出共享工作区的文件。用于查看有哪些文件可用。",
        param_infos={
            "relative_path": "子目录路径，默认 '.' 表示根目录"
        }
    )
    async def list_shared_file(self, relative_path: str = ".") -> str:
        """列出共享工作区中的文件和目录"""
        try:
            workspace = self.current_workspace
            target_dir = self._resolve_path(workspace, relative_path)

            if not target_dir.exists():
                return f"Directory not found: {relative_path}"

            items = []
            for item in target_dir.iterdir():
                marker = "[DIR] " if item.is_dir() else "[FILE]"
                items.append(f"{marker}{item.name}")

            return "\n".join(items) if items else "(Empty Directory)"

        except Exception as e:
            return f"Error listing shared files: {str(e)}"

    @register_action(
        "读取共享工作区的文件内容。仅支持文本文件。",
        param_infos={
            "relative_path": "文件相对路径"
        }
    )
    async def read_shared_file(self, relative_path: str) -> str:
        """读取共享工作区中的文本文件"""
        try:
            workspace = self.current_workspace
            file_path = self._resolve_path(workspace, relative_path)

            if not file_path.exists():
                return f"Error: File '{relative_path}' does not exist."

            if not file_path.is_file():
                return f"Error: '{relative_path}' is not a file."

            # 文件大小限制：50KB
            MAX_SIZE = 50 * 1024
            if file_path.stat().st_size > MAX_SIZE:
                return f"Error: File too large ({file_path.stat().st_size} bytes). Limit: {MAX_SIZE} bytes."

            return file_path.read_text(encoding='utf-8')

        except UnicodeDecodeError:
            return "Error: Binary file detected. Cannot read as text."
        except Exception as e:
            return f"Error reading shared file: {str(e)}"

    @register_action(
        "写入内容到共享工作区的文件。",
        param_infos={
            "relative_path": "文件相对路径",
            "content": "要写入的文本内容"
        }
    )
    async def write_shared_file(self, relative_path: str, content: str) -> str:
        """写入内容到共享工作区的文件"""
        try:
            workspace = self.current_workspace
            file_path = self._resolve_path(workspace, relative_path)

            # 自动创建父目录
            file_path.parent.mkdir(parents=True, exist_ok=True)

            file_path.write_text(content, encoding='utf-8')
            return f"Success: Written to shared workspace '{relative_path}'"

        except Exception as e:
            return f"Error writing shared file: {str(e)}"