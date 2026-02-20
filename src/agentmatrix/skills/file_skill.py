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


# ==================== Bash 安全白名单 ====================

# 分级白名单（Unix）
BASH_WHITELIST_UNIX = {
    # ===== 等级 1: 完全安全（无副作用）=====
    "safe": {
        # 文本查看
        "cat", "head", "tail", "less", "more",
        # 搜索
        "grep", "egrep", "fgrep",
        # 排序和统计
        "sort", "uniq", "wc", "nl",
        # 文本处理
        "cut", "tr", "sed", "awk",
        # 系统信息（只读）
        "pwd", "date", "whoami", "hostname", "uname",
        "df", "du", "free", "uptime",
        # 进程查看
        "ps", "top",
        # 文件列表
        "ls", "ll", "dir",
        # 回显
        "echo", "printf",
    },

    # ===== 等级 2: 需要参数限制（有文件操作）=====
    "restricted": {
        # 创建目录
        "mkdir",
        # 创建文件
        "touch",
        # 删除文件（需要额外检查）
        "rm",
        # 复制/移动（需要路径检查）
        "cp", "mv",
        # 压缩
        "tar", "gzip", "gunzip", "zip", "unzip",
        # 权限（需要严格限制）
        "chmod",
        # 查找文件
        "find",
        # 链接
        "ln",
    },

    # ===== 等级 3: 需要谨慎使用（开发工具）=====
    "caution": {
        # 开发工具
        "python3", "python", "node",
        # 版本控制
        "git",
        # 网络工具
        "curl", "wget",
        # 包管理
        "pip", "pip3", "npm",
    },
}

# 白名单（Windows）
BASH_WHITELIST_WINDOWS = {
    "safe": {
        "dir", "type", "echo",
        "findstr", "where",
    },
    "restricted": {
        "mkdir", "del", "copy", "move", "ren",
    },
}



class FileSkillMixin:
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

        
        working_context = getattr(self, 'working_context', None)
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        base_dir = directory or working_context.current_dir

        
        if hasattr(self, 'root_agent'):
            target = self.root_agent
        else:
            target = self

        # 根据平台选择实现
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
        """
        读取文件内容

        Args:
            file_path: 文件路径
            start_line: 起始行号（从 1 开始，默认 1）
            end_line: 结束行号（默认 200）
        """
        from ..core.working_context import WorkingContext

        
        working_context = getattr(self, 'working_context', None)
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        
        if hasattr(self, 'root_agent'):
            target = self.root_agent
        else:
            target = self

        # 根据平台选择实现
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
        """
        写入文件内容

        Args:
            file_path: 文件路径
            content: 文件内容
            mode: 写入模式，'overwrite' 覆盖或 'append' 追加（默认 overwrite）
            allow_overwrite: 是否允许覆盖已存在文件（默认 False）
        """
        from ..core.working_context import WorkingContext

        
        working_context = getattr(self, 'working_context', None)
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        
        if hasattr(self, 'root_agent'):
            target = self.root_agent
        else:
            target = self

        # 根据平台选择实现
        if platform.system() == "Windows":
            return await self._write_windows(file_path, content, mode, allow_overwrite, working_context)
        else:
            return await self._write_unix(file_path, content, mode, allow_overwrite, working_context)

    @register_action(
        description="搜索文件或文件里的内容。支持按文件名或文件内容搜索",
        param_infos={
            "pattern": "搜索模式（文件名模式或文本内容）",
            "target": "搜索目标，'content' 表示在文件内容中搜索，'filename' 表示按文件名搜索（默认content）",
            "directory": "搜索目录（可选，默认当前目录）",
            "recursive": "是否递归搜索（默认True）"
        }
    )
    async def search_file(
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

        
        working_context = getattr(self, 'working_context', None)
        if not working_context or not isinstance(working_context, WorkingContext):
            return "错误：缺少 working_context"

        
        if hasattr(self, 'root_agent'):
            target_agent = self.root_agent
        else:
            target_agent = self

        # 根据平台选择实现（传入 working_context）
        if platform.system() == "Windows":
            return await self._search_windows(pattern, target, directory, recursive, working_context)
        else:
            return await self._search_unix(pattern, target, directory, recursive, working_context)

    @register_action(
        description="""执行 bash 命令或脚本
""",
        param_infos={
            "command": "bash 命令或脚本（多行脚本用 \\n 分隔）",
            "timeout": "超时时间（秒，默认30）"
        }
    )
    async def bash(self, command: str, timeout: int = 30) -> str:
        """
        执行 bash 命令或脚本（安全模式）

        Args:
            command: bash 命令或脚本
            timeout: 超时时间（秒，默认30）

        Returns:
            执行结果
        """
        
        if hasattr(self, 'root_agent'):
            target = self.root_agent
        else:
            
            target = self

        # 1. 预处理：移除注释
        cleaned_command = self._remove_bash_comments(command)

        # 2. 语法检查（仅 Unix）
        if platform.system() != "Windows":
            is_valid, syntax_error = await self._validate_bash_syntax(cleaned_command)
            if not is_valid:
                return f"❌ 脚本语法错误：\n{syntax_error}"

        # 3. 命令白名单验证
        is_allowed, allow_error = await self._validate_bash_command(cleaned_command)
        if not is_allowed:
            return f"❌ 命令验证失败：\n{allow_error}"

        # 4. 执行命令（根据平台选择实现）
        if platform.system() == "Windows":
            return await self._bash_windows(cleaned_command, self.working_context, timeout)
        else:
            return await self._bash_unix(cleaned_command, self.working_context, timeout)

    @register_action(
        description="字符串替换：在文件中查找并替换字符串。",
        param_infos={
            "file_path": "文件路径",
            "old_pattern": "要替换的旧字符串",
            "new_string": "新字符串",
            "use_regex": "是否使用正则表达式（默认false）"
        }
    )
    async def replace_string_in_file(self, file_path: str, old_pattern: str, new_string: str, use_regex: bool = False) -> str:
        """
        在文件中查找并替换字符串

        Args:
            file_path: 文件路径
            old_pattern: 要替换的旧字符串
            new_string: 新字符串
            use_regex: 是否使用正则表达式（默认false）
        """
        # 调用平台实现
        if platform.system() == "Windows":
            return await self.root_agent._string_replace_windows(file_path, old_pattern, new_string, use_regex, self.working_context)
        else:
            return await self.root_agent._string_replace_unix(file_path, old_pattern, new_string, use_regex, self.working_context)

    # ==================== 辅助方法（Bash 安全）====================

    def _remove_bash_comments(self, script: str) -> str:
        """
        移除 bash 脚本中的注释行

        规则：
        - 保留 shebang (#!)
        - 移除以 # 开头的行
        - 移除行尾的 # 注释
        - 保留字符串中的 #
        """
        lines = []
        for line in script.split('\n'):
            # 保留 shebang
            if line.strip().startswith('#!'):
                lines.append(line)
                continue

            # 移除注释行
            stripped = line.strip()
            if stripped.startswith('#'):
                continue

            # 移除行尾注释（但要小心字符串中的 #）
            # 简化版：只在非引号内的 # 移除
            in_single_quote = False
            in_double_quote = False
            result = []
            i = 0
            while i < len(line):
                char = line[i]
                if char == "'" and not in_double_quote and (i == 0 or line[i-1] != '\\'):
                    in_single_quote = not in_single_quote
                elif char == '"' and not in_single_quote and (i == 0 or line[i-1] != '\\'):
                    in_double_quote = not in_double_quote
                elif char == '#' and not in_single_quote and not in_double_quote:
                    # 找到注释，跳过剩余部分
                    break
                result.append(char)
                i += 1

            cleaned = ''.join(result).rstrip()
            if cleaned:
                lines.append(cleaned)

        return '\n'.join(lines)

    async def _validate_bash_syntax(self, script: str) -> tuple[bool, str]:
        """
        验证 bash 脚本语法

        Returns:
            (is_valid, error_message)
        """
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(script)
            temp_path = f.name

        try:
            result = subprocess.run(
                ['bash', '-n', temp_path],  # -n 只检查语法，不执行
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return True, ""
            else:
                return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "语法检查超时"
        except FileNotFoundError:
            # bash 不存在（可能是 Windows），跳过检查
            return True, ""
        except Exception as e:
            return False, str(e)
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

    async def _validate_bash_command(self, command: str) -> tuple[bool, str]:
        """
        验证 bash 命令是否在白名单中

        Returns:
            (is_allowed, error_message)
        """
        # 获取平台对应的白名单
        if platform.system() == "Windows":
            whitelist = BASH_WHITELIST_WINDOWS
        else:
            whitelist = BASH_WHITELIST_UNIX

        # 解析命令中的所有命令（处理管道、分号等）
        commands = self._parse_command_tokens(command)

        if not commands:
            return True, ""  # 空命令

        # 检查每个命令
        for cmd_name in commands:
            # 检查是否在白名单中
            if cmd_name in whitelist.get("safe", set()):
                continue  # 等级1：完全允许

            elif cmd_name in whitelist.get("restricted", set()):
                # 等级2：允许但需要参数检查
                # 简化：暂不检查参数，只检查命令名
                continue

            elif cmd_name in whitelist.get("caution", set()):
                # 等级3：谨慎使用，但允许
                continue

            else:
                # 不在白名单
                return False, f"命令 '{cmd_name}' 不在白名单中。\n提示：只允许使用安全的文件和文本处理命令。"

        return True, ""

    def _parse_command_tokens(self, command: str) -> list:
        """
        解析命令，提取所有命令名

        处理：
        - 管道 |
        - 分号 ;
        - 逻辑运算 &&, ||
        - 重定向 >, >>, <

        Returns:
            list of command names
        """
        import re

        # 移除重定向（简化处理）
        # 替换重定向为空格
        command = re.sub(r'[<>][<>?\s]', ' ', command)

        # 按管道、分号、逻辑运算分割
        separators = r'\s*[|;]\s*|\s&&\s*|\s\|\|\s*'
        parts = re.split(separators, command)

        # 提取每个部分的命令名
        commands = []
        for part in parts:
            part = part.strip()
            if part:
                # 分割单词，取第一个作为命令名
                words = part.split()
                if words:
                    cmd_name = words[0]
                    commands.append(cmd_name)

        return commands

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

        # PDF 文件特殊处理
        if self._is_pdf_file(file_path):
            try:
                # 获取缓存文件路径
                cache_path = await self._get_pdf_cache_path(abs_path, working_context)

                # 检查缓存是否需要更新
                need_convert = True
                if os.path.exists(cache_path):
                    # 比较修改时间
                    pdf_mtime = os.path.getmtime(abs_path)
                    cache_mtime = os.path.getmtime(cache_path)
                    if cache_mtime >= pdf_mtime:
                        need_convert = False

                # 如果需要转换
                if need_convert:
                    # 转换 PDF 到 Markdown
                    markdown_text = await self._convert_pdf_to_markdown_text(abs_path)

                    # 保存到缓存文件
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    with open(cache_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_text)

                # 读取缓存文件
                abs_path = cache_path
                file_path = f"{file_path} (Markdown 缓存)"

            except Exception as e:
                return f"错误：PDF 处理失败: {e}\n  文件: {abs_path}"

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
            return f"> 成功{mode_desc} {file_path}\n"

        except Exception as e:
            return f"> 写入{file_path}失败: {e}"

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

    async def _bash_unix(self, command: str, working_context, timeout: int = 30) -> str:
        """Unix 执行 bash 命令实现"""
        # 执行命令（使用 working_context.current_dir 作为工作目录）
        return await self._run_shell_unix(command, f" ", working_context, timeout=timeout)

    async def _string_replace_unix(self, file_path: str, old_pattern: str, new_string: str, use_regex: bool, working_context) -> str:
        """Unix 字符串替换实现"""
        import re

        # 读取文件内容
        abs_path = self._resolve_path(file_path, working_context)
        if abs_path.startswith("错误："):
            return abs_path

        if not os.path.exists(abs_path):
            return f"错误：文件不存在: {abs_path}"

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if use_regex:
                new_content = re.sub(old_pattern, new_string, content)
            else:
                new_content = content.replace(old_pattern, new_string)

            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            old_preview = old_pattern[:20] + "..." if len(old_pattern) > 20 else old_pattern
            new_preview = new_string[:20] + "..." if len(new_string) > 20 else new_string

            return f"""字符串已替换"""

        except Exception as e:
            return f"❌ 替换失败：{str(e)}"

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

        # PDF 文件特殊处理
        if self._is_pdf_file(file_path):
            try:
                # 获取缓存文件路径
                cache_path = await self._get_pdf_cache_path(abs_path, working_context)

                # 检查缓存是否需要更新
                need_convert = True
                if os.path.exists(cache_path):
                    # 比较修改时间
                    pdf_mtime = os.path.getmtime(abs_path)
                    cache_mtime = os.path.getmtime(cache_path)
                    if cache_mtime >= pdf_mtime:
                        need_convert = False

                # 如果需要转换
                if need_convert:
                    # 转换 PDF 到 Markdown
                    markdown_text = await self._convert_pdf_to_markdown_text(abs_path)

                    # 保存到缓存文件
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    with open(cache_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_text)

                # 读取缓存文件
                abs_path = cache_path
                file_path = f"{file_path} (Markdown 缓存)"

            except Exception as e:
                return f"错误：PDF 处理失败: {e}\n  文件: {abs_path}"

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

    async def _bash_windows(self, command: str, working_context, timeout: int = 30) -> str:
        """Windows 执行 shell 命令实现"""
        # 执行命令（使用 working_context.current_dir 作为工作目录）
        return await self._run_shell_windows(command, f"执行命令: {command}", working_context, timeout=timeout)

    async def _string_replace_windows(self, file_path: str, old_pattern: str, new_string: str, use_regex: bool, working_context) -> str:
        """Windows 字符串替换实现"""
        import re

        # 读取文件内容
        abs_path = self._resolve_path(file_path, working_context)
        if abs_path.startswith("错误："):
            return abs_path

        if not os.path.exists(abs_path):
            return f"错误：文件不存在: {abs_path}"

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if use_regex:
                new_content = re.sub(old_pattern, new_string, content)
            else:
                new_content = content.replace(old_pattern, new_string)

            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            old_preview = old_pattern[:20] + "..." if len(old_pattern) > 20 else old_pattern
            new_preview = new_string[:20] + "..." if len(new_string) > 20 else new_string

            return f"""内容已替换 """

        except Exception as e:
            return f"❌ 替换失败：{str(e)}"

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
            return f"{output}"

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
        return f"{preview_output}\n\n# 输出已截断（共 {total_lines} 行，{size_str}）\n# 完整输出已保存到: {temp_path}\n# 查看完整输出: cat {temp_path}"

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

    async def _run_shell_unix(self, cmd: str, description: str, working_context, enable_limit: bool = False, timeout: int = 30) -> str:
        """
        执行 Unix shell 命令

        Args:
            cmd: shell 命令
            description: 描述
            working_context: MicroAgent 的 working_context
            enable_limit: 是否启用输出限制（防爆设计，默认False）
            timeout: 超时时间（秒，默认30）
        """
        try:
            import subprocess
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_context.current_dir,  # 使用 MicroAgent 的当前目录
                timeout=timeout
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[错误输出]\n{result.stderr}"

            if not output:
                return f"Done（无输出）"

            # 应用防爆设计
            if enable_limit:
                return await self._format_output_with_limit(description, output, working_context)
            else:
                return f"> {description}\n{output}"

        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时（{timeout}秒）\n  命令: {cmd}"
        except Exception as e:
            return f"错误：执行命令失败: {e}\n  命令: {cmd}"

    async def _run_shell_windows(self, cmd: str, description: str, working_context, enable_limit: bool = False, timeout: int = 30) -> str:
        """
        执行 Windows shell 命令

        Args:
            cmd: shell 命令
            description: 描述
            working_context: MicroAgent 的 working_context
            enable_limit: 是否启用输出限制（防爆设计，默认False）
            timeout: 超时时间（秒，默认30）
        """
        try:
            import subprocess
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_context.current_dir,  # 使用 MicroAgent 的当前目录
                timeout=timeout
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

        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时（{timeout}秒）\n  命令: {cmd}"
        except Exception as e:
            return f"错误：执行命令失败: {e}\n  命令: {cmd}"

    # ==================== PDF 处理辅助方法 ====================

    def _is_pdf_file(self, file_path: str) -> bool:
        """
        检测文件是否为 PDF

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否为 PDF 文件
        """
        return file_path.lower().endswith('.pdf')

    async def _get_pdf_cache_path(self, pdf_path: str, working_context) -> str:
        """
        获取 PDF 缓存文件的路径

        缓存位置：{current_dir}/temp/.pdf_cache/{pdf_filename}.md

        Args:
            pdf_path: PDF 文件路径
            working_context: MicroAgent 的 working_context

        Returns:
            str: 缓存文件的绝对路径
        """
        import os

        # 创建缓存目录：temp/.pdf_cache/
        cache_dir = os.path.join(working_context.current_dir, "temp", ".pdf_cache")
        os.makedirs(cache_dir, exist_ok=True)

        # 使用 PDF 文件名作为缓存文件名
        pdf_filename = os.path.basename(pdf_path)
        cache_filename = f"{pdf_filename}.md"

        return os.path.join(cache_dir, cache_filename)

    async def _convert_pdf_to_markdown_text(self, pdf_path: str) -> str:
        """
        将 PDF 文件转换为 Markdown 文本

        移植自 crawler_helpers.py，改为异步版本

        Args:
            pdf_path: PDF 文件的绝对路径

        Returns:
            str: Markdown 格式的文本

        Raises:
            Exception: PDF 转换失败
        """
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
        import fitz

        try:
            # 获取 PDF 总页数
            with fitz.open(pdf_path) as doc:
                total_pages = len(doc)

            # 使用 asyncio.to_thread 避免阻塞
            def _convert():
                # 初始化 marker 模型
                converter = PdfConverter(
                    artifact_dict=create_model_dict(),
                )

                # 执行转换
                rendered = converter(pdf_path)

                # 从渲染结果中提取文本
                text, _, images = text_from_rendered(rendered)

                return text

            # 在线程池中执行转换（避免阻塞）
            import asyncio
            text = await asyncio.to_thread(_convert)

            return text

        except Exception as e:
            raise Exception(f"PDF 转换失败: {e}")
