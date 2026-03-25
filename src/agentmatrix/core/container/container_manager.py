"""
Container Manager - 容器管理器（使用新的抽象层）

基于容器运行时抽象层实现统一的容器管理功能。
这是新的容器管理器实现，支持 Docker 和 Podman。
"""

from pathlib import Path
from typing import Tuple, Dict, Optional
import hashlib
import logging
from datetime import datetime

from .runtime_factory import ContainerRuntimeFactory
from .runtime_adapter import ContainerAdapter, ContainerHandle
from .compat import ContainerCompat



def sanitize_container_name(agent_name: str) -> str:
    """
    标准化容器名称，确保符合容器命名规范

    Docker/Podman 容器名称要求：[a-zA-Z0-9][a-zA-Z0-9_.-]*

    使用 SHA256 哈希确保：
    1. 符合命名规范
    2. 唯一性（不同 agent 名称产生不同哈希）
    3. 确定性（相同名称总是产生相同哈希）

    Args:
        agent_name: Agent 原始名称（可能包含中文）

    Returns:
        str: 符合规范的容器名称（格式：agent_xxxxxxxxxxxx）
    """
    # SHA256 哈希，取前 8 位
    hash_obj = hashlib.sha256(agent_name.encode('utf-8'))
    short_hash = hash_obj.hexdigest()[:8]
    return f"agent_{short_hash}"


class ContainerManager:
    """
    容器管理器（支持 Docker 和 Podman）

    职责：
    - 容器生命周期管理（创建、唤醒、休眠、停止）
    - 符号链接动态切换（switch_workspace）
    - 容器内命令执行接口（exec_command）
    - 目录初始化（initialize_directories）

    与旧的 DockerContainerManager 的区别：
    - 使用容器运行时抽象层，支持多种运行时
    - 运行时自动检测（Podman 优先）
    - 配置驱动的运行时选择
    """

    def __init__(
        self,
        agent_name: str,
        workspace_root: Path,
        image_name: str = "agentmatrix:latest",
        runtime_type: str = None,
        parent_logger: Optional[logging.Logger] = None
    ):
        """
        初始化容器管理器

        Args:
            agent_name: Agent 名称
            workspace_root: 工作区根目录
            image_name: 镜像名称
            runtime_type: 运行时类型 ('docker', 'podman', 'auto')
                         如果为 None，自动检测
            parent_logger: 父级 logger（可选）

        Raises:
            RuntimeError: 容器运行时不可用
        """
        self.agent_name = agent_name
        self.workspace_root = workspace_root
        self.image_name = image_name

        # 设置 logger
        if parent_logger:
            self.logger = parent_logger.getChild(f"container_{agent_name}")
        else:
            self.logger = logging.getLogger(f"container.{agent_name}")

        # 初始化容器运行时适配器
        self.adapter: ContainerAdapter = ContainerRuntimeFactory.create(
            runtime_type=runtime_type,
            logger=self.logger
        )

        # 检测运行时类型
        self.runtime_type = ContainerCompat.detect_runtime_type(self.adapter)
        self.logger.info(f"✅ 使用容器运行时: {self.runtime_type}")

        # 目录路径
        self.skills_dir = self.workspace_root / "SKILLS"
        self.agent_files_dir = self.workspace_root / "agent_files" / agent_name
        self.agent_home = self.agent_files_dir / "home"
        self.work_files_base = self.agent_files_dir / "work_files"

        # 容器名称（标准化）
        self.container_name = sanitize_container_name(agent_name)

        # 容器句柄（延迟创建）
        self.container: Optional[ContainerHandle] = None

    def initialize_directories(self) -> None:
        """
        初始化目录结构

        创建宿主机上的目录结构：
        - agent_files/{agent_name}/home/
        - agent_files/{agent_name}/work_files/

        Raises:
            OSError: 目录创建失败
        """
        try:
            # 创建 agent_home
            self.agent_home.mkdir(parents=True, exist_ok=True)

            # 创建 work_files_base（父目录，包含所有 session）
            self.work_files_base.mkdir(parents=True, exist_ok=True)

            # 创建知识目录（可选）
            knowledge_dir = self.agent_home / "knowledge"
            knowledge_dir.mkdir(exist_ok=True)

            self.logger.info(f"✅ 目录结构初始化完成: {self.agent_files_dir}")

        except OSError as e:
            raise RuntimeError(f"目录创建失败: {e}") from e

    def _create_container(self) -> None:
        """
        创建容器

        挂载策略：
        - /SKILLS -> workspace_root/SKILLS (ro)
        - /home -> agent_files/{agent_name}/home (rw)
        - /work_files_base -> agent_files/{agent_name}/work_files (rw)

        Raises:
            RuntimeError: 容器创建失败
        """
        try:
            # 准备挂载配置
            volumes = {
                str(self.skills_dir): {'bind': '/SKILLS', 'mode': 'ro'},
                str(self.agent_home): {'bind': '/home', 'mode': 'rw'},
                str(self.work_files_base): {'bind': '/work_files_base', 'mode': 'rw'},
            }

            # 创建容器
            self.container = self.adapter.create_container(
                name=self.container_name,
                image=self.image_name,
                volumes=volumes,
                detach=True,
                tty=True,  # 保持容器运行
                auto_remove=False,  # 不自动删除，便于调试
            )

            self.logger.info(
                f"✅ 容器创建成功: {self.container_name} "
                f"({self.container.short_id})"
            )

        except Exception as e:
            raise RuntimeError(f"容器创建失败: {e}") from e

    def _create_default_work_files_link(self) -> None:
        """
        创建默认的 /work_files 符号链接

        容器创建后，创建一个默认的 session（"default"），
        并让 /work_files 指向它，确保 WORKDIR 存在。
        """
        try:
            # 1. 在宿主机创建默认 session 目录
            default_session_dir = self.work_files_base / "default"
            default_session_dir.mkdir(parents=True, exist_ok=True)

            # 2. 启动容器（如果未运行）
            if self.container.status.lower() != "running":
                self.container.start()

            # 3. 在容器内创建符号链接
            cmd = "ln -s /work_files_base/default /work_files"
            exit_code, output = self.container.exec_run(cmd, workdir="/")

            if exit_code != 0:
                error_msg = output.decode('utf-8', errors='ignore').strip()
                raise RuntimeError(f"创建默认符号链接失败: {error_msg}")

            self.logger.info(
                "✅ 默认工作区符号链接已创建: "
                "/work_files -> /work_files_base/default"
            )

        except Exception as e:
            raise RuntimeError(f"创建默认工作区失败: {e}") from e

    def _ensure_container(self) -> None:
        """
        确保容器存在（如果不存在则创建）

        Raises:
            RuntimeError: 容器操作失败
        """
        if self.container is None:
            # 尝试查找已存在的容器
            existing = self.adapter.get_container(self.container_name)

            if existing:
                self.container = existing
                self.logger.info(f"📦 找到已存在的容器: {self.container_name}")
            else:
                # 容器不存在，创建新的
                self._create_container()
                # 创建完成后，确保容器已启动
                if self.container.status.lower() in ("created", "exited"):
                    self.container.start()
                # 创建默认的符号链接
                self._create_default_work_files_link()

    def wakeup(self) -> bool:
        """
        唤醒容器（unpause 或 start）

        如果容器未运行，则启动容器；
        如果容器已暂停，则恢复容器。

        Returns:
            bool: 成功返回 True

        Raises:
            RuntimeError: 唤醒失败
        """
        try:
            self._ensure_container()

            # 刷新容器状态（确保获取最新状态）
            self.container.reload()

            # 检查容器状态
            status = self.container.status.lower()

            if status == "paused":
                # 恢复暂停的容器
                self.container.unpause()
                self.logger.info(f"▶️ 容器已恢复: {self.container_name}")

            elif status in ("created", "exited"):
                # 启动已停止的容器
                self.container.start()
                self.logger.info(f"▶️ 容器已启动: {self.container_name}")

            elif status == "running":
                # 容器已在运行
                self.logger.debug(f"✅ 容器已在运行: {self.container_name}")

            else:
                raise RuntimeError(f"未知的容器状态: {status}")

            return True

        except Exception as e:
            raise RuntimeError(f"容器唤醒失败: {e}") from e

    def hibernate(self) -> bool:
        """
        休眠容器（pause）

        暂停容器以节省资源，但保持容器状态。

        Returns:
            bool: 成功返回 True

        Raises:
            RuntimeError: 休眠失败
        """
        try:
            self._ensure_container()

            # 只有运行中的容器才能暂停
            if self.container.status.lower() == "running":
                self.container.pause()
                self.logger.info(f"⏸️ 容器已休眠: {self.container_name}")
            else:
                self.logger.debug(
                    f"容器未运行，无需休眠: {self.container_name} "
                    f"(status: {self.container.status})"
                )

            return True

        except Exception as e:
            raise RuntimeError(f"容器休眠失败: {e}") from e

    def switch_workspace(self, task_id: str) -> bool:
        """
        切换工作区符号链接

        在容器内重新创建 /work_files 符号链接，指向：
        /work_files_base/{task_id}/

        Args:
            task_id: 用户会话 ID

        Returns:
            bool: 成功返回 True

        Raises:
            RuntimeError: 切换失败
        """
        try:
            self._ensure_container()

            # 1. 确保容器已运行
            if self.container.status.lower() != "running":
                self.wakeup()

            # 2. 确保 session 目录存在（宿主机）
            session_dir = self.work_files_base / task_id
            session_dir.mkdir(parents=True, exist_ok=True)

            # 3. 容器内删除旧链接
            rm_cmd = "rm -rf /work_files"
            exit_code, _ = self.container.exec_run(rm_cmd, workdir="/")
            if exit_code != 0:
                self.logger.warning(f"删除旧链接失败（可能不存在）: {rm_cmd}")

            # 4. 容器内创建新符号链接
            ln_cmd = f"ln -s /work_files_base/{task_id} /work_files"
            exit_code, output = self.container.exec_run(ln_cmd, workdir="/")

            if exit_code != 0:
                error_msg = output.decode('utf-8', errors='ignore').strip()
                raise RuntimeError(f"符号链接创建失败: {error_msg}")

            self.logger.info(
                f"🔄 工作区已切换: /work_files -> /work_files_base/{task_id}"
            )

            return True

        except Exception as e:
            raise RuntimeError(f"工作区切换失败: {e}") from e

    async def exec_command(
        self,
        command: str,
        timeout: int = 30
    ) -> Tuple[int, str, str]:
        """
        在容器内执行命令（async 版本）

        所有命令在 /work_files 目录下执行（内部使用 cd 处理符号链接）

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒，默认30秒）

        Returns:
            Tuple[int, str, str]: (退出码, stdout, stderr)

        Raises:
            RuntimeError: 命令执行失败或超时
        """
        try:
            self._ensure_container()

            # 确保容器已运行
            if self.container.status.lower() != "running":
                self.wakeup()

            # 执行命令（在线程池中执行，避免阻塞事件循环）
            import asyncio
            loop = asyncio.get_event_loop()

            # 在命令内部 cd，避免符号链接问题
            full_command = f"cd /work_files && {command}"

            # 🔧 添加超时机制
            try:
                exit_code, output = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self.container.exec_run(
                            ["sh", "-c", full_command],  # 列表形式
                            demux=True
                        )
                    ),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                self.logger.error(
                    f"⏱️ 命令执行超时（{timeout}秒）: {command[:100]}"
                )
                raise RuntimeError(f"命令执行超时（{timeout}秒）: {command[:100]}")

            # 解码输出
            if isinstance(output, tuple):
                # demux=True 时返回 (stdout, stderr)
                stdout_data, stderr_data = output
                stdout = stdout_data.decode('utf-8', errors='ignore') if stdout_data else ""
                stderr = stderr_data.decode('utf-8', errors='ignore') if stderr_data else ""
            else:
                # demux=False 或其他情况
                stdout = output.decode('utf-8', errors='ignore') if output else ""
                stderr = ""

            return exit_code, stdout, stderr

        except Exception as e:
            raise RuntimeError(f"命令执行失败: {e}") from e

    def get_status(self) -> Dict:
        """
        获取容器状态

        Returns:
            Dict: 包含容器状态信息的字典
            - name: 容器名称
            - id: 容器 ID
            - status: 容器状态
            - image: 镜像名称
            - runtime: 运行时类型
        """
        try:
            self._ensure_container()

            self.container.reload()  # 刷新状态

            return {
                "name": self.container_name,
                "id": self.container.short_id,
                "status": self.container.status,
                "image": self.image_name,
                "runtime": self.runtime_type,
                "created": self.container.get_attribute('Created'),
            }

        except Exception as e:
            return {
                "name": self.container_name,
                "status": "error",
                "runtime": self.runtime_type,
                "error": str(e)
            }

    def stop(self) -> bool:
        """
        停止容器

        Returns:
            bool: 成功返回 True

        Raises:
            RuntimeError: 停止失败
        """
        try:
            self._ensure_container()

            if self.container.status.lower() == "running":
                # 先恢复（如果暂停）
                if self.container.status.lower() == "paused":
                    self.container.unpause()

                # 停止容器
                self.container.stop(timeout=5)
                self.logger.info(f"🛑 容器已停止: {self.container_name}")

            return True

        except Exception as e:
            raise RuntimeError(f"容器停止失败: {e}") from e

    def remove(self) -> bool:
        """
        删除容器

        Returns:
            bool: 成功返回 True

        Raises:
            RuntimeError: 删除失败
        """
        try:
            self._ensure_container()

            # 先停止容器
            if self.container.status.lower() in ("running", "paused"):
                self.stop()

            # 删除容器
            self.container.remove()
            self.container = None

            self.logger.info(f"🗑️ 容器已删除: {self.container_name}")

            return True

        except Exception as e:
            raise RuntimeError(f"容器删除失败: {e}") from e

    def __del__(self):
        """析构函数：清理资源"""
        try:
            if hasattr(self, 'adapter') and self.adapter:
                self.adapter.close()
        except Exception:
            pass
