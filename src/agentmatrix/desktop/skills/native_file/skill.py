"""
Native File Operation Skill - 宿主机直接执行版本

与 FileSkillMixin 功能完全一致，但所有操作在宿主机上直接执行：
- 通过 LocalSession（持久本地 bash）执行命令
- 路径即宿主机路径，无需容器路径转换
- 写入文件直接用 Python I/O

用于 LocalFileAgent（如 BrowserCollabAgent）的文件操作。
"""

import asyncio
import base64
import shlex
from pathlib import Path
from typing import Optional
from agentmatrix.core.action import register_action


class Native_fileSkillMixin:
    """
    Native File Operation Skill Mixin (宿主机直接执行版本)

    与 FileSkillMixin 接口一致，通过 local_session 在宿主机执行。
    """

    _skill_description = """本地文件操作技能（直接操作宿主机文件）。当前任务的工作目录在`~/current_task`, 临时文件放`~/current_task/tmp`, 任务输出放`~/current_task/output`. 发给他人的附件要留好copy。及时清理自己的临时文件，维护好系统的健康整洁。"""

    _skill_usage_guide = """本地文件操作技能。所有文件操作直接在宿主机上执行，路径即宿主机路径。当前任务的工作目录在`~/current_task`, 临时文件放`~/current_task/tmp`, 任务输出放`~/current_task/output`. 发给他人的附件要留好copy。及时清理自己的临时文件，维护好系统的健康整洁。"""

    # ==================== Actions ====================

    @register_action(
        short_desc="列目录[directory, recursive=False]",
        description="列出目录内容。支持单层或递归列出",
        param_infos={
            "directory": "目录路径（可选，默认当前目录）",
            "recursive": "是否递归列出子目录（默认False）",
        },
    )
    async def list_dir(
        self, directory: Optional[str] = None, recursive: bool = False
    ) -> str:
        local_session = self.root_agent.local_session
        work_dir = directory or "."
        safe_dir = self._shell_path(work_dir)
        if recursive:
            cmd = f"ls -lhR {safe_dir}"
        else:
            cmd = f"ls -lho {safe_dir}"

        exit_code, stdout, stderr = await asyncio.to_thread(
            local_session.execute, cmd
        )

        self.logger.info(f"[list_dir] 命令: {cmd}, exit_code: {exit_code}")

        if exit_code != 0:
            return f"列出目录失败\n- 命令: {cmd}\n- 退出码: {exit_code}\n- 错误: {stderr.strip() if stderr else '(空)'}"

        return stdout or "目录为空"

    @staticmethod
    def _shell_path(path: str) -> str:
        """Quote path for shell, but preserve ~ expansion."""
        if path.startswith("~/"):
            return "~/" + shlex.quote(path[2:])
        if path == "~":
            return "~"
        return shlex.quote(path)

    _BLOCKED_PATHS = ("/dev/", "/proc/", "/sys/")

    @register_action(
        short_desc="读取文本文件内容[file_path, start_line=1,end_line=200]",
        description="读取普通文本文件的内容（如 .py, .md, .txt, .json, .yaml 等）。支持指定行范围（默认前200行）。不可用于设备文件、管道等特殊路径。",
        param_infos={
            "file_path": "文本文件路径",
            "start_line": "起始行号（从1开始，默认1）",
            "end_line": "结束行号（默认200）",
        },
    )
    async def read_txt_file(
        self,
        file_path: str,
        start_line: Optional[int] = 1,
        end_line: Optional[int] = 200,
    ) -> str:
        if any(file_path.startswith(p) for p in self._BLOCKED_PATHS):
            return f"读取文件失败：路径 '{file_path}' 是特殊路径（设备文件/伪文件系统），不可读取。请使用普通文件路径。"

        local_session = self.root_agent.local_session
        safe_path = self._shell_path(file_path)
        cmd = f"sed -n '{start_line},{end_line}p' {safe_path}; echo '___WC_SEP___'; wc -l {safe_path}"

        exit_code, stdout, stderr = await asyncio.wait_for(
            asyncio.to_thread(local_session.execute, cmd, 30),
            timeout=35,
        )

        self.logger.info(f"[read_txt_file] 命令: {cmd}, exit_code: {exit_code}")

        if "___WC_SEP___" in stdout:
            content, wc_part = stdout.split("___WC_SEP___", 1)
            content = content.strip()
            total_lines = wc_part.strip().split()[0] if wc_part.strip() else "?"
        else:
            content = stdout
            total_lines = "?"

        if exit_code != 0:
            return f"读取文件失败\n- 文件: {file_path}\n- 退出码: {exit_code}\n- 错误: {stderr.strip() if stderr else '(空)'}"

        try:
            total = int(total_lines)
        except (ValueError, TypeError):
            total = None

        if total is not None and total > (end_line - start_line + 1):
            return f"# 文件: {file_path} (共 {total} 行，显示第 {start_line}-{end_line} 行)\n\n{content}"

        return content

    @register_action(
        short_desc="写入文件[file_path,content,mode='overwrite',allow_overwrite=False]",
        description="写入文件内容。默认覆盖模式。",
        param_infos={
            "file_path": "文件路径",
            "content": "文件内容",
            "mode": "写入模式，'overwrite' 覆盖或 'append' 追加（默认overwrite）",
            "allow_overwrite": "（可选）是否允许覆盖已存在文件（默认False）",
        },
    )
    async def write(
        self,
        file_path: str,
        content: str,
        mode: str = "overwrite",
        allow_overwrite: bool = False,
    ) -> str:
        # 宿主机直接写入，不需要路径转换
        host_path = Path(file_path).expanduser()

        if host_path.exists() and mode == "overwrite" and not allow_overwrite:
            return f"错误：文件已存在，如果要覆盖请设置 allow_overwrite=True\n  文件: {file_path}"

        host_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if mode == "append":
                with open(str(host_path), "a", encoding="utf-8") as f:
                    f.write(content)
            else:
                with open(str(host_path), "w", encoding="utf-8") as f:
                    f.write(content)

            self.logger.info(f"[write] 写入文件: {host_path}")
            mode_desc = "追加到" if mode == "append" else "写入"
            return f"成功{mode_desc} {file_path}\n"
        except Exception as e:
            self.logger.error(f"[write] 写入失败: {e}")
            return f"写入文件失败\n- 文件: {file_path}\n- 错误: {str(e)}"

    @register_action(
        short_desc="搜文件(详细用法看help)",
        description="搜索文件或文件里的内容。支持按文件名或文件内容搜索",
        param_infos={
            "pattern": "搜索模式（文件名模式或文本内容）",
            "target": "搜索目标，'content' 表示在文件内容中搜索，'filename' 表示按文件名搜索（默认content）",
            "directory": "搜索目录（可选，默认当前目录）",
            "recursive": "是否递归搜索（默认True）",
        },
    )
    async def search_file(
        self,
        pattern: str,
        target: str = "content",
        directory: Optional[str] = None,
        recursive: bool = True,
    ) -> str:
        local_session = self.root_agent.local_session
        work_dir = directory or "."
        safe_dir = self._shell_path(work_dir)

        if target == "filename":
            cmd = f"find {safe_dir}"
            if not recursive:
                cmd += " -maxdepth 1"
            cmd += f" -name '*{shlex.quote(pattern)[1:-1]}*'"
        else:
            if recursive:
                cmd = f"grep -rn {shlex.quote(pattern)} {safe_dir}"
            else:
                cmd = f"grep -n {shlex.quote(pattern)} {safe_dir}/*"

        exit_code, stdout, stderr = await asyncio.to_thread(
            local_session.execute, cmd
        )

        self.logger.info(f"[search_file] 命令: {cmd}, exit_code: {exit_code}")

        if exit_code != 0 and not stdout:
            return "未找到匹配结果"

        return stdout or "未找到匹配结果"

    @register_action(
        short_desc=(
            "执行bash命令或脚本（宿主机执行）。"
            "单行命令用普通引号: native_file.bash(command=\"ls -la\")。"
            "多行脚本或 heredoc 必须用 r\"\"\"...\"\"\" 包裹，内容用真实换行，不要用 \\n：\n"
            "native_file.bash(command=r\"\"\"python3 << 'EOF'\nprint('hello')\nEOF\"\"\")"
        ),
        description="执行bash命令或脚本（宿主机执行）",
        param_infos={
            "command": "bash 命令。多行/heredoc 用 r\"\"\"...\"\"\"（真实换行），单行用 \"...\"",
            "timeout": "超时秒数，默认3600",
        },
    )
    async def bash(self, command: str, timeout: int = 3600) -> str:
        local_session = self.root_agent.local_session

        await asyncio.to_thread(local_session.ensure_responsive)

        exit_code, stdout, stderr = await asyncio.to_thread(
            local_session.execute, command, timeout
        )

        self.logger.info(f"[bash] 命令: {command}, exit_code: {exit_code}")

        result = ""
        if stdout:
            result += stdout
        if stderr:
            result += f"\n{stderr}"

        if not result:
            return "Done（无输出）"

        return result

    @register_action(
        short_desc="文件内替换[file_path,old_pattern,new_string,use_regex=False]",
        description="字符串替换：在文件中查找并替换字符串。",
        param_infos={
            "file_path": "文件路径",
            "old_pattern": "要替换的旧字符串",
            "new_string": "新字符串",
            "use_regex": "是否使用正则表达式（默认false）",
        },
    )
    async def replace_string_in_file(
        self, file_path: str, old_pattern: str, new_string: str, use_regex: bool = False
    ) -> str:
        host_path = Path(file_path).expanduser()

        if not host_path.exists():
            return f"错误：文件不存在 {file_path}"

        try:
            with open(str(host_path), "r", encoding="utf-8") as f:
                content = f.read()

            if use_regex:
                import re
                count = len(re.findall(old_pattern, content))
                new_content = re.sub(old_pattern, new_string, content)
            else:
                count = content.count(old_pattern)
                new_content = content.replace(old_pattern, new_string)

            if count == 0:
                return f"未找到匹配内容，未做修改。old_pattern: {old_pattern[:100]}"

            with open(str(host_path), "w", encoding="utf-8") as f:
                f.write(new_content)

            self.logger.info(f"[replace] 替换: {host_path}, {count} 处")
            return f"已替换 {count} 处"

        except Exception as e:
            self.logger.error(f"[replace] 替换失败: {e}")
            return f"替换失败\n- 文件: {file_path}\n- 错误: {str(e)}"
