"""
File Operation Skill - 直接暴露文件操作 actions

重构说明：
- 不再使用 FileMicroAgent，直接在 Mixin 层暴露 actions
- 根据操作系统动态选择实现
- @register_action 方法：self = MicroAgent (调用者)
- 实现方法：self = BaseAgent (持有 mixin)

关键设计：
- action 方法获取 self.working_context（MicroAgent 的当前工作目录）
- 传递给平台实现方法
- 实现方法使用传入的 working_context，而不是 self.working_context
"""

import os
import platform
from typing import Optional
from ..core.action import register_action


class FileOperationSkillMixin:
    """
    File Operation Skill Mixin (新版本)

    直接暴露文件操作 actions：
    - list_dir: 列出目录内容
    - read: 读取文件
    - write: 写入文件
    - search: 搜索文件或内容
    - shell_cmd: 执行 shell 命令

    特点：
    - 根据操作系统自动选择实现
    - 必须在有 working_context 的环境中使用
    - 所有路径都会进行安全检查
    """

    # ==================== Actions ====================

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
        """
        列出目录内容

        Args:
            directory: 目录路径（默认当前目录）
            recursive: 是否递归列出子目录
        """
        from ..core.working_context import WorkingContext

        # self = MicroAgent (调用者)
        working_context = getattr(self, 'working_context', None)
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        base_dir = directory or working_context.current_dir

        # 通过 root_agent 调用实现方法（和 browser_use_skill 一样）
        if hasattr(self, 'root_agent'):
            target = self.root_agent
        else:
            target = self

        # 根据平台选择实现
        if platform.system() == "Windows":
            return await target._list_dir_windows(base_dir, recursive, working_context)
        else:
            return await target._list_dir_unix(base_dir, recursive, working_context)

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
        """
        读取文件内容

        Args:
            file_path: 文件路径
            start_line: 起始行号（从 1 开始，默认 1）
            end_line: 结束行号（默认 200）
        """
        from ..core.working_context import WorkingContext

        # self = MicroAgent (调用者)
        working_context = getattr(self, 'working_context', None)
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        # 通过 root_agent 调用实现方法（和 browser_use_skill 一样）
        if hasattr(self, 'root_agent'):
            target = self.root_agent
        else:
            target = self

        # 根据平台选择实现
        if platform.system() == "Windows":
            return await target._read_windows(file_path, start_line, end_line, working_context)
        else:
            return await target._read_unix(file_path, start_line, end_line, working_context)

    @register_action(
        description="写入文件内容。支持覆盖或追加模式",
        param_infos={
            "file_path": "文件路径",
            "content": "文件内容",
            "mode": "写入模式，'overwrite' 覆盖或 'append' 追加（默认overwrite）",
            "allow_overwrite": "是否允许覆盖已存在文件（默认False）"
        }
    )
    async def write(
        self,
        file_path: str,
        content: str,
        mode: str = "overwrite",
        allow_overwrite: bool = False
    ) -> str:
        """
        写入文件内容

        Args:
            file_path: 文件路径
            content: 文件内容
            mode: 写入模式，'overwrite' 覆盖或 'append' 追加（默认 overwrite）
            allow_overwrite: 是否允许覆盖已存在文件（默认 False）
        """
        from ..core.working_context import WorkingContext

        # self = MicroAgent (调用者)
        working_context = getattr(self, 'working_context', None)
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        # 通过 root_agent 调用实现方法（和 browser_use_skill 一样）
        if hasattr(self, 'root_agent'):
            target = self.root_agent
        else:
            target = self

        # 根据平台选择实现
        if platform.system() == "Windows":
            return await target._write_windows(file_path, content, mode, allow_overwrite, working_context)
        else:
            return await target._write_unix(file_path, content, mode, allow_overwrite, working_context)

    @register_action(
        description="搜索文件或内容。支持按文件名或文件内容搜索",
        param_infos={
            "pattern": "搜索模式（文件名模式或文本内容）",
            "target": "搜索目标，'content' 表示在文件内容中搜索，'filename' 表示按文件名搜索（默认content）",
            "directory": "搜索目录（可选，默认当前目录）",
            "recursive": "是否递归搜索（默认True）"
        }
    )
    async def search(
        self,
        pattern: str,
        target: str = "content",
        directory: Optional[str] = None,
        recursive: bool = True
    ) -> str:
        """
        搜索文件或内容

        Args:
            pattern: 搜索模式
            target: 搜索目标，"content" 表示在文件内容中搜索，"filename" 表示按文件名搜索
            directory: 搜索目录（默认当前目录）
            recursive: 是否递归搜索
        """
        from ..core.working_context import WorkingContext

        # self = MicroAgent (调用者)
        working_context = getattr(self, 'working_context', None)
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        # 通过 root_agent 调用实现方法（和 browser_use_skill 一样）
        if hasattr(self, 'root_agent'):
            target_agent = self.root_agent
        else:
            target_agent = self

        # 根据平台选择实现（传入 working_context）
        if platform.system() == "Windows":
            return await target_agent._search_windows(pattern, target, directory, recursive, working_context)
        else:
            return await target_agent._search_unix(pattern, target, directory, recursive, working_context)

    @register_action(
        description="执行 shell 命令（仅限白名单命令）",
        param_infos={
            "command": "要执行的 shell 命令"
        }
    )
    async def shell_cmd(self, command: str) -> str:
        """
        直接执行 shell 命令（仅限白名单命令）

        白名单命令：ls, cat, grep, sed, find (Unix) 或 dir, type, findstr (Windows)

        Args:
            command: shell 命令
        """
        from ..core.working_context import WorkingContext

        # self = MicroAgent (调用者)
        working_context = getattr(self, 'working_context', None)
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        # 通过 root_agent 调用实现方法（和 browser_use_skill 一样）
        if hasattr(self, 'root_agent'):
            target_agent = self.root_agent
        else:
            target_agent = self

        # 根据平台选择实现（传入 working_context）
        if platform.system() == "Windows":
            return await target_agent._shell_cmd_windows(command, working_context)
        else:
            return await target_agent._shell_cmd_unix(command, working_context)

    # ==================== Unix 实现 ====================

    async def _list_dir_unix(self, base_dir: str, recursive: bool, working_context) -> str:
        """Unix 列出目录实现"""
        if recursive:
            cmd = f"ls -lhR {base_dir}"
        else:
            cmd = f"ls -lho {base_dir}"

        return await self._run_shell_unix(cmd, f"列出目录: {base_dir or '当前目录'}", working_context, enable_limit=True)

    async def _read_unix(self, file_path: str, start_line: int, end_line: int, working_context) -> str:
        """Unix 读取文件实现（Python 原生）"""
        # 路径安全检查
        abs_path = self._resolve_path(file_path, working_context)
        if abs_path.startswith("错误："):
            return abs_path

        # 检查文件是否存在
        if not os.path.exists(abs_path):
            return f"错误：文件不存在: {abs_path}"

        # 读取文件
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 获取文件统计信息
            total_lines = len(lines)
            file_size = os.path.getsize(abs_path)
            size_str = self._format_size(file_size)

            # 应用行范围
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            selected_lines = lines[start_idx:end_idx]

            # 构建统计信息
            header = f"# 文件: {file_path} ({size_str}, 共 {total_lines} 行)\n"
            header += f"# 显示第 {start_line}-{end_idx} 行\n"

            # 返回原始内容（不带行号）
            content = ''.join(selected_lines)

            return header + content

        except Exception as e:
            return f"错误：读取文件失败: {e}"

    async def _write_unix(self, file_path: str, content: str, mode: str, allow_overwrite: bool, working_context) -> str:
        """Unix 写入文件实现（Python 原生）"""
        # 路径安全检查
        abs_path = self._resolve_path(file_path, working_context)
        if abs_path.startswith("错误："):
            return abs_path

        # 检查文件是否存在
        file_exists = os.path.exists(abs_path)
        if file_exists and mode == "overwrite" and not allow_overwrite:
            return f"> 检查文件: {abs_path}\n错误：文件已存在，如果要覆盖请设置 allow_overwrite=True"

        # 写入文件
        try:
            os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else abs_path, exist_ok=True)
            write_mode = 'a' if mode == "append" else 'w'
            with open(abs_path, write_mode, encoding='utf-8') as f:
                f.write(content)

            mode_desc = '追加到' if mode == 'append' else '写入'
            return f"> 成功{mode_desc}文件: {abs_path}\n"

        except Exception as e:
            return f"> 写入文件失败: {e}\n  文件路径: {abs_path}"

    async def _search_unix(self, pattern: str, target: str, directory: Optional[str], recursive: bool, working_context) -> str:
        """Unix 搜索实现"""
        base_dir = directory or working_context.current_dir

        if target == "filename":
            # 按文件名搜索（使用 find）
            cmd = f"find {base_dir}"
            if not recursive:
                cmd += " -maxdepth 1"
            cmd += f" -name '{pattern}'"
        else:
            # 在文件内容中搜索（使用 grep）
            if recursive:
                cmd = f"grep -rn '{pattern}' {base_dir}"
            else:
                cmd = f"grep -n '{pattern}' {base_dir}/*"

        return await self._run_shell_unix(cmd, f"搜索: {pattern}", working_context, enable_limit=True)

    async def _shell_cmd_unix(self, command: str, working_context) -> str:
        """Unix 执行 shell 命令实现"""
        # 白名单检查
        whitelist = {'ls', 'cat', 'head', 'tail', 'sed', 'grep', 'find', 'echo', 'wc'}
        cmd_parts = command.split()
        if not cmd_parts or cmd_parts[0] not in whitelist:
            return f"错误：命令 '{cmd_parts[0] if cmd_parts else ''}' 不在白名单中"

        # 执行命令（使用 working_context.current_dir 作为工作目录）
        return await self._run_shell_unix(command, f"执行命令: {command}", working_context)

    # ==================== Windows 实现 ====================

    async def _list_dir_windows(self, base_dir: str, recursive: bool, working_context) -> str:
        """Windows 列出目录实现"""
        if recursive:
            cmd = f"dir /s /b {base_dir}"
        else:
            cmd = f"dir /o:-d /-c {base_dir}"

        return await self._run_shell_windows(cmd, f"列出目录: {base_dir or '当前目录'}", working_context, enable_limit=True)

    async def _read_windows(self, file_path: str, start_line: int, end_line: int, working_context) -> str:
        """Windows 读取文件实现（Python 原生）"""
        # 路径安全检查
        abs_path = self._resolve_path(file_path, working_context)
        if abs_path.startswith("错误："):
            return abs_path

        # 检查文件是否存在
        if not os.path.exists(abs_path):
            return f"错误：文件不存在: {abs_path}"

        # 读取文件（Python 跨平台）
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 获取文件统计信息
            total_lines = len(lines)
            file_size = os.path.getsize(abs_path)
            size_str = self._format_size(file_size)

            # 应用行范围
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            selected_lines = lines[start_idx:end_idx]

            # 构建统计信息
            header = f"# 文件: {file_path} ({size_str}, 共 {total_lines} 行)\n"
            header += f"# 显示第 {start_line}-{end_idx} 行\n"

            # 返回原始内容（不带行号）
            content = ''.join(selected_lines)

            return header + content

        except Exception as e:
            return f"错误：读取文件失败: {e}"

    async def _write_windows(self, file_path: str, content: str, mode: str, allow_overwrite: bool, working_context) -> str:
        """Windows 写入文件实现（Python 原生）"""
        # 路径安全检查
        abs_path = self._resolve_path(file_path, working_context)
        if abs_path.startswith("错误："):
            return abs_path

        # 检查文件是否存在
        file_exists = os.path.exists(abs_path)
        if file_exists and mode == "overwrite" and not allow_overwrite:
            return f"> 检查文件: {abs_path}\n错误：文件已存在，如果要覆盖请设置 allow_overwrite=True"

        # 写入文件
        try:
            os.makedirs(os.path.dirname(abs_path) if os.path.dirname(abs_path) else abs_path, exist_ok=True)
            write_mode = 'a' if mode == "append" else 'w'
            with open(abs_path, write_mode, encoding='utf-8') as f:
                f.write(content)

            mode_desc = '追加到' if mode == 'append' else '写入'
            return f"> 成功{mode_desc}文件: {abs_path}\n"

        except Exception as e:
            return f"> 写入文件失败: {e}\n  文件路径: {abs_path}"

    async def _search_windows(self, pattern: str, target: str, directory: Optional[str], recursive: bool, working_context) -> str:
        """Windows 搜索实现"""
        base_dir = directory or working_context.current_dir

        if target == "filename":
            # 按文件名搜索
            cmd = f"dir /s /b {base_dir} | findstr /i \"{pattern}\""
        else:
            # 在文件内容中搜索
            recursive_flag = "/s" if recursive else ""
            cmd = f'findstr {recursive_flag} /n /i /c:"{pattern}" *'

        return await self._run_shell_windows(cmd, f"搜索: {pattern}", working_context, enable_limit=True)

    async def _shell_cmd_windows(self, command: str, working_context) -> str:
        """Windows 执行 shell 命令实现"""
        # 白名单检查
        whitelist = {'dir', 'type', 'findstr', 'echo'}
        cmd_parts = command.split()
        if not cmd_parts or cmd_parts[0] not in whitelist:
            return f"错误：命令 '{cmd_parts[0] if cmd_parts else ''}' 不在白名单中"

        # 执行命令（使用 working_context.current_dir 作为工作目录）
        return await self._run_shell_windows(command, f"执行命令: {command}", working_context)

    # ==================== 辅助方法 ====================

    def _format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小

        Args:
            size_bytes: 文件大小（字节）

        Returns:
            格式化后的字符串，如 "1.2KB", "3.5MB"
        """
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"

    async def _create_temp_file(self, working_context) -> str:
        """
        在 session 目录的 temp 子目录下创建临时文件

        Args:
            working_context: MicroAgent 的 working_context

        Returns:
            str: 临时文件的相对路径（用于显示）
        """
        import uuid
        import os

        # 创建 temp 目录
        temp_dir = os.path.join(working_context.current_dir, "temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # 生成唯一的临时文件名
        temp_filename = f"temp_{uuid.uuid4().hex[:8]}.txt"

        # 返回相对路径（用于显示）
        return f"temp/{temp_filename}"

    async def _save_to_temp_file(self, content: str, temp_path: str, working_context) -> None:
        """
        将内容保存到临时文件

        Args:
            content: 要保存的内容
            temp_path: 临时文件路径（相对路径）
            working_context: MicroAgent 的 working_context
        """
        import os
        full_path = os.path.join(working_context.current_dir, temp_path)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

    async def _format_output_with_limit(self, description: str, output: str, working_context, max_lines: int = 200) -> str:
        """
        格式化输出，限制最大行数（防爆设计）

        Args:
            description: 操作描述
            output: 输出内容
            working_context: MicroAgent 的 working_context
            max_lines: 最大行数（默认 200）

        Returns:
            str: 格式化后的结果（可能包含截断提示）
        """
        lines = output.split('\n')
        total_lines = len(lines)

        if total_lines <= max_lines:
            # 输出较小，直接返回
            return f"> {description}\n{output}"

        # 输出过大，需要截断
        preview_lines = lines[:max_lines]
        preview_output = '\n'.join(preview_lines)

        # 创建临时文件
        temp_path = await self._create_temp_file(working_context)
        await self._save_to_temp_file(output, temp_path, working_context)

        # 构造提示信息
        import os
        temp_file_full = os.path.join(working_context.current_dir, temp_path)
        file_size = os.path.getsize(temp_file_full)
        if file_size < 1024:
            size_str = f"{file_size} bytes"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f}KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f}MB"

        # 显示结果
        return f"> {description}\n{preview_output}\n\n# 输出已截断（共 {total_lines} 行，{size_str}）\n# 完整输出已保存到: {temp_path}\n# 查看完整输出: cat {temp_path}"

    def _resolve_path(self, file_path: str, working_context) -> str:
        """
        解析并验证路径（安全检查）

        Args:
            file_path: 文件路径
            working_context: MicroAgent 的 working_context

        Returns:
            绝对路径，或错误消息
        """
        # 检查危险路径模式
        if ".." in file_path or file_path.startswith("~"):
            return "错误：不允许使用相对路径父目录 (..) 或 home directory (~)"

        # 解析为绝对路径
        if os.path.isabs(file_path):
            abs_path = os.path.abspath(file_path)
        else:
            # 相对于 working_context.current_dir（MicroAgent 的当前目录）
            abs_path = os.path.abspath(os.path.join(working_context.current_dir, file_path))

        # 安全检查：确保不超出 base_dir
        abs_base = os.path.abspath(working_context.base_dir)
        if not abs_path.startswith(abs_base):
            return f"错误：路径超出安全边界\n  路径: {abs_path}\n  允许范围: {abs_base}"

        return abs_path

    async def _run_shell_unix(self, cmd: str, description: str, working_context, enable_limit: bool = False) -> str:
        """
        执行 Unix shell 命令

        Args:
            cmd: shell 命令
            description: 描述
            working_context: MicroAgent 的 working_context
            enable_limit: 是否启用输出限制（防爆设计，默认False）
        """
        try:
            import subprocess
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_context.current_dir  # 使用 MicroAgent 的当前目录
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[错误输出]\n{result.stderr}"

            if not output:
                return f"> {description}（无输出）"

            # 应用防爆设计
            if enable_limit:
                return await self._format_output_with_limit(description, output, working_context)
            else:
                return f"> {description}\n{output}"

        except Exception as e:
            return f"错误：执行命令失败: {e}\n  命令: {cmd}"

    async def _run_shell_windows(self, cmd: str, description: str, working_context, enable_limit: bool = False) -> str:
        """
        执行 Windows shell 命令

        Args:
            cmd: shell 命令
            description: 描述
            working_context: MicroAgent 的 working_context
            enable_limit: 是否启用输出限制（防爆设计，默认False）
        """
        try:
            import subprocess
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_context.current_dir  # 使用 MicroAgent 的当前目录
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[错误输出]\n{result.stderr}"

            if not output:
                return f"> {description}（无输出）"

            # 应用防爆设计
            if enable_limit:
                return await self._format_output_with_limit(description, output, working_context)
            else:
                return f"> {description}\n{output}"

        except Exception as e:
            return f"错误：执行命令失败: {e}\n  命令: {cmd}"
