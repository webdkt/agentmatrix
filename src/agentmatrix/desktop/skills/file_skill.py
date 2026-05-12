"""
File Operation Skill - 容器内执行版本

核心设计：
- 所有文件操作在共享容器内以 Agent 用户身份执行
- 写入文件时，优先尝试将容器路径转换为宿主路径，直接在宿主上写入
- 这样可以避免管道操作导致的 broken pipe 问题
- Agent 在自己的工作目录中有完全权限（无白名单限制）
"""

import asyncio
import base64
import shlex
from pathlib import Path
from typing import Optional
from agentmatrix.core.action import register_action


class FileSkillMixin:
    """
    File Operation Skill Mixin (容器内执行版本)

    所有文件操作在共享容器内以 Agent 用户身份执行：
    - list_dir: 列出目录内容
    - read: 读取文件
    - write: 写入文件
    - search: 搜索文件或内容
    - bash: 执行 shell 命令
    """

    # Skill 级别元数据
    _skill_description = """文件操作技能。注意你和其他Agent共用同一个Linux环境，切勿直接修改他人文件。当前任务的工作目录在`~/current_task`, 临时文件放`~/current_task/tmp`, 任务输出放`~/current_task/output`. 发给他人的附件要留好copy。及时清理自己的临时文件，维护好系统的健康整洁。"""

    _skill_usage_guide = """
文件操作技能。注意你和其他Agent共用同一个Li文件操作技能。注意你和其他Agent共用同一个Linux环境，切勿直接修改他人文件。当前任务的工作目录在`~/current_task`, 临时文件放`~/current_task/tmp`, 任务输出放`~/current_task/output`. 发给他人的附件要留好copy。及时清理自己的临时文件，维护好系统的健康整洁。nux环境，切勿直接修改他人文件。及时清理自己的临时文件，维护好系统的健康和整洁。
"""

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
        """
        列出目录内容（容器内执行）

        Args:
            directory: 目录路径（默认当前目录）
            recursive: 是否递归列出子目录
        """
        container_session = self.root_agent.container_session

        # 默认当前目录
        work_dir = directory or "."

        # 构建命令
        safe_dir = self._shell_path(work_dir)
        if recursive:
            cmd = f"ls -lhR {safe_dir}"
        else:
            cmd = f"ls -lho {safe_dir}"

        # 在容器内执行（异步避免阻塞）
        exit_code, stdout, stderr = await asyncio.to_thread(
            container_session.execute, cmd
        )

        self.logger.info(f"[list_dir] 命令: {cmd}")
        self.logger.info(f"[list_dir] exit_code: {exit_code}")

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

    # 不可读取的路径（设备文件、伪文件系统等会阻塞或无意义）
    _BLOCKED_PATHS = ("/dev/", "/proc/", "/sys/")

    def _container_path_to_host(self, container_path: str) -> Optional[Path]:
        """
        将容器内路径转换为宿主路径（使用公共方法）

        Args:
            container_path: 容器内路径（如 ~/current_task/data.txt）

        Returns:
            宿主路径对象，如果路径无法转换则返回 None
        """
        agent_name = self.root_agent.name
        task_id = self.root_agent.current_task_id
        paths = self.root_agent.runtime.paths

        return paths.container_path_to_host(container_path, agent_name, task_id)

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
        """
        读取文本文件内容（容器内执行）

        Args:
            file_path: 文本文件路径
            start_line: 起始行号（从 1 开始，默认 1）
            end_line: 结束行号（默认 200）
        """
        # 黑名单检查：拒绝设备文件、伪文件系统等特殊路径
        if any(file_path.startswith(p) for p in self._BLOCKED_PATHS):
            return f"读取文件失败：路径 '{file_path}' 是特殊路径（设备文件/伪文件系统），不可读取。请使用普通文件路径。"

        container_session = self.root_agent.container_session

        # 使用 sed 读取指定行，合并 wc -l 为单次调用，加 30s 超时
        safe_path = self._shell_path(file_path)
        cmd = f"sed -n '{start_line},{end_line}p' {safe_path}; echo '___WC_SEP___'; wc -l {safe_path}"

        exit_code, stdout, stderr = await asyncio.wait_for(
            asyncio.to_thread(container_session.execute, cmd, 30),
            timeout=35,
        )

        self.logger.info(f"[read_txt_file] 命令: {cmd}")
        self.logger.info(f"[read_txt_file] exit_code: {exit_code}")

        # 解析合并输出
        if "___WC_SEP___" in stdout:
            content, wc_part = stdout.split("___WC_SEP___", 1)
            content = content.strip()
            total_lines = wc_part.strip().split()[0] if wc_part.strip() else "?"
        else:
            content = stdout
            total_lines = "?"

        if exit_code != 0:
            return f"读取文件失败\n- 文件: {file_path}\n- 退出码: {exit_code}\n- 错误: {stderr.strip() if stderr else '(空)'}"

        # 只有内容被截断时才加头部信息
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
        """
        写入文件内容（优先使用宿主路径直接写入，避免 broken pipe）

        Args:
            file_path: 文件路径
            content: 文件内容
            mode: 写入模式，'overwrite' 覆盖或 'append' 追加（默认 overwrite）
            allow_overwrite: 是否允许覆盖已存在文件（默认 False）
        """
        # 优先尝试将容器路径转换为宿主路径
        host_path = self._container_path_to_host(file_path)

        if host_path:
            # 可以直接在宿主上写入（避免 broken pipe）
            host_path_str = str(host_path)

            # 检查文件是否存在
            if host_path.exists() and mode == "overwrite" and not allow_overwrite:
                return f"错误：文件已存在，如果要覆盖请设置 allow_overwrite=True\n  文件: {file_path}"

            # 创建目录
            host_path.parent.mkdir(parents=True, exist_ok=True)

            # 直接写入（使用 Python，不需要通过容器）
            try:
                if mode == "append":
                    with open(host_path_str, "a", encoding="utf-8") as f:
                        f.write(content)
                else:
                    with open(host_path_str, "w", encoding="utf-8") as f:
                        f.write(content)

                self.logger.info(f"[write] 直接写入宿主文件: {host_path_str}")
                mode_desc = "追加到" if mode == "append" else "写入"
                return f"成功{mode_desc} {file_path}\n"
            except Exception as e:
                self.logger.error(f"[write] 宿主写入失败: {e}")
                return f"写入文件失败\n- 文件: {file_path}\n- 错误: {str(e)}"

        # 路径无法转换，回退到容器内写入（原来的逻辑）
        container_session = self.root_agent.container_session

        # 检查文件是否存在
        check_cmd = f"test -f {file_path} && echo 'exists' || echo 'not_exists'"
        exit_code, stdout, _ = await asyncio.to_thread(
            container_session.execute, check_cmd
        )
        file_exists = stdout.strip() == "exists"

        if file_exists and mode == "overwrite" and not allow_overwrite:
            return f"错误：文件已存在，如果要覆盖请设置 allow_overwrite=True\n  文件: {file_path}"

        # 创建目录（用 shell 变量赋值 + ${var%/*} 提取父目录，确保 ~ 被正确展开）
        dir_cmd = f"p={file_path}; mkdir -p \"${{p%/*}}\""
        await asyncio.to_thread(container_session.execute, dir_cmd)

        # 写入文件
        # 使用 base64 编码传递内容（避免转义问题）
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")

        if mode == "append":
            write_cmd = (
                f"echo {encoded_content} | base64 -d | tee -a {file_path} > /dev/null"
            )
        else:
            write_cmd = (
                f"echo {encoded_content} | base64 -d | tee {file_path} > /dev/null"
            )

        exit_code, stdout, stderr = await asyncio.to_thread(
            container_session.execute, write_cmd
        )

        self.logger.info(f"[write] 命令: {write_cmd}")
        self.logger.info(f"[write] exit_code: {exit_code}")

        if exit_code != 0:
            return f"写入文件失败\n- 文件: {file_path}\n- 退出码: {exit_code}\n- 错误: {stderr.strip() if stderr else '(空)'}"

        mode_desc = "追加到" if mode == "append" else "写入"
        return f"成功{mode_desc} {file_path}\n"

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
        """
        搜索文件或内容（容器内执行）

        Args:
            pattern: 搜索模式
            target: 搜索目标，"content" 表示在文件内容中搜索，"filename" 表示按文件名搜索
            directory: 搜索目录（默认当前目录）
            recursive: 是否递归搜索
        """
        container_session = self.root_agent.container_session

        # 默认当前目录
        work_dir = directory or "."
        safe_dir = self._shell_path(work_dir)

        if target == "filename":
            # 按文件名搜索
            cmd = f"find {safe_dir}"
            if not recursive:
                cmd += " -maxdepth 1"
            cmd += f" -name '*{shlex.quote(pattern)[1:-1]}*'"
        else:
            # 在文件内容中搜索
            if recursive:
                cmd = f"grep -rn {shlex.quote(pattern)} {safe_dir}"
            else:
                cmd = f"grep -n {shlex.quote(pattern)} {safe_dir}/*"

        exit_code, stdout, stderr = await asyncio.to_thread(
            container_session.execute, cmd
        )

        self.logger.info(f"[search_file] 命令: {cmd}")
        self.logger.info(f"[search_file] exit_code: {exit_code}")

        if exit_code != 0 and not stdout:
            return "未找到匹配结果"

        return stdout or "未找到匹配结果"

    @register_action(
        short_desc=(
            "执行bash命令或脚本（容器内执行）。"
            "单行命令用普通引号: file.bash(command=\"ls -la\")。"
            "多行脚本或 heredoc 必须用 r\"\"\"...\"\"\" 包裹，内容用真实换行，不要用 \\n：\n"
            "file.bash(command=r\"\"\"python3 << 'EOF'\nprint('hello')\nEOF\"\"\")"
        ),
        description="执行bash命令或脚本",
        param_infos={
            "command": "bash 命令。多行/heredoc 用 r\"\"\"...\"\"\"（真实换行），单行用 \"...\"",
            "timeout": "超时秒数，默认3600",
        },
    )
    async def bash(self, command: str, timeout: int = 3600) -> str:
        """
        执行 bash 命令或脚本（容器内执行）

        Args:
            command: bash 命令或脚本
            timeout: 超时时间（秒，默认3600）

        Returns:
            执行结果
        """
        container_session = self.root_agent.container_session

        # 执行前检查 shell 是否可响应，不可响应则自动重启
        await asyncio.to_thread(container_session.ensure_responsive)

        # 直接在容器内执行命令（无白名单限制）
        exit_code, stdout, stderr = await asyncio.to_thread(
            container_session.execute, command, timeout
        )

        self.logger.info(f"[bash] 命令: {command}")
        self.logger.info(f"[bash] exit_code: {exit_code}")

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
        """
        在文件中查找并替换字符串

        Args:
            file_path: 文件路径
            old_pattern: 要替换的旧字符串（或正则表达式）
            new_string: 新字符串
            use_regex: 是否使用正则表达式（默认false）
        """
        host_path = self._container_path_to_host(file_path)

        if host_path:
            # 宿主路径可用，直接用 Python 替换
            host_path_str = str(host_path)
            if not host_path.exists():
                return f"错误：文件不存在 {file_path}"

            try:
                with open(host_path_str, "r", encoding="utf-8") as f:
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

                with open(host_path_str, "w", encoding="utf-8") as f:
                    f.write(new_content)

                self.logger.info(f"[replace] 宿主文件替换: {host_path_str}, {count} 处")
                return f"已替换 {count} 处"

            except Exception as e:
                self.logger.error(f"[replace] 宿主替换失败: {e}")
                return f"替换失败\n- 文件: {file_path}\n- 错误: {str(e)}"

        # 回退到容器内执行 Python 脚本
        container_session = self.root_agent.container_session
        import json

        payload = json.dumps({"path": file_path, "old": old_pattern, "new": new_string, "regex": use_regex})
        script = (
            "import json, re, sys\n"
            "d = json.loads(sys.argv[1])\n"
            "with open(d['path'], 'r') as f: c = f.read()\n"
            "if d['regex']:\n"
            "    n = len(re.findall(d['old'], c))\n"
            "    c = re.sub(d['old'], d['new'], c)\n"
            "else:\n"
            "    n = c.count(d['old'])\n"
            "    c = c.replace(d['old'], d['new'])\n"
            "if n == 0: print(f'未找到匹配内容，未做修改'); sys.exit(0)\n"
            "with open(d['path'], 'w') as f: f.write(c)\n"
            "print(f'已替换 {n} 处')\n"
        )
        cmd = f"python3 -c {shlex.quote(script)} {shlex.quote(payload)}"
        exit_code, stdout, stderr = await asyncio.to_thread(
            container_session.execute, cmd
        )

        self.logger.info(f"[replace] 命令 exit_code: {exit_code}")

        if exit_code != 0:
            return f"替换失败：{stderr}"

        return stdout.strip()
