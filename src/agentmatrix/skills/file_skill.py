"""
File Operation Skill - Docker 容器内执行版本

重构说明：
- 所有文件操作在 Docker 容器内执行
- 移除 working_context 依赖
- 使用 docker_manager.exec_command() 执行命令
- 移除路径溢出检查（容器内已隔离）
- 返回结果保持不变

核心设计：
- 容器内工作目录：/work_files
- 所有命令通过容器执行
- bash 安全白名单保留
"""

import os
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
        "df", "du",
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
        # 删除文件
        "rm",
        # 复制/移动
        "cp", "mv",
        # 压缩
        "tar", "gzip", "gunzip",
        # 查找文件
        "find",
        # 链接
        "ln",
    },

    # ===== 等级 3: 需要谨慎使用（开发工具）=====
    "caution": {
        # 开发工具
        "python3", "python",
        # 版本控制
        "git",
        # 网络工具
        "curl", "wget",
    },
}


class FileSkillMixin:
    """
    File Operation Skill Mixin (Docker 容器版本)

    所有文件操作在 Docker 容器内执行：
    - list_dir: 列出目录内容
    - read: 读取文件
    - write: 写入文件
    - search: 搜索文件或内容
    - bash: 执行 shell 命令

    特点：
    - 容器内执行，路径隔离
    - 工作目录：/work_files
    - bash 安全白名单保留
    """

    # 🆕 Skill 级别元数据
    _skill_description = "文件操作技能：读取、写入、搜索文件和目录，执行 shell 命令。默认当前路径是`/work_files`，你的私人长期目录是`/home`"

    _skill_usage_guide = """
使用场景：
- 需要读取或写入文件
- 需要列出目录内容
- 需要在文件中搜索内容
- 需要执行 shell 命令或脚本

使用建议：
- 使用 list_dir 查看目录结构（支持递归）
- 使用 read 读取文件（支持行范围，默认前200行）
- 使用 write 写入文件（默认覆盖模式，支持追加）
- 使用 search_file 搜索文件或内容（支持文件名和内容搜索）
- 使用 bash 执行 shell 命令（有安全白名单）

注意事项：
- 所有路径相对于 /work_files
- write 默认覆盖，需设置 allow_overwrite=True
- bash 命令受安全白名单限制
"""

    def _get_root_agent(self):
        """获取 root_agent"""
        if hasattr(self, 'root_agent') and self.root_agent:
            return self.root_agent
        return self

    def _ensure_docker_manager(self):
        """确保 docker_manager 可用"""
        root_agent = self._get_root_agent()
        
        if not hasattr(root_agent, 'docker_manager') or not root_agent.docker_manager:
            raise RuntimeError("Docker manager 未初始化，无法执行文件操作")
        
        return root_agent.docker_manager

    # ==================== Actions ====================

    @register_action(
        description="列出目录内容。支持单层或递归列出",
        param_infos={
            "directory": "目录路径（可选，默认当前目录 /work_files）",
            "recursive": "是否递归列出子目录（默认False）"
        }
    )
    async def list_dir(
        self,
        directory: Optional[str] = None,
        recursive: bool = False
    ) -> str:
        """
        列出目录内容（容器内执行）

        Args:
            directory: 目录路径（默认当前目录）
            recursive: 是否递归列出子目录
        """
        docker_manager = self._ensure_docker_manager()

        # 默认工作目录（使用相对路径）
        work_dir = directory or "."

        # 构建命令
        if recursive:
            cmd = f"ls -lhR {work_dir}"
        else:
            cmd = f"ls -lho {work_dir}"

        # 在容器内执行
        exit_code, stdout, stderr = await docker_manager.exec_command(cmd)
        
        if exit_code != 0:
            return f"错误：列出目录失败\n{stderr}"
        
        return stdout or "目录为空"

    @register_action(
        description="读取文件内容。支持指定行范围（默认前200行）",
        param_infos={
            "file_path": "文件路径（相对于 /work_files）",
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
        读取文件内容（容器内执行）

        Args:
            file_path: 文件路径
            start_line: 起始行号（从 1 开始，默认 1）
            end_line: 结束行号（默认 200）
        """
        docker_manager = self._ensure_docker_manager()
        
        # 容器内路径
        if not os.path.isabs(file_path):
            container_path = f"/work_files/{file_path}"
        else:
            container_path = file_path
        
        # 使用 sed 读取指定行
        cmd = f"sed -n '{start_line},{end_line}p' {container_path}"
        
        exit_code, stdout, stderr = await docker_manager.exec_command(cmd)
        
        if exit_code != 0:
            return f"错误：读取文件失败: {stderr}"
        
        # 获取文件总行数
        total_cmd = f"wc -l {container_path}"
        total_exit, total_out, _ = await docker_manager.exec_command(total_cmd)
        total_lines = total_out.strip().split()[0] if total_exit == 0 else "?"
        
        return f"# 文件: {file_path} (共 {total_lines} 行)\n# 显示第 {start_line}-{end_line} 行\n\n{stdout}"

    @register_action(
        description="写入文件内容。默认覆盖模式。",
        param_infos={
            "file_path": "文件路径（相对于 /work_files）",
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
        写入文件内容（容器内执行）

        Args:
            file_path: 文件路径
            content: 文件内容
            mode: 写入模式，'overwrite' 覆盖或 'append' 追加（默认 overwrite）
            allow_overwrite: 是否允许覆盖已存在文件（默认 False）
        """
        docker_manager = self._ensure_docker_manager()

        # 容器内路径
        if not os.path.isabs(file_path):
            container_path = f"/work_files/{file_path}"
        else:
            container_path = file_path

        # 检查文件是否存在
        check_cmd = f"test -f {container_path} && echo 'exists' || echo 'not_exists'"
        exit_code, stdout, _ = await docker_manager.exec_command(check_cmd)
        file_exists = stdout.strip() == "exists"

        if file_exists and mode == "overwrite" and not allow_overwrite:
            return f"错误：文件已存在，如果要覆盖请设置 allow_overwrite=True\n  文件: {file_path}"

        # 创建目录
        dir_cmd = f"mkdir -p $(dirname {container_path})"
        await docker_manager.exec_command(dir_cmd)

        # 写入文件
        # 使用 base64 编码传递内容（避免转义问题）
        import base64
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')

        # 使用相对路径（因为 workdir 已经是 /work_files）
        # 去掉 /work_files 前缀，得到相对路径
        if container_path.startswith("/work_files/"):
            relative_path = container_path[len("/work_files/"):]
        elif container_path == "/work_files":
            relative_path = "."
        else:
            relative_path = container_path

        if mode == "append":
            write_cmd = f'echo {encoded_content} | base64 -d | tee -a {relative_path} > /dev/null'
        else:
            write_cmd = f'echo {encoded_content} | base64 -d | tee {relative_path} > /dev/null'

        exit_code, stdout, stderr = await docker_manager.exec_command(write_cmd)
        
        if exit_code != 0:
            return f"错误：写入文件失败\n{stderr}"
        
        mode_desc = '追加到' if mode == 'append' else '写入'
        return f"成功{mode_desc} {file_path}\n"

    @register_action(
        description="搜索文件或文件里的内容。支持按文件名或文件内容搜索",
        param_infos={
            "pattern": "搜索模式（文件名模式或文本内容）",
            "target": "搜索目标，'content' 表示在文件内容中搜索，'filename' 表示按文件名搜索（默认content）",
            "directory": "搜索目录（可选，默认当前目录 /work_files）",
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
        搜索文件或内容（容器内执行）

        Args:
            pattern: 搜索模式
            target: 搜索目标，"content" 表示在文件内容中搜索，"filename" 表示按文件名搜索
            directory: 搜索目录（默认当前目录）
            recursive: 是否递归搜索
        """
        docker_manager = self._ensure_docker_manager()

        # 默认工作目录（使用相对路径，避免符号链接问题）
        work_dir = directory or "."

        if target == "filename":
            # 按文件名搜索
            cmd = f"find {work_dir}"
            if not recursive:
                cmd += " -maxdepth 1"
            cmd += f" -name '*{pattern}*'"
        else:
            # 在文件内容中搜索
            if recursive:
                cmd = f"grep -rn '{pattern}' {work_dir}"
            else:
                cmd = f"grep -n '{pattern}' {work_dir}/*"

        exit_code, stdout, stderr = await docker_manager.exec_command(cmd)

        if exit_code != 0 and not stdout:
            return f"未找到匹配结果"

        return stdout or "未找到匹配结果"

    @register_action(
        description="""执行 bash 命令或脚本（在容器内执行）""",
        param_infos={
            "command": "bash 命令或脚本（多行脚本用 \\n 分隔）",
            "timeout": "超时时间（秒，默认30）"
        }
    )
    async def bash(self, command: str, timeout: int = 30) -> str:
        """
        执行 bash 命令或脚本（容器内执行，安全模式）

        Args:
            command: bash 命令或脚本
            timeout: 超时时间（秒，默认30）

        Returns:
            执行结果
        """
        docker_manager = self._ensure_docker_manager()
        
        # 1. 预处理：移除注释
        cleaned_command = self._remove_bash_comments(command)
        
        # 2. 语法检查（可选）
        # 跳过语法检查，因为命令将在容器内执行
        
        # 3. 命令白名单验证
        is_allowed, allow_error = await self._validate_bash_command(cleaned_command)
        if not is_allowed:
            return f"❌ 命令验证失败：\n{allow_error}"
        
        # 4. 在容器内执行命令
        exit_code, stdout, stderr = await docker_manager.exec_command(cleaned_command)
        
        result = ""
        if stdout:
            result += stdout
        if stderr:
            result += f"\n[错误输出]\n{stderr}"
        
        if not result:
            return "Done（无输出）"
        
        return result

    @register_action(
        description="字符串替换：在文件中查找并替换字符串。",
        param_infos={
            "file_path": "文件路径（相对于 /work_files）",
            "old_pattern": "要替换的旧字符串",
            "new_string": "新字符串",
            "use_regex": "是否使用正则表达式（默认false）"
        }
    )
    async def replace_string_in_file(
        self,
        file_path: str,
        old_pattern: str,
        new_string: str,
        use_regex: bool = False
    ) -> str:
        """
        在文件中查找并替换字符串（容器内执行）

        Args:
            file_path: 文件路径
            old_pattern: 要替换的旧字符串
            new_string: 新字符串
            use_regex: 是否使用正则表达式（默认false）
        """
        docker_manager = self._ensure_docker_manager()
        
        # 容器内路径
        if not os.path.isabs(file_path):
            container_path = f"/work_files/{file_path}"
        else:
            container_path = file_path
        
        # 使用 sed 进行替换
        if use_regex:
            # sed 正则表达式替换
            # 转义特殊字符
            sed_pattern = old_pattern
            cmd = f"sed -i 's/{sed_pattern}/{new_string}/g' {container_path}"
        else:
            # sed 字面字符串替换（需要转义）
            sed_pattern = old_pattern.replace('/', '\\/')
            sed_replacement = new_string.replace('/', '\\/')
            cmd = f"sed -i 's/{sed_pattern}/{sed_replacement}/g' {container_path}"
        
        exit_code, stdout, stderr = await docker_manager.exec_command(cmd)
        
        if exit_code != 0:
            return f"❌ 替换失败：{stderr}"
        
        return f"字符串已替换"

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

    async def _validate_bash_command(self, command: str) -> tuple[bool, str]:
        """
        验证 bash 命令是否在白名单中

        Returns:
            (is_allowed, error_message)
        """
        # 获取白名单
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
