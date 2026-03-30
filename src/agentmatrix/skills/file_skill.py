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
- Agent 在容器内有完全权限（无白名单限制）
"""

import os
from typing import Optional
from ..core.action import register_action


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
    _skill_description = """文件操作技能：读取、写入、搜索文件和目录，执行 shell 命令。注意你的工作环境位于容器中，和宿主机环境是隔离的。你和用户以及其他Agent不能直接共享文件，向用户传递文件需要通过附件。当前会话的工作路径是`/work_files`，你的私人长期目录是`/home`"""

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
        if hasattr(self, "root_agent") and self.root_agent:
            return self.root_agent
        return self

    def _ensure_docker_manager(self):
        """确保 docker_manager 可用"""
        root_agent = self._get_root_agent()

        if not hasattr(root_agent, "docker_manager") or not root_agent.docker_manager:
            raise RuntimeError("Docker manager 未初始化，无法执行文件操作")

        return root_agent.docker_manager

    # ==================== Actions ====================

    @register_action(
        short_desc="列目录[directory, recursive=False]",
        description="列出目录内容。支持单层或递归列出",
        param_infos={
            "directory": "目录路径（可选，默认当前目录 /work_files）",
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

        self.logger.info(f"[list_dir] 命令: {cmd}")
        self.logger.info(f"[list_dir] exit_code: {exit_code}")
        self.logger.info(f"[list_dir] stdout:\n{stdout}")
        self.logger.info(f"[list_dir] stderr:\n{stderr}")

        if exit_code != 0:
            # 提供详细的错误信息
            container_status = "unknown"
            try:
                container_status = (
                    docker_manager.container.status
                    if docker_manager.container
                    else "no_container"
                )
            except Exception:
                container_status = "error_getting_status"

            error_msg = f"""列出目录失败
- 命令: {cmd}
- 退出码: {exit_code}
- 容器状态: {container_status}
- 标准输出: {stdout.strip() if stdout else "(空)"}
- 标准错误: {stderr.strip() if stderr else "(空)"}
"""
            return error_msg

        return stdout or "目录为空"

    @register_action(
        short_desc="读文件内容[file_path, start_line=1,end_line=200]",
        description="读取文件内容。支持指定行范围（默认前200行）",
        param_infos={
            "file_path": "文件路径（相对于 /work_files）",
            "start_line": "起始行号（从1开始，默认1）",
            "end_line": "结束行号（默认200）",
        },
    )
    async def read(
        self,
        file_path: str,
        start_line: Optional[int] = 1,
        end_line: Optional[int] = 200,
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

        self.logger.info(f"[read] 命令: {cmd}")
        self.logger.info(f"[read] exit_code: {exit_code}")
        self.logger.info(f"[read] stdout:\n{stdout}")
        self.logger.info(f"[read] stderr:\n{stderr}")

        if exit_code != 0:
            container_status = "unknown"
            try:
                container_status = (
                    docker_manager.container.status
                    if docker_manager.container
                    else "no_container"
                )
            except Exception:
                container_status = "error_getting_status"
            return f"""读取文件失败
- 文件路径: {file_path}
- 容器内路径: {container_path}
- 退出码: {exit_code}
- 容器状态: {container_status}
- 标准错误: {stderr.strip() if stderr else "(空)"}
"""

        # 获取文件总行数
        total_cmd = f"wc -l {container_path}"
        total_exit, total_out, _ = await docker_manager.exec_command(total_cmd)
        total_lines = total_out.strip().split()[0] if total_exit == 0 else "?"

        return f"# 文件: {file_path} (共 {total_lines} 行)\n# 显示第 {start_line}-{end_line} 行\n\n{stdout}"

    @register_action(
        short_desc="写入文件[file_path,content,mode='overwrite',allow_overwrite=False]",
        description="写入文件内容。默认覆盖模式。",
        param_infos={
            "file_path": "文件路径（相对于 /work_files）",
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

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")

        # 使用相对路径（因为 workdir 已经是 /work_files）
        # 去掉 /work_files 前缀，得到相对路径
        if container_path.startswith("/work_files/"):
            relative_path = container_path[len("/work_files/") :]
        elif container_path == "/work_files":
            relative_path = "."
        else:
            relative_path = container_path

        if mode == "append":
            write_cmd = f"echo {encoded_content} | base64 -d | tee -a {relative_path} > /dev/null"
        else:
            write_cmd = (
                f"echo {encoded_content} | base64 -d | tee {relative_path} > /dev/null"
            )

        exit_code, stdout, stderr = await docker_manager.exec_command(write_cmd)

        self.logger.info(f"[write] 命令: {write_cmd}")
        self.logger.info(f"[write] exit_code: {exit_code}")
        self.logger.info(f"[write] stdout:\n{stdout}")
        self.logger.info(f"[write] stderr:\n{stderr}")

        if exit_code != 0:
            container_status = "unknown"
            try:
                container_status = (
                    docker_manager.container.status
                    if docker_manager.container
                    else "no_container"
                )
            except Exception:
                container_status = "error_getting_status"
            return f"""写入文件失败
- 文件路径: {file_path}
- 退出码: {exit_code}
- 容器状态: {container_status}
- 标准错误: {stderr.strip() if stderr else "(空)"}
"""

        mode_desc = "追加到" if mode == "append" else "写入"
        return f"成功{mode_desc} {file_path}\n"

    @register_action(
        short_desc="搜文件(详细用法看help)",
        description="搜索文件或文件里的内容。支持按文件名或文件内容搜索",
        param_infos={
            "pattern": "搜索模式（文件名模式或文本内容）",
            "target": "搜索目标，'content' 表示在文件内容中搜索，'filename' 表示按文件名搜索（默认content）",
            "directory": "搜索目录（可选，默认当前目录 /work_files）",
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

        self.logger.info(f"[search_file] 命令: {cmd}")
        self.logger.info(f"[search_file] exit_code: {exit_code}")
        self.logger.info(f"[search_file] stdout:\n{stdout}")
        self.logger.info(f"[search_file] stderr:\n{stderr}")

        if exit_code != 0 and not stdout:
            return f"未找到匹配结果"

        return stdout or "未找到匹配结果"

    @register_action(
        short_desc="执行base脚本",
        description="""执行 bash 命令或脚本（在容器内执行）""",
        param_infos={
            "command": "bash 命令或脚本（多行脚本用 \\n 分隔）",
            "timeout": "超时时间（秒，默认30）",
        },
    )
    async def bash(self, command: str, timeout: int = 30) -> str:
        """
        执行 bash 命令或脚本（容器内执行）

        Args:
            command: bash 命令或脚本
            timeout: 超时时间（秒，默认30）

        Returns:
            执行结果
        """
        docker_manager = self._ensure_docker_manager()

        # 直接在容器内执行命令（无白名单限制）
        # 注意：Agent 在自己的容器里有完全权限，可以执行任意命令
        exit_code, stdout, stderr = await docker_manager.exec_command(command)

        self.logger.info(f"[bash] 命令: {command}")
        self.logger.info(f"[bash] exit_code: {exit_code}")
        self.logger.info(f"[bash] stdout:\n{stdout}")
        self.logger.info(f"[bash] stderr:\n{stderr}")

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
            "file_path": "文件路径（相对于 /work_files）",
            "old_pattern": "要替换的旧字符串",
            "new_string": "新字符串",
            "use_regex": "是否使用正则表达式（默认false）",
        },
    )
    async def replace_string_in_file(
        self, file_path: str, old_pattern: str, new_string: str, use_regex: bool = False
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
            sed_pattern = old_pattern.replace("/", "\\/")
            sed_replacement = new_string.replace("/", "\\/")
            cmd = f"sed -i 's/{sed_pattern}/{sed_replacement}/g' {container_path}"

        exit_code, stdout, stderr = await docker_manager.exec_command(cmd)

        self.logger.info(f"[replace_string_in_file] 命令: {cmd}")
        self.logger.info(f"[replace_string_in_file] exit_code: {exit_code}")
        self.logger.info(f"[replace_string_in_file] stdout:\n{stdout}")
        self.logger.info(f"[replace_string_in_file] stderr:\n{stderr}")

        if exit_code != 0:
            return f"❌ 替换失败：{stderr}"

        return f"字符串已替换"
