"""
File Skill - 文件操作技能（新架构）

特点：
- 简化版本，包含核心文件操作功能
- self 始终指向 MicroAgent（拥有 working_context 等属性）
- 不需要判断 root_agent，直接访问 self 的属性
"""

import os
import platform
from typing import Optional
from ..core.action import register_action
from .registry import register_skill


@register_skill("file")
class FileSkillMixin:
    """
    File Operation Skill Mixin（新架构）

    提供：
    - list_dir: 列出目录
    - read: 读取文件
    - write: 写入文件
    - search_file: 搜索文件
    - bash: 执行命令
    """

    @register_action(
        description="列出目录内容。支持单层或递归列出",
        param_infos={
            "directory": "目录路径（可选，默认当前目录）",
            "recursive": "是否递归列出子目录（默认False）"
        }
    )
    async def list_dir(
        self,
        directory: Optional[str] = None,
        recursive: bool = False
    ) -> str:
        """列出目录内容"""
        from ..core.working_context import WorkingContext

        # ✅ 直接访问 self 的属性
        working_context = self.working_context
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        base_dir = directory or working_context.current_dir

        # 根据平台执行
        if platform.system() == "Windows":
            return await self._list_dir_windows(base_dir, recursive, working_context)
        else:
            return await self._list_dir_unix(base_dir, recursive, working_context)

    @register_action(
        description="读取文件内容。支持指定行范围（默认前200行）",
        param_infos={
            "file_path": "文件路径",
            "start_line": "起始行号（从1开始，默认1）",
            "end_line": "结束行号（默认200）"
        }
    )
    async def read(
        self,
        file_path: str,
        start_line: Optional[int] = 1,
        end_line: Optional[int] = 200
    ) -> str:
        """读取文件内容"""
        from ..core.working_context import WorkingContext

        working_context = self.working_context
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        if platform.system() == "Windows":
            return await self._read_windows(file_path, start_line, end_line, working_context)
        else:
            return await self._read_unix(file_path, start_line, end_line, working_context)

    @register_action(
        description="写入文件内容。默认覆盖模式。",
        param_infos={
            "file_path": "文件路径",
            "content": "文件内容",
            "mode": "写入模式，'overwrite' 覆盖或 'append' 追加（默认overwrite）",
            "allow_overwrite": "（可选）是否允许覆盖已存在文件（默认False）"
        }
    )
    async def write(
        self,
        file_path: str,
        content: str,
        mode: str = "overwrite",
        allow_overwrite: bool = False
    ) -> str:
        """写入文件内容"""
        from ..core.working_context import WorkingContext

        working_context = self.working_context
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        if platform.system() == "Windows":
            return await self._write_windows(file_path, content, mode, allow_overwrite, working_context)
        else:
            return await self._write_unix(file_path, content, mode, allow_overwrite, working_context)

    # ==================== Unix 实现（简化版）====================

    async def _list_dir_unix(self, base_dir: str, recursive: bool, working_context) -> str:
        """Unix 列出目录实现"""
        if recursive:
            cmd = f"ls -lhR {base_dir}"
        else:
            cmd = f"ls -lho {base_dir}"

        return await self._run_shell_unix(cmd, working_context)

    async def _read_unix(self, file_path: str, start_line: int, end_line: int, working_context) -> str:
        """Unix 读取文件实现（简化版）"""
        abs_path = self._resolve_path(file_path, working_context)
        if abs_path.startswith("错误："):
            return abs_path

        if not os.path.exists(abs_path):
            return f"错误：文件不存在: {abs_path}"

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            total_lines = len(lines)
            file_size = os.path.getsize(abs_path)
            size_str = self._format_size(file_size)

            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            selected_lines = lines[start_idx:end_idx]

            header = f"# 文件: {file_path} ({size_str}, 共 {total_lines} 行)\n"
            header += f"# 显示第 {start_line}-{end_idx} 行\n"

            content = ''.join(selected_lines)
            return header + content

        except Exception as e:
            return f"错误：读取文件失败: {e}"

    async def _write_unix(self, file_path: str, content: str, mode: str, allow_overwrite: bool, working_context) -> str:
        """Unix 写入文件实现"""
        abs_path = self._resolve_path(file_path, working_context)
        if abs_path.startswith("错误："):
            return abs_path

        file_exists = os.path.exists(abs_path)
        if file_exists and mode == "overwrite" and not allow_overwrite:
            return f"> 检查文件: {abs_path}\n错误：文件已存在，如果要覆盖请设置 allow_overwrite=True"

        try:
            os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else abs_path, exist_ok=True)
            write_mode = 'a' if mode == "append" else 'w'
            with open(abs_path, write_mode, encoding='utf-8') as f:
                f.write(content)

            mode_desc = '追加到' if mode == 'append' else '写入'
            return f"> 成功{mode_desc} {file_path}\n"

        except Exception as e:
            return f"> 写入{file_path}失败: {e}"

    # ==================== Windows 实现（简化版）====================

    async def _list_dir_windows(self, base_dir: str, recursive: bool, working_context) -> str:
        """Windows 列出目录实现"""
        if recursive:
            cmd = f"dir /s /b {base_dir}"
        else:
            cmd = f"dir /o:-d /-c {base_dir}"

        return await self._run_shell_windows(cmd, working_context)

    async def _read_windows(self, file_path: str, start_line: int, end_line: int, working_context) -> str:
        """Windows 读取文件实现（与 Unix 相同，跨平台）"""
        return await self._read_unix(file_path, start_line, end_line, working_context)

    async def _write_windows(self, file_path: str, content: str, mode: str, allow_overwrite: bool, working_context) -> str:
        """Windows 写入文件实现（与 Unix 相同，跨平台）"""
        return await self._write_unix(file_path, content, mode, allow_overwrite, working_context)

    # ==================== 辅助方法 ====================

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"

    def _resolve_path(self, file_path: str, working_context) -> str:
        """解析并验证路径"""
        if ".." in file_path or file_path.startswith("~"):
            return "错误：不允许使用相对路径父目录 (..) 或 home directory (~)"

        if os.path.isabs(file_path):
            abs_path = os.path.abspath(file_path)
        else:
            abs_path = os.path.abspath(os.path.join(working_context.current_dir, file_path))

        abs_base = os.path.abspath(working_context.base_dir)
        if not abs_path.startswith(abs_base):
            return f"错误：路径超出安全边界\n  路径: {abs_path}\n  允许范围: {abs_base}"

        return abs_path

    async def _run_shell_unix(self, cmd: str, working_context) -> str:
        """执行 Unix shell 命令"""
        try:
            import subprocess
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_context.current_dir,
                timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[错误输出]\n{result.stderr}"

            if not output:
                return "Done（无输出）"

            return output

        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时\n  命令: {cmd}"
        except Exception as e:
            return f"错误：执行命令失败: {e}\n  命令: {cmd}"

    async def _run_shell_windows(self, cmd: str, working_context) -> str:
        """执行 Windows shell 命令"""
        try:
            import subprocess
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_context.current_dir,
                timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[错误输出]\n{result.stderr}"

            if not output:
                return "Done（无输出）"

            return output

        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时\n  命令: {cmd}"
        except Exception as e:
            return f"错误：执行命令失败: {e}\n  命令: {cmd}"
