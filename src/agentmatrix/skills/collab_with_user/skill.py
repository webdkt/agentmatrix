"""Collab with User Skill - 用户交互技能"""

import asyncio
import os
import platform
import signal
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from ...core.action import register_action


class Collab_with_userSkillMixin:
    """Collab with User Skill Mixin - 提供用户交互能力"""

    _skill_description = """用户协作技能。可以预览文件、向用户提问等。"""

    # 可执行文件黑名单
    _EXECUTABLE_BLACKLIST = {
        '.py', '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd',
        '.exe', '.com', '.jar', '.app'
    }

    def _preview_ctx(self):
        """获取当前 Agent 的 preview 上下文"""
        if "preview" not in self.skill_context:
            self.skill_context["preview"] = {
                "current_pid": None,
                "current_tmp_path": None,
                "current_host_path": None,
            }
        return self.skill_context["preview"]
 
    @register_action(
        short_desc="[question=问题， options*=单选选项， multiple*=多选选项, image_path*=要显示的图片] 暂停工作向用户提问（支持文本/单选/多选，都可选带图片, 单多选时用户也可以自定义文本来回答）",
        description="向用户提问并等待回答。当你需要用户提供信息时调用此 action。",
        param_infos={"question": "要向用户提出的问题（清晰、具体）"},
    )
    async def ask_user(self, question: str) -> str:
        """
        💬 向用户提问并等待回答（特殊 action）

        这是一个特殊的 action，会挂起当前 MicroAgent 的执行，等待用户通过 Server API 提供答案。

        注意：此方法会被 MicroAgent._execute_action 特殊处理，实际调用 root_agent.ask_user()。

        Args:
            question: 向用户提出的问题

        Returns:
            str: 用户的回答

        Raises:
            RuntimeError: 如果没有 root_agent（不应该发生）
        """
        # 这个方法不应该被直接调用
        # _execute_action 会检测到 action_name="ask_user" 并调用 root_agent.ask_user()
        # 这里只是为了注册 action，提供一个占位实现
        raise RuntimeError(
            "ask_user should be handled by MicroAgent._execute_action, check root_agent"
        )

    @register_action(
        short_desc="[file_path]打开文件让用户预览，每次打开预览后都MUST用ask_user询问是否看到预览，是否正常，是否有反馈等，也起到一个提醒用户预览打开了的作用。",
        description="在宿主机用默认应用打开文件进行预览。每次只能预览一个文件，新预览会关闭旧预览。不支持可执行脚本文件。",
        param_infos={
            "file_path": "要预览的文件路径（容器内路径）"
        },
    )
    async def open_file_for_user_preview(self, file_path: str) -> str:
        """
        在宿主机预览容器内文件

        Args:
            file_path: 容器内文件路径

        Returns:
            str: 预览结果信息
        """
        container_session = self.root_agent.container_session
        task_id = self.current_task_id or "default"
        ctx = self._preview_ctx()

        # 1. 安全检查：黑名单
        file_ext = Path(file_path).suffix.lower()
        if file_ext in self._EXECUTABLE_BLACKLIST:
            supported = ", ".join(sorted(self._EXECUTABLE_BLACKLIST))
            return f"预览失败：不支持可执行脚本文件\n  扩展名: {file_ext}\n  提示：可用 read_txt_file 查看内容"

        # 2. 在容器内获取绝对路径（realpath 会自动展开 ~ 和解析软链接）
        realpath_cmd = f'realpath "{file_path}"'
        exit_code, abs_path, stderr = await asyncio.to_thread(
            container_session.execute, realpath_cmd
        )

        if exit_code != 0:
            return f"预览失败：文件不存在或路径无效\n  路径: {file_path}\n  错误: {stderr.strip() if stderr else '(realpath 失败)'}"

        abs_path = abs_path.strip()
        self.logger.info(f"[open_file_for_user_preview] 容器内绝对路径: {abs_path}")

        # 3. 判断路径类型并复制
        if self._is_mappable_path(abs_path):
            # 情况A：可映射路径 → 直接在宿主机 copy
            self.logger.info(f"[open_file_for_user_preview] 可映射路径，从宿主机 copy")
            host_path = self._resolve_container_abs_path_to_host(abs_path)
            if not host_path:
                return f"预览失败：无法解析宿主机路径\n  容器路径: {abs_path}"

            if not Path(host_path).exists():
                return f"预览失败：宿主机文件不存在\n  容器路径: {abs_path}\n  宿主机路径: {host_path}"

            tmp_path = await self._copy_file_to_temp(host_path)
        else:
            # 情况B：不可映射路径 → 从容器 copy
            self.logger.info(f"[open_file_for_user_preview] 不可映射路径，从容器 copy")
            tmp_path = await self._copy_file_from_container(abs_path)

        if not tmp_path:
            return f"预览失败：无法复制文件到临时目录\n  路径: {file_path}"

        # 4. 关闭旧预览并打开新预览
        self._close_and_open_preview(tmp_path)

        filename = Path(file_path).name
        return f"已打开预览: {filename}\n  临时路径: {tmp_path}"

    def _is_mappable_path(self, container_abs_path: str) -> bool:
        """
        判断容器内绝对路径是否能映射到宿主机

        可映射路径：/data/agents/{agent_name}/... （volume mount 映射）
        不可映射路径：/tmp、/var/tmp 等容器内其他路径

        Args:
            container_abs_path: 容器内绝对路径

        Returns:
            bool: 是否可映射
        """
        runtime = self.root_agent.runtime
        if not runtime:
            return False

        agent_name = self.root_agent.name
        # 可映射路径的前缀
        mappable_prefix = f"/data/agents/{agent_name}/"

        return container_abs_path.startswith(mappable_prefix)

    def _resolve_container_abs_path_to_host(self, container_abs_path: str) -> str:
        """
        将容器内绝对路径转换为宿主机路径

        前提：路径必须是可映射的（在 /data/agents/{agent_name}/ 下）
        映射关系：/data/agents/{agent_name}/... → workspace/agent_files/{agent_name}/...

        Args:
            container_abs_path: 容器内绝对路径

        Returns:
            str: 宿主机路径，如果不可映射则返回 None
        """
        if not self._is_mappable_path(container_abs_path):
            return None

        runtime = self.root_agent.runtime
        agent_name = self.root_agent.name

        # 提取 /data/agents/{agent_name}/ 后面的部分
        prefix = f"/data/agents/{agent_name}/"
        relative_path = container_abs_path[len(prefix):]

        # 构造宿主机路径
        return str(runtime.paths.workspace_dir / "agent_files" / agent_name / relative_path)

    def _resolve_container_path_to_host(self, container_path: str, task_id: str) -> str:
        """
        将容器内路径转换为宿主机路径

        容器内 → 宿主机的映射（基于 docs/core/10-容器与文件系统.md）：
        - ~/ → /home/{agent_name} → workspace/agent_files/{agent_name}/home/
        - ~/current_task → work_files/{task_id}/ → workspace/agent_files/{agent_name}/work_files/{task_id}/
        - /data/agents/{agent_name}/... → workspace/agent_files/{agent_name}/...
        """
        runtime = self.root_agent.runtime
        if not runtime:
            return None

        agent_name = self.root_agent.name

        # 情况 1: ~/current_task/... （软链接）
        if container_path.startswith("~/current_task"):
            rel_path = container_path[len("~/current_task/"):].lstrip("/")
            return str(
                runtime.paths.get_agent_work_files_dir(agent_name, task_id) / rel_path
            )

        # 情况 2: ~/... （主目录）
        if container_path.startswith("~/"):
            rel_path = container_path[2:].lstrip("/")  # 移除 "~"
            return str(
                runtime.paths.get_agent_home_dir(agent_name) / rel_path
            )

        # 情况 3: /data/agents/{agent_name}/...
        if container_path.startswith("/data/agents/"):
            # 提取 {agent_name}/...
            parts = container_path.split("/", 3)  # ["", "data", "agents", "{agent_name}", ...]
            if len(parts) > 3:
                relative = "/".join(parts[3:])  # {agent_name}/...
                return str(runtime.paths.workspace_dir / "agent_files" / relative)

        # 情况 4: 相对路径
        if not Path(container_path).is_absolute():
            return str(
                runtime.paths.get_agent_work_files_dir(agent_name, task_id)
                / container_path
            )

        # 情况 5: 其他绝对路径（容器内其他路径，无法映射）
        return None

    async def _copy_file_from_container(self, container_path: str) -> str:
        """
        从容器内复制文件到宿主机临时目录

        用于不可映射路径（如 /tmp、/var/tmp 等）。
        使用 base64 编码支持二进制文件。

        Args:
            container_path: 容器内绝对路径

        Returns:
            str: 临时文件路径，失败返回 None
        """
        try:
            container_session = self.root_agent.container_session

            # 使用 base64 编码读取文件（支持二进制）
            cmd = f'base64 "{container_path}"'
            exit_code, base64_content, stderr = await asyncio.to_thread(
                container_session.execute, cmd
            )

            if exit_code != 0:
                self.logger.error(f"Failed to read file from container: {stderr}")
                return None

            # 创建临时目录和文件
            temp_dir = tempfile.gettempdir()
            preview_dir = os.path.join(temp_dir, "agentmatrix_previews")
            os.makedirs(preview_dir, exist_ok=True)

            # 生成临时文件名
            agent_name = self.root_agent.name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            basename = Path(container_path).name
            tmp_filename = f"{agent_name}_{timestamp}_{basename}"
            tmp_path = os.path.join(preview_dir, tmp_filename)

            # 解码 base64 并写入文件
            file_content = base64.b64decode(base64_content.strip())
            with open(tmp_path, "wb") as f:
                f.write(file_content)

            self.logger.info(f"Copied file from container: {container_path} -> {tmp_path}")
            return tmp_path

        except Exception as e:
            self.logger.error(f"Failed to copy file from container: {e}")
            return None

    async def _copy_file_to_temp(self, host_path: str) -> str:
        """复制文件到临时目录"""
        try:
            # 创建临时目录
            temp_dir = tempfile.gettempdir()
            preview_dir = os.path.join(temp_dir, "agentmatrix_previews")
            os.makedirs(preview_dir, exist_ok=True)

            # 生成临时文件名（包含 Agent 名字和时间戳）
            agent_name = self.root_agent.name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            basename = Path(host_path).name
            tmp_filename = f"{agent_name}_{timestamp}_{basename}"
            tmp_path = os.path.join(preview_dir, tmp_filename)

            # 复制文件
            shutil.copy2(host_path, tmp_path)
            self.logger.info(f"Copied file to temp: {host_path} -> {tmp_path}")
            return tmp_path

        except Exception as e:
            self.logger.error(f"Failed to copy file to temp: {e}")
            return None

    def _close_and_open_preview(self, tmp_path: str):
        """关闭旧预览并打开新预览"""
        ctx = self._preview_ctx()

        # 关闭旧预览
        old_pid = ctx.get("current_pid")
        old_tmp_path = ctx.get("current_tmp_path")
        if old_pid:
            self._close_preview_process(old_pid)
        if old_tmp_path and os.path.exists(old_tmp_path):
            self._cleanup_temp_file(old_tmp_path)

        # 打开新文件
        pid = self._open_file_with_default_app(tmp_path)

        # 更新状态
        ctx["current_pid"] = pid
        ctx["current_tmp_path"] = tmp_path
        ctx["current_host_path"] = tmp_path

        # 同步到 root_agent 的 current_preview_file
        self.root_agent.current_preview_file = tmp_path

    def _open_file_with_default_app(self, file_path: str) -> int:
        """用默认应用打开文件（跨平台）"""
        try:
            system = platform.system()
            if system == "Darwin":  # macOS
                process = subprocess.Popen(["open", file_path])
            elif system == "Linux":
                process = subprocess.Popen(["xdg-open", file_path])
            elif system == "Windows":
                subprocess.Popen(["start", "", file_path], shell=True)
                # Windows 的 start 命令无法获取 PID，返回 None
                return None
            else:
                self.logger.warning(f"Unsupported platform: {system}")
                return None

            self.logger.info(f"Opened file: {file_path} (PID: {process.pid})")
            return process.pid

        except Exception as e:
            self.logger.error(f"Failed to open file: {e}")
            return None

    def _close_preview_process(self, pid: int):
        """关闭预览进程（跨平台）"""
        try:
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["pkill", "-P", str(pid)], check=False)
            elif system == "Linux":
                subprocess.run(["pkill", "-P", str(pid)], check=False)
            elif system == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False)
            else:
                self.logger.warning(f"Unsupported platform for closing: {system}")

            self.logger.info(f"Closed preview process (PID: {pid})")

        except Exception as e:
            self.logger.error(f"Failed to close process (PID: {pid}): {e}")

    def _cleanup_temp_file(self, file_path: str):
        """清理临时文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"Cleaned temp file: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to cleanup temp file {file_path}: {e}")

    async def skill_cleanup(self):
        """清理资源"""
        ctx = self._preview_ctx()
        if ctx["current_pid"]:
            self._close_preview_process(ctx["current_pid"])
            ctx["current_pid"] = None
        if ctx["current_tmp_path"]:
            self._cleanup_temp_file(ctx["current_tmp_path"])
            ctx["current_tmp_path"] = None
        # 清除 root_agent 的 preview 状态
        self.root_agent.current_preview_file = None
