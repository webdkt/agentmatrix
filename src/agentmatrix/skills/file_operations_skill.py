"""
File Operations Skill - 提供 file_operation action

架构：
1. FileOperationSkillMixin (外层) - 暴露 file_operation action 给主 Agent
2. _FileMicroAgentBase (基类) - 通用逻辑
3. _UnixFileMicroAgent / _WindowsFileMicroAgent (系统特定实现)
"""

import platform
import asyncio
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from ..agents.micro_agent import MicroAgent
from ..backends.llm_client import LLMClient
from ..core.action import register_action


# ==================== 系统特定的 File Micro Agent ====================

class _FileMicroAgentBase(MicroAgent, ABC):
    """
    File Micro Agent 基类

    提供通用逻辑：
    - shell 执行
    - parser
    - action 元数据
    """

    def __init__(
        self,
        session_dir: str,
        brain: LLMClient,
        cerebellum: Any,
        default_max_steps: int = 10
    ):
        """
        初始化 File Micro Agent

        Args:
            session_dir: session 目录路径（文件操作根目录）
            brain: LLM 接口
            cerebellum: 参数协商器
            default_max_steps: 默认最大步数
        """
        self.root_dir = session_dir  # 内部还是叫 root_dir（表示文件操作的根）

        # 准备 action registry（只有 4 个核心 action + shell_cmd）
        action_registry = {
            "list_dir": self.list_dir,
            "read": self.read,
            "write": self.write,
            "search": self.search,
            "shell_cmd": self.shell_cmd,
            "all_finished": self.all_finished
        }

        # 初始化 MicroAgent
        super().__init__(
            brain=brain,
            cerebellum=cerebellum,
            action_registry=action_registry,
            name=f"FileMicroAgent_{self.system_name}",
            default_max_steps=default_max_steps
        )

        # 累积操作结果
        self.operation_results: list[str] = []

    def _build_system_prompt(self) -> str:
        """构建 File Micro Agent 专用 System Prompt"""
        return f"""
            ### 你的工具箱 (可用action)
            {self._format_actions_list()}"""
        

    @property
    @abstractmethod
    def system_name(self) -> str:
        """系统名称"""
        pass

    # ==================== 抽象方法（子类实现）====================

    @abstractmethod
    async def list_dir(
        self,
        directory: Optional[str] = None,
        recursive: bool = False
    ) -> str:
        """
        列出目录内容

        Args:
            directory: 目录路径（默认为当前目录）
            recursive: 是否递归列出子目录
        """
        pass

    @abstractmethod
    async def read(self, file_path: str, start_line: Optional[int] = 1, end_line: Optional[int] = 200) -> str:
        """
        读取文件内容

        Args:
            file_path: 文件路径
            start_line: 起始行号（从 1 开始，默认 1）
            end_line: 结束行号（默认 200，最多读取 200 行）
        """
        pass

    @abstractmethod
    async def shell_cmd(self, command: str) -> str:
        """
        直接执行 shell 命令（仅限白名单命令）

        白名单命令对应现有 action：
        - ls, dir, cat, type, head, sed → read
        - grep, findstr → search
        - find → search (按文件名)

        Args:
            command: shell 命令

        Returns:
            str: 命令输出
        """
        pass

    @abstractmethod
    async def write(self, file_path: str, content: str, mode: str = "overwrite", allow_overwrite: bool = False) -> str:
        """
        写入文件内容

        Args:
            file_path: 文件路径
            content: 文件内容
            mode: 写入模式，'overwrite' 覆盖或 'append' 追加（默认 overwrite）
            allow_overwrite: 是否允许覆盖已存在文件（默认 False）
        """
        pass

    @abstractmethod
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
            pattern: 搜索模式（文件名模式或文本内容）
            target: 搜索目标，"content" 表示在文件内容中搜索，"filename" 表示按文件名搜索
            directory: 搜索目录（默认为当前目录）
            recursive: 是否递归搜索
        """
        pass

    async def all_finished(self, result: str) -> str:
        """完成任务"""
        return result

    # ==================== 通用方法 ====================

    async def _create_temp_file(self) -> str:
        """
        在 session 目录的 temp 子目录下创建临时文件

        Returns:
            str: 临时文件的相对路径（用于显示）
        """
        import uuid
        import os

        # 创建 temp 目录
        temp_dir = os.path.join(self.root_dir, "temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # 生成唯一的临时文件名
        temp_filename = f"temp_{uuid.uuid4().hex[:8]}.txt"
        temp_file_path = os.path.join(temp_dir, temp_filename)

        # 返回相对路径（用于显示）
        return f"temp/{temp_filename}"

    async def _save_to_temp_file(self, content: str, temp_path: str) -> None:
        """
        将内容保存到临时文件

        Args:
            content: 要保存的内容
            temp_path: 临时文件路径（相对路径）
        """
        import os
        full_path = os.path.join(self.root_dir, temp_path)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

    async def _format_output_with_limit(self, command: str, output: str, max_lines: int = 200) -> tuple[str, str]:
        """
        格式化输出，限制最大行数（防爆设计）

        Args:
            command: 执行的命令
            output: 命令输出
            max_lines: 最大行数（默认 200）

        Returns:
            tuple[str, str]: (格式化后的显示结果, 实际累积到 operation_results 的结果)
        """
        lines = output.split('\n')
        total_lines = len(lines)

        if total_lines <= max_lines:
            # 输出较小，直接返回
            formatted = f"> {command}\n{output}"
            return formatted, formatted

        # 输出过大，需要截断
        preview_lines = lines[:max_lines]
        preview_output = '\n'.join(preview_lines)

        # 创建临时文件
        temp_path = await self._create_temp_file()
        await self._save_to_temp_file(output, temp_path)

        # 构造提示信息
        import os
        temp_file_full = os.path.join(self.root_dir, temp_path)
        file_size = os.path.getsize(temp_file_full)
        if file_size < 1024:
            size_str = f"{file_size} bytes"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f}KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f}MB"

        # 显示结果
        display_result = f"> {command}\n{preview_output}\n\n# 输出已截断（共 {total_lines} 行，{size_str}）\n# 完整输出已保存到: {temp_path}\n# 查看完整输出: cat {temp_path}"

        # 累积结果（包含截断提示）
        accumulated_result = display_result

        return display_result, accumulated_result

    async def _exec_shell(self, command: str) -> str:
        """
        执行 shell 命令（不累积到 operation_results）

        用于获取元数据等不需要显示给用户的操作

        Args:
            command: shell 命令

        Returns:
            str: 命令输出（stdout + stderr）
        """
        import os
        import re

        # ===== 安全检查 =====
        security_error = self._check_command_security(command)
        if security_error:
            return security_error

        # ===== 执行命令 =====
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=self.root_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )

            stdout, stderr = await process.communicate()

            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                output += "\n" + stderr.decode('utf-8', errors='replace')

            return output if output else "命令执行成功，无输出"

        except Exception as e:
            return f"命令执行失败: {str(e)}"

    async def _run_shell(self, command: str, operation_name: str = "操作",
                        enable_limit: bool = True, custom_prefix: str = "") -> str:
        """
        执行 shell 命令（带安全检查，并累积到 operation_results）

        安全特性：
        1. 检查危险命令模式
        2. 检查路径逃逸（防止访问 root_dir 之外）
        3. 所有命令在 root_dir 下执行

        Args:
            command: shell 命令
            operation_name: 操作名称（保留参数兼容性，暂未使用）
            enable_limit: 是否启用行数限制防爆（默认 True）
            custom_prefix: 自定义前缀注释（用于 read 等需要额外信息的场景）

        Returns:
            str: 命令输出（stdout + stderr）
        """
        import os
        import re

        # ===== 安全检查 =====
        security_error = self._check_command_security(command)
        if security_error:
            # 安全错误也格式化为终端输出
            formatted_result = f"> {command}\n{security_error}"
            self.operation_results.append(formatted_result)
            return security_error

        # ===== 执行命令 =====
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=self.root_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )

            stdout, stderr = await process.communicate()

            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                output += "\n" + stderr.decode('utf-8', errors='replace')

            result = output if output else "命令执行成功，无输出"

            # ===== 防爆处理 =====
            if enable_limit:
                display_result, accumulated_result = await self._format_output_with_limit(
                    command,
                    result if not custom_prefix else custom_prefix + "\n" + result
                )
            else:
                # 不启用防爆，直接格式化
                if custom_prefix:
                    formatted_result = f"> {command}\n{custom_prefix}\n{result}"
                else:
                    formatted_result = f"> {command}\n{result}"
                display_result = formatted_result
                accumulated_result = formatted_result

            # 累积操作结果（纯净终端格式：命令 + 输出）
            self.operation_results.append(accumulated_result)

            return display_result

        except Exception as e:
            error_msg = f"命令执行失败: {str(e)}"
            # 错误也格式化为终端输出
            formatted_result = f"> {command}\n{error_msg}"
            self.operation_results.append(formatted_result)
            return error_msg

    def _check_command_security(self, command: str) -> Optional[str]:
        """
        检查命令安全性

        Returns:
            Optional[str]: 如果不安全，返回错误信息；如果安全，返回 None
        """
        import os
        import re

        # 1. 检查危险命令模式
        dangerous_patterns = [
            # 系统破坏
            "rm -rf /",
            "rm -rf ~",
            "rm -rf ..",
            "mkfs",
            "dd if=/dev/",
            "format c:",
            "del /q",

            # 路径逃逸
            "..",           # 不允许父目录访问
            "~",            # 不允许访问 home 目录
            "/etc/",        # 不允许访问系统配置（除非绝对路径）
            "C:\\Windows",  # 不允许访问 Windows 系统目录
            "C:\\System32", # 不允许访问系统32

            # 管道和重定向到危险位置
            "> /dev/",
            "> /etc/",
            "> ~/",
            "> C:\\Windows",
            "> C:\\System32",
        ]

        # 检查危险模式（但允许在安全上下文中使用）
        # 例如：允许 "grep -r 'pattern' ." 但不允许 "cat /etc/passwd"
        for pattern in dangerous_patterns:
            if pattern in command:
                # 特殊处理：如果是相对路径的 ".."，直接拒绝
                if pattern == "..":
                    return f"安全错误：不允许使用父目录访问 (..)"
                if pattern == "~":
                    return f"安全错误：不允许访问 home 目录 (~)"
                return f"安全错误：检测到危险操作模式 ({pattern})"

        # 2. 检查是否尝试访问 root_dir 之外
        # 提取命令中的路径
        abs_root = os.path.abspath(self.root_dir)

        # 匹配可能的路径模式
        # Unix: /path/to/file, ./file, ../file, "path", 'path'
        # Windows: C:\path, path\file, "path", 'path'
        path_pattern = r'''['"]?([a-zA-Z]:?[\\/][\w\-./\\]+)['"]?|['"]?([\w\-./]+)['"]?'''
        matches = re.findall(path_pattern, command)

        for match_tuple in matches:
            for match in match_tuple:
                if not match:
                    continue

                # 跳过非路径（如命令名）
                if match in ["ls", "dir", "cat", "type", "grep", "find", "findstr"]:
                    continue

                # 解析为绝对路径
                if os.path.isabs(match):
                    abs_path = os.path.abspath(match)
                else:
                    # 相对于 root_dir 解析
                    abs_path = os.path.abspath(os.path.join(self.root_dir, match))

                # 检查是否在 root_dir 内
                if not abs_path.startswith(abs_root):
                    return f"安全错误：不允许访问 {match} (超出工作目录 {self.root_dir})"

        # 3. 所有检查通过
        return None

    async def _generate_command_with_retry(
        self,
        prompt: str,
        parser_context: str
    ) -> str:
        """
        使用 think_with_retry 让 LLM 生成命令

        Args:
            prompt: 提示词
            parser_context: 解析器上下文（用于区分不同场景）

        Returns:
            str: 生成的命令
        """
        # 使用 brain 的 think_with_retry
        # 注意：直接传函数引用，通过 parser_kwargs 传递额外参数
        command = await self.brain.think_with_retry(
            initial_messages=prompt,
            parser=self._parse_shell_command,
            context=parser_context,
            max_retries=3
        )

        return command

    def _parse_shell_command(self, raw_reply: str, **kwargs) -> Dict[str, Any]:
        """
        解析 LLM 输出的 shell 命令

        从 [COMMAND] 标记后提取命令

        Args:
            raw_reply: LLM 的原始输出
            **kwargs: 额外参数（通过 parser_kwargs 传递）
                - context: 解析上下文（用于错误提示）

        Returns:
            dict: {"status": "success" | "error", "content" | "feedback"}
        """
        context = kwargs.get('context', '未知场景')
        try:
            # 查找 [COMMAND] 标记
            if "[COMMAND]" in raw_reply:
                parts = raw_reply.split("[COMMAND]", 1)
                command_part = parts[1].strip()

                # 移除可能的后续标记
                for marker in ["[CONTENT]", "[END]", "[EXPLANATION]", "```"]:
                    if marker in command_part:
                        command_part = command_part.split(marker)[0].strip()

                # 清理 markdown 代码块标记
                command_part = command_part.strip()
                if command_part.startswith("```"):
                    lines = command_part.split("\n", 1)
                    command_part = lines[1] if len(lines) > 1 else command_part
                if command_part.endswith("```"):
                    command_part = command_part.rsplit("\n", 1)[0]
                if command_part.startswith(("bash", "powershell", "sh")):
                    lines = command_part.split("\n", 1)
                    command_part = lines[1] if len(lines) > 1 else command_part

                return {"status": "success", "content": command_part.strip()}

            # 如果没有标记，返回错误
            return {
                "status": "error",
                "feedback": f"未找到 [COMMAND] 标记。请在输出中使用 [COMMAND] 标记来指示命令部分。\n\n场景: {context}"
            }

        except Exception as e:
            return {
                "status": "error",
                "feedback": f"解析命令失败: {str(e)}\n\n场景: {context}"
            }

    def _parse_command_and_content(self, raw_reply: str) -> Dict[str, Any]:
        """
        解析 write_file 的命令和内容

        提取 [COMMAND] 和 [CONTENT] 部分

        Returns:
            dict: {"status": "success" | "error", "content" | "feedback"}
        """
        try:
            from ..skills.parser_utils import multi_section_parser

            result = multi_section_parser(
                raw_reply,
                section_headers=["[COMMAND]", "[CONTENT]"],
                match_mode="ALL"
            )

            if result["status"] == "success":
                command = result["content"]["[COMMAND]"].strip()
                content = result["content"]["[CONTENT]"].strip()

                # 组合成完整的可执行命令
                full_command = self._combine_command_and_content(command, content)

                return {"status": "success", "content": full_command}

            return {
                "status": "error",
                "feedback": "未找到必需的 [COMMAND] 和 [CONTENT] 标记。请使用这两个标记来分别指示命令和内容。"
            }

        except Exception as e:
            return {
                "status": "error",
                "feedback": f"解析失败: {str(e)}。请使用 [COMMAND] 和 [CONTENT] 标记。"
            }

    def _combine_command_and_content(self, command: str, content: str) -> str:
        """
        组合命令和内容

        子类可以重写此方法来实现特定的组合逻辑
        """
        # 默认：直接拼接（适用于 heredoc 等格式）
        return f"{command}\n{content}"


# ==================== Unix/Linux/macOS 实现 ====================

class _UnixFileMicroAgent(_FileMicroAgentBase):
    """
    Unix/Linux/macOS 版本的 File Micro Agent
    """

    @property
    def system_name(self) -> str:
        return "Unix"

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
        base_dir = directory or "."

        if recursive:
            # 递归显示：使用 ls -lhR (递归、长格式、人类可读大小)
            cmd = f"ls -lhR {base_dir}"
        else:
            # 单层显示：使用 ls -lho (长格式、人类可读大小、省略组名)
            cmd = f"ls -lho {base_dir}"

        return await self._run_shell(cmd, f"列出目录: {directory or '当前目录'}")

    async def read(self, file_path: str, start_line: Optional[int] = 1, end_line: Optional[int] = 200) -> str:
        """
        读取文件内容（支持指定行范围）

        Args:
            file_path: 文件路径
            start_line: 起始行号（从 1 开始，默认 1）
            end_line: 结束行号（默认 200，最多读取 200 行）
        """
        # 获取文件统计信息（不显示给用户）
        stat_cmd = f"wc -l \"{file_path}\" && ls -l \"{file_path}\""
        stat_result = await self._exec_shell(stat_cmd)

        # 解析总行数
        import re
        total_lines = 0
        file_size = ""

        # 从 wc 输出提取行数
        wc_match = re.search(r'^\s*(\d+)', stat_result.split('\n')[0])
        if wc_match:
            total_lines = int(wc_match.group(1))

        # 从 ls 输出提取文件大小
        ls_lines = stat_result.split('\n')
        if len(ls_lines) > 1:
            ls_parts = ls_lines[1].split()
            if len(ls_parts) >= 5:
                file_size = ls_parts[4]

        # 调整 end_line：不超过文件总行数
        actual_end_line = min(end_line, total_lines) if total_lines > 0 else end_line
        lines_to_read = actual_end_line - start_line + 1

        # 准备读取命令和说明
        if total_lines > end_line:
            # 文件大于请求的范围：显示指定范围，并标注还有更多内容
            cmd = f"sed -n '{start_line},{actual_end_line}p' \"{file_path}\""
            comment = f"# 文件: {file_path} ({file_size}, 共 {total_lines} 行)\n# 显示第 {start_line}-{actual_end_line} 行（已截断）\n\n"
        elif start_line > 1:
            # 从中间开始读取
            cmd = f"sed -n '{start_line},{actual_end_line}p' \"{file_path}\""
            comment = f"# 文件: {file_path} ({file_size}, 共 {total_lines} 行)\n# 显示第 {start_line}-{actual_end_line} 行\n\n"
        else:
            # 读取全部（文件较小）
            cmd = f"cat \"{file_path}\""
            comment = f"# 文件: {file_path} ({file_size}, 共 {total_lines} 行)\n\n"

        # 执行读取命令（使用 custom_prefix 传递文件信息注释，不使用防爆）
        read_result = await self._run_shell(
            cmd,
            f"读取文件: {file_path}",
            enable_limit=False,
            custom_prefix=comment.strip()
        )

        return comment + read_result

    async def write(self, file_path: str, content: str, mode: str = "overwrite", allow_overwrite: bool = False) -> str:
        """
        写入文件内容（使用 heredoc 格式，安全处理特殊字符）

        Args:
            file_path: 文件路径
            content: 文件内容
            mode: 写入模式，'overwrite' 覆盖或 'append' 追加（默认 overwrite）
            allow_overwrite: 是否允许覆盖已存在文件（默认 False）
        """
        # 检查文件是否存在
        check_cmd = f"test -f \"{file_path}\" && echo 'exists' || echo 'not_exists'"
        result = await self._exec_shell(check_cmd)
        file_exists = result.strip() == "exists"

        # 如果文件存在，检查是否允许覆盖
        if file_exists and mode == "overwrite" and not allow_overwrite:
            return f"> 检查文件: {file_path}\n错误：原文件存在，如果要覆盖，请明确指定 allow_overwrite=True"

        # 生成写入命令
        if mode == "append":
            # 追加模式
            redirect_op = ">>"
            mode_desc = "追加"
        else:
            # 覆盖模式（文件不存在或允许覆盖）
            redirect_op = ">"
            mode_desc = "覆盖" if file_exists else "创建"

        prompt = f"""用户要求{mode_desc}文件：
- 文件路径: {file_path}
- 内容长度: {len(content)} 字符
- 写入模式: {mode}

请生成一个 shell 命令来完成这个操作。

要求：
1. 使用 heredoc 格式（最安全、最可靠）
2. 使用 {redirect_op} 进行{"追加" if mode == "append" else "覆盖"}
3. 示例格式：

[COMMAND]
cat {redirect_op} {file_path} << 'EOF'
[CONTENT]
{content}
EOF

只返回命令和内容，不要解释。
"""

        # 使用 think_with_retry
        full_command = await self.brain.think_with_retry(
            initial_messages=prompt,
            parser=self._parse_command_and_content,
            max_retries=3
        )

        return await self._run_shell(full_command, f"{'追加到' if mode == 'append' else '写入文件'}: {file_path}")

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
        base_dir = directory or "."

        if target == "filename":
            # 按文件名搜索（使用 find）
            cmd = f"find {base_dir}"

            # 递归控制
            if not recursive:
                cmd += " -maxdepth 1"

            # 检测 pattern 类型（正则 vs glob）
            regex_chars = ['^', '$', '|', '\\', '[', ']', '(', ')']
            is_regex = any(char in pattern for char in regex_chars)

            if is_regex:
                # 正则表达式模式
                if not pattern.startswith('.*'):
                    pattern = f".*{pattern}"
                cmd += f' -regex "{pattern}"'
            else:
                # Glob 模式
                cmd += f' -name "{pattern}"'

            # 只显示文件（不显示目录）
            cmd += ' -type f'

            return await self._run_shell(cmd, f"按文件名搜索: {pattern}")

        else:  # target == "content"
            # 在文件内容中搜索（使用 grep）
            # -n: 显示行号
            if recursive:
                cmd = f'grep -rn "{pattern}" {base_dir}'
            else:
                cmd = f'grep -n "{pattern}" {base_dir}/*'

            return await self._run_shell(cmd, f"在文件中搜索: {pattern}")

    async def shell_cmd(self, command: str) -> str:
        """
        直接执行 shell 命令（仅限白名单命令）

        白名单命令：ls, cat, head, tail, sed, grep, find

        Args:
            command: shell 命令

        Returns:
            str: 命令输出
        """
        # 白名单命令（对应现有 action）
        whitelist = {
            'ls', 'cat', 'head', 'tail', 'sed',  # 对应 read
            'grep', 'find',  # 对应 search
        }

        # 提取命令名（第一个单词）
        import shlex
        try:
            parts = shlex.split(command)
            cmd_name = parts[0] if parts else ""
        except:
            # 简单提取（空格分割）
            cmd_name = command.split()[0] if command.split() else ""

        # 检查是否在白名单中
        if cmd_name not in whitelist:
            return f"错误：命令 '{cmd_name}' 不在允许的白名单中。\n允许的命令：{', '.join(sorted(whitelist))}"

        # 执行命令（使用 _run_shell 的默认防爆功能）
        return await self._run_shell(command, f"执行命令: {command}")

    async def all_finished(self, result: str) -> str:
        """完成任务"""
        return result


# 为 _UnixFileMicroAgent 的方法添加元数据
_UnixFileMicroAgent.list_dir._action_desc = "列出目录内容。可选择只列出当前层或递归列出所有子目录"
_UnixFileMicroAgent.list_dir._action_param_infos = {
    "directory": "目录路径（可选，默认当前目录）",
    "recursive": "是否递归列出子目录（可选，默认 false）"
}

_UnixFileMicroAgent.read._action_desc = "读取文件内容。可指定读取行范围（默认读取前 200 行）。会显示文件统计信息（大小、总行数）"
_UnixFileMicroAgent.read._action_param_infos = {
    "file_path": "文件路径",
    "start_line": "起始行号（可选，默认 1）",
    "end_line": "结束行号（可选，默认 200，最多读取 200 行）"
}

_UnixFileMicroAgent.write._action_desc = "写入内容到文件。支持覆盖写入或追加模式。如果要覆盖已存在的文件，必须明确说明允许覆盖"
_UnixFileMicroAgent.write._action_param_infos = {
    "file_path": "文件路径",
    "content": "文件内容",
    "mode": "写入模式（可选，默认 'overwrite'）。可选值：'overwrite' 覆盖，'append' 追加",
    "allow_overwrite": "是否允许覆盖已存在文件（可选，默认 False）。如果文件存在且mode为overwrite，必须设置为True才能覆盖"
}

_UnixFileMicroAgent.search._action_desc = "搜索文件或内容。可选择按文件名搜索（支持 Glob 模式如 *.txt）或在文件内容中搜索关键词（支持正则表达式）。默认在文件内容中搜索。可选择递归或非递归搜索"
_UnixFileMicroAgent.search._action_param_infos = {
    "target": "搜索目标（可选，默认 'content'）。可选值：'filename' 表示按文件名搜索，'content' 表示在文件内容中搜索",
    "pattern": "搜索patter或者text。如果 target='filename'，则支持 Glob 模式（如 *.txt）或正则表达式（如 .*\\.txt$）；如果 target='content'，则为要搜索的关键词或文本（支持 grep 正则语法）",
    "directory": "搜索目录（可选，默认当前目录）",
    "recursive": "是否递归搜索（可选，默认 true）"
}

_UnixFileMicroAgent.shell_cmd._action_desc = "直接执行 shell 命令（仅限白名单命令：ls, cat, head, tail, sed, grep, find）。适用于 Agent 直接给出 shell 命令的场景"
_UnixFileMicroAgent.shell_cmd._action_param_infos = {
    "command": "要执行的 shell 命令（必须在白名单中）"
}

_UnixFileMicroAgent.all_finished._action_desc = "完成任务并返回结果"
_UnixFileMicroAgent.all_finished._action_param_infos = {
    "result": "最终结果"
}


# ==================== Windows 实现 ====================

class _WindowsFileMicroAgent(_FileMicroAgentBase):
    """
    Windows 版本的 File Micro Agent
    """

    @property
    def system_name(self) -> str:
        return "Windows"

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
        base_dir = directory or "."

        if recursive:
            # 递归显示：简洁路径列表
            cmd = f"dir /s /b {base_dir}"
        else:
            # 单层显示：日期降序、无千位分隔符
            cmd = f"dir /o:-d /-c {base_dir}"

        return await self._run_shell(cmd, f"列出目录: {directory or '当前目录'}")

    async def read(self, file_path: str, start_line: Optional[int] = 1, end_line: Optional[int] = 200) -> str:
        """
        读取文件内容（支持指定行范围）

        Args:
            file_path: 文件路径
            start_line: 起始行号（从 1 开始，默认 1）
            end_line: 结束行号（默认 200，最多读取 200 行）
        """
        # 使用 PowerShell 获取文件统计信息（不显示给用户）
        stat_cmd = f'powershell -Command "$lines = (Get-Content \'{file_path}\').Count; $size = (Get-Item \'{file_path}\').Length; Write-Output \"$lines $size\""'
        stat_result = await self._exec_shell(stat_cmd)

        # 解析统计信息
        parts = stat_result.strip().split()
        total_lines = int(parts[0]) if len(parts) > 0 else 0
        size_bytes = int(parts[1]) if len(parts) > 1 else 0

        # 格式化文件大小
        if size_bytes < 1024:
            file_size = f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            file_size = f"{size_bytes / 1024:.1f}KB"
        else:
            file_size = f"{size_bytes / (1024 * 1024):.1f}MB"

        # 调整 end_line：不超过文件总行数
        actual_end_line = min(end_line, total_lines) if total_lines > 0 else end_line

        # 准备读取命令和说明
        if total_lines > end_line:
            # 文件大于请求的范围：显示指定范围，并标注还有更多内容
            cmd = f'powershell -Command "Get-Content \'{file_path}\' | Select-Object -Index {start_line-1}..{actual_end_line-1}"'
            comment = f"# 文件: {file_path} ({file_size}, 共 {total_lines} 行)\n# 显示第 {start_line}-{actual_end_line} 行（已截断）\n\n"
        elif start_line > 1:
            # 从中间开始读取
            cmd = f'powershell -Command "Get-Content \'{file_path}\' | Select-Object -Index {start_line-1}..{actual_end_line-1}"'
            comment = f"# 文件: {file_path} ({file_size}, 共 {total_lines} 行)\n# 显示第 {start_line}-{actual_end_line} 行\n\n"
        else:
            # 读取全部（文件较小）
            cmd = f"type {file_path}"
            comment = f"# 文件: {file_path} ({file_size}, 共 {total_lines} 行)\n\n"

        # 执行读取命令（使用 custom_prefix 传递文件信息注释，不使用防爆）
        read_result = await self._run_shell(
            cmd,
            f"读取文件: {file_path}",
            enable_limit=False,
            custom_prefix=comment.strip()
        )

        return comment + read_result

    async def write(self, file_path: str, content: str, mode: str = "overwrite", allow_overwrite: bool = False) -> str:
        """
        写入文件内容（使用 PowerShell here-string 格式，安全处理特殊字符）

        Args:
            file_path: 文件路径
            content: 文件内容
            mode: 写入模式，'overwrite' 覆盖或 'append' 追加（默认 overwrite）
            allow_overwrite: 是否允许覆盖已存在文件（默认 False）
        """
        # 检查文件是否存在
        check_cmd = f"if exist \"{file_path}\" (echo exists) else (echo not_exists)"
        result = await self._exec_shell(check_cmd)
        file_exists = result.strip() == "exists"

        # 如果文件存在，检查是否允许覆盖
        if file_exists and mode == "overwrite" and not allow_overwrite:
            return f"> 检查文件: {file_path}\n错误：原文件存在，如果要覆盖，请明确指定 allow_overwrite=True"

        # 生成写入命令
        if mode == "append":
            # 追加模式使用 Add-Content
            cmdlet = "Add-Content"
            mode_desc = "追加"
        else:
            # 覆盖模式使用 Out-File
            cmdlet = "Out-File"
            mode_desc = "覆盖" if file_exists else "创建"

        prompt = f"""用户要求{mode_desc}文件：
- 文件路径: {file_path}
- 内容长度: {len(content)} 字符
- 写入模式: {mode}

请生成一个 PowerShell 命令来完成这个操作。

要求：
1. 使用 PowerShell 的 here-string 格式（@" "@）
2. 使用 {cmdlet} cmdlet 进行{"追加" if mode == "append" else "覆盖"}
3. 示例格式：

[COMMAND]
powershell -Command "@\"
{content}
@\" | {cmdlet} -Encoding UTF8 {file_path}

只返回命令，不要解释。
"""

        # 使用 think_with_retry
        full_command = await self.brain.think_with_retry(
            initial_messages=prompt,
            parser=self._parse_command_and_content,
            max_retries=3
        )

        return await self._run_shell(full_command, f"{'追加到' if mode == 'append' else '写入文件'}: {file_path}")

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
        base_dir = directory or "."

        if target == "filename":
            # 按文件名搜索（使用 dir）
            recursive_flag = "/s" if recursive else ""
            cmd = f'dir {recursive_flag} /b "{pattern}"'

            return await self._run_shell(cmd, f"按文件名搜索: {pattern}")

        else:  # target == "content"
            # 在文件内容中搜索（使用 findstr）
            # /n: 显示行号
            recursive_flag = "/s" if recursive else ""
            cmd = f'findstr {recursive_flag} /n /c:"{pattern}" *'

            return await self._run_shell(cmd, f"在文件中搜索: {pattern}")

    async def shell_cmd(self, command: str) -> str:
        """
        直接执行 shell 命令（仅限白名单命令）

        白名单命令：dir, type, powershell, findstr

        Args:
            command: shell 命令

        Returns:
            str: 命令输出
        """
        # 白名单命令（对应现有 action）
        whitelist = {
            'dir', 'type',  # 对应 read
            'findstr',  # 对应 search
        }

        # 提取命令名（第一个单词）
        import shlex
        try:
            parts = shlex.split(command)
            cmd_name = parts[0] if parts else ""
        except:
            # 简单提取（空格分割）
            cmd_name = command.split()[0] if command.split() else ""

        # 检查是否在白名单中
        if cmd_name not in whitelist:
            return f"错误：命令 '{cmd_name}' 不在允许的白名单中。\n允许的命令：{', '.join(sorted(whitelist))}"

        # 执行命令（使用 _run_shell 的默认防爆功能）
        return await self._run_shell(command, f"执行命令: {command}")

    async def all_finished(self, result: str) -> str:
        """完成任务"""
        return result


# 为 _WindowsFileMicroAgent 的方法添加元数据
_WindowsFileMicroAgent.list_dir._action_desc = "列出目录内容。可选择只列出当前层或递归列出所有子目录"
_WindowsFileMicroAgent.list_dir._action_param_infos = {
    "directory": "目录路径（可选，默认当前目录）",
    "recursive": "是否递归列出子目录（可选，默认 false）"
}

_WindowsFileMicroAgent.read._action_desc = "读取文件内容。可指定读取行范围（默认读取前 200 行）。会显示文件统计信息（大小、总行数）"
_WindowsFileMicroAgent.read._action_param_infos = {
    "file_path": "文件路径",
    "start_line": "起始行号（可选，默认 1）",
    "end_line": "结束行号（可选，默认 200，最多读取 200 行）"
}

_WindowsFileMicroAgent.write._action_desc = "写入内容到文件。支持覆盖写入或追加模式。如果要覆盖已存在的文件，必须明确说明允许覆盖"
_WindowsFileMicroAgent.write._action_param_infos = {
    "file_path": "文件路径",
    "content": "文件内容",
    "mode": "写入模式（可选，默认 'overwrite'）。可选值：'overwrite' 覆盖，'append' 追加",
    "allow_overwrite": "是否允许覆盖已存在文件（可选，默认 False）。如果文件存在且mode为overwrite，必须设置为True才能覆盖"
}

_WindowsFileMicroAgent.search._action_desc = "搜索文件或内容。可选择按文件名搜索（支持 Glob 模式如 *.txt）或在文件内容中搜索关键词。默认在文件内容中搜索。可选择递归或非递归搜索"
_WindowsFileMicroAgent.search._action_param_infos = {
    "pattern": "搜索模式。如果 target='filename'，则支持 Glob 模式（如 *.txt）；如果 target='content'，则为要搜索的关键词或文本",
    "target": "搜索目标（可选，默认 'content'）。可选值：'filename' 表示按文件名搜索，'content' 表示在文件内容中搜索",
    "directory": "搜索目录（可选，默认当前目录）",
    "recursive": "是否递归搜索（可选，默认 true）"
}

_WindowsFileMicroAgent.shell_cmd._action_desc = "直接执行 shell 命令（仅限白名单命令：dir, type, findstr）。适用于 Agent 直接给出 shell 命令的场景"
_WindowsFileMicroAgent.shell_cmd._action_param_infos = {
    "command": "要执行的 shell 命令（必须在白名单中）"
}

_WindowsFileMicroAgent.all_finished._action_desc = "完成任务并返回结果"
_WindowsFileMicroAgent.all_finished._action_param_infos = {
    "result": "最终结果"
}



# ==================== 工厂函数 ====================

def create_file_micro_agent(
    session_dir: str,
    brain: LLMClient,
    cerebellum: Any,
    default_max_steps: int = 10
) -> _FileMicroAgentBase:
    """
    工厂函数：根据当前操作系统创建对应的 File Micro Agent

    Args:
        session_dir: session 目录路径（文件操作根目录）
        brain: LLM 接口
        cerebellum: 参数协商器
        default_max_steps: 默认最大步数

    Returns:
        _FileMicroAgentBase: 对应系统的 File Micro Agent 实例
    """
    system = platform.system()

    if system == "Windows":
        return _WindowsFileMicroAgent(session_dir, brain, cerebellum, default_max_steps)
    else:
        # Unix-like 系统（Linux, macOS, Darwin, etc.）
        return _UnixFileMicroAgent(session_dir, brain, cerebellum, default_max_steps)


# ==================== Skill Mixin ====================

class FileOperationSkillMixin:
    """
    File Operation Skill Mixin

    暴露 file_operation action 给主 Agent

    注意：这个 mixin 会自动使用当前 Agent 的 session 目录
    """

    @register_action(
        description="执行文件操作。支持列目录、读写文件和搜索操作",
        param_infos={
            "operation_description": "自然语言描述的文件操作，例如：'列出当前目录的所有文件'、'读取 config.txt 的内容'、'创建文件 test.md，内容为 # 标题'"
        }
    )
    async def file_operation(self, operation_description: str) -> str:
        """
        执行文件操作（在当前 session 目录下）

        这是主 Agent 看到的唯一接口

        Args:
            operation_description: 自然语言描述的文件操作

        Returns:
            str: 操作结果

        示例:
            - "读取 overall_dashboard.md 的内容"
            - "在 Notebook 目录下创建新章节"
            - "搜索所有包含'机器学习'的文件"
        """
        # 获取当前 session 目录（从 BaseAgent 的 current_session_folder）
        session_dir = getattr(self, 'current_session_folder', None)

        if not session_dir:
            # 如果没有 session 目录，使用 workspace_root 作为降级方案
            workspace_root = getattr(self, 'workspace_root', None)
            if workspace_root:
                session_dir = workspace_root
            else:
                # 都没有，使用当前目录
                session_dir = '.'

        # 使用工厂函数创建 File Micro Agent（传递 session 目录）
        file_micro_agent = create_file_micro_agent(
            session_dir=session_dir,  # ← 使用 session 目录，而不是 workspace_root
            brain=self.brain,
            cerebellum=self.cerebellum
        )

        # 清空之前的操作结果
        file_micro_agent.operation_results = []

        # 执行任务（返回值被忽略，因为我们使用 operation_results）
        await file_micro_agent.execute(
            persona="你是文件操作专家。擅长理解用户的文件操作要求，将其对应为具体的Action。用户很清楚自己要做什么，所以只需要按照要求选择正确Action并整理好参数即可，不用担心前置条件。有问题再汇报。如果用户要求没法用你拥有的Action完成，就告诉用户无法完成。",

            task=f"现在用户要求执行文件操作：\n====begin====\n{operation_description}\n\n====end=====\n\n请分析用户意图，选择合适的 action 执行操作。",

            available_actions=[
                "list_dir",
                "read",
                "write",
                "search",
                "shell_cmd",
                "all_finished"
            ],

            max_steps=10
        )

        # 返回累积的原始 shell 输出结果
        if file_micro_agent.operation_results:
            # 如果有多个操作结果，用换行符连接
            return "\n\n".join(file_micro_agent.operation_results)
        else:
            return "文件操作完成"
