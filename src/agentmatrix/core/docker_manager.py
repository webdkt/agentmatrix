"""
Docker 容器管理器

负责 Agent 容器的生命周期管理、工作区切换和命令执行。
"""

import docker
from docker.errors import DockerException, APIError
from pathlib import Path
from typing import Tuple, Dict, Optional
import logging
from datetime import datetime
import platform
import subprocess
import time


def ensure_docker_running(logger: Optional[logging.Logger] = None) -> bool:
    """
    确保 Docker 正在运行，如果未运行则尝试自动启动

    这是一个全局初始化函数，应该在系统启动时调用一次，
    而不是在每个 Agent 初始化时调用。

    Args:
        logger: 日志记录器（可选）

    Returns:
        bool: Docker 是否成功运行
    """
    def log(msg: str, level: int = logging.INFO):
        if logger:
            logger.log(level, msg)
        else:
            print(msg)

    # 首先检查 Docker 是否已经在运行
    try:
        client = docker.from_env()
        client.ping()
        log("✅ Docker 已在运行")
        return True
    except DockerException:
        log("⚠️ Docker 未运行，尝试自动启动...")

    # Docker 未运行，尝试启动
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            log("🔍 检测到 macOS，尝试启动 Docker Desktop...")
            subprocess.run(
                ["open", "-a", "Docker"],
                check=True,
                capture_output=True
            )
            log("⏳ Docker Desktop 启动中，等待连接...")

            # 等待 Docker daemon 启动（最多等待 30 秒）
            for i in range(30):
                time.sleep(1)
                try:
                    test_client = docker.from_env()
                    test_client.ping()
                    log(f"✅ Docker Desktop 已启动（耗时 {i + 1} 秒）")
                    return True
                except DockerException:
                    if i < 29:
                        log(f"等待中... ({i + 1}/30)", logging.DEBUG)
                    continue

            log("⚠️ Docker Desktop 启动超时，请手动启动", logging.WARNING)
            return False

        elif system == "Linux":
            log("🔍 检测到 Linux，尝试启动 Docker 服务...")
            # 尝试使用 systemctl
            try:
                subprocess.run(
                    ["sudo", "systemctl", "start", "docker"],
                    check=True,
                    capture_output=True
                )
                log("✅ Docker 服务启动命令已执行，等待就绪...")

                # 等待 Docker daemon 启动（最多等待 10 秒）
                for i in range(10):
                    time.sleep(1)
                    try:
                        test_client = docker.from_env()
                        test_client.ping()
                        log(f"✅ Docker 服务已就绪（耗时 {i + 1} 秒）")
                        return True
                    except DockerException:
                        continue

                return True  # systemctl 成功，假设会最终启动
            except (subprocess.CalledProcessError, FileNotFoundError):
                log("⚠️ 无法自动启动 Docker，请手动执行: sudo systemctl start docker", logging.WARNING)
                return False

        elif system == "Windows":
            log("🔍 检测到 Windows，尝试启动 Docker Desktop...")
            # Docker Desktop 在 Windows 上的常见路径
            docker_paths = [
                r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
                r"C:\Program Files\Docker\Docker\DockerCli.exe",
            ]

            for docker_path in docker_paths:
                try:
                    if Path(docker_path).exists():
                        subprocess.Popen(
                            [docker_path],
                            shell=True
                        )
                        log("⏳ Docker Desktop 启动中，等待连接...")

                        # 等待 Docker daemon 启动（最多等待 30 秒）
                        for i in range(30):
                            time.sleep(1)
                            try:
                                test_client = docker.from_env()
                                test_client.ping()
                                log(f"✅ Docker Desktop 已启动（耗时 {i + 1} 秒）")
                                return True
                            except DockerException:
                                if i < 29:
                                    log(f"等待中... ({i + 1}/30)", logging.DEBUG)
                                continue

                        log("⚠️ Docker Desktop 启动超时，请手动启动", logging.WARNING)
                        return False
                except Exception as e:
                    log(f"尝试路径 {docker_path} 失败: {e}", logging.DEBUG)
                    continue

            log(
                "⚠️ 未找到 Docker Desktop，请确保已安装 Docker Desktop\n"
                "下载地址: https://www.docker.com/products/docker-desktop/",
                logging.WARNING
            )
            return False

    except Exception as e:
        log(f"⚠️ 自动启动 Docker 失败: {e}", logging.WARNING)
        return False

    return False


class DockerContainerManager:
    """
    Docker 容器管理器

    职责：
    - 容器生命周期管理（创建、唤醒、休眠、停止）
    - 符号链接动态切换（switch_workspace）
    - 容器内命令执行接口（exec_command）
    - 目录初始化（initialize_directories）
    """

    def __init__(
        self,
        agent_name: str,
        workspace_root: str,
        image_name: str = "agentmatrix:latest",
        parent_logger: Optional[logging.Logger] = None
    ):
        """
        初始化 Docker 容器管理器

        Args:
            agent_name: Agent 名称
            workspace_root: 工作区根目录
            image_name: Docker 镜像名称
            parent_logger: 父级 logger（可选）

        Raises:
            RuntimeError: Docker 未安装或未运行
        """
        self.agent_name = agent_name
        self.workspace_root = Path(workspace_root)
        self.image_name = image_name

        # 设置 logger
        if parent_logger:
            self.logger = parent_logger.getChild(f"docker_{agent_name}")
        else:
            self.logger = logging.getLogger(f"docker.{agent_name}")

        # 初始化 Docker 客户端
        # 注意: Docker 的启动检查应该在系统初始化时完成（见 ensure_docker_running）
        # 这里只负责连接，如果连接失败说明系统初始化有问题
        try:
            self.client = docker.from_env()
            # 测试连接
            self.client.ping()
            self.logger.info("✅ Docker 连接成功")
        except DockerException as e:
            raise RuntimeError(
                f"Docker 连接失败。如果 Docker Desktop 未运行，请手动启动。\n"
                f"启动方法：\n"
                f"  - macOS: 打开 Docker Desktop 应用\n"
                f"  - Linux: sudo systemctl start docker\n"
                f"  - Windows: 从开始菜单启动 Docker Desktop\n"
                f"下载: https://www.docker.com/products/docker-desktop/\n"
                f"原始错误: {e}"
            ) from e

        # 目录路径
        self.skills_dir = self.workspace_root / "SKILLS"
        self.agent_files_dir = self.workspace_root / "agent_files" / agent_name
        self.agent_home = self.agent_files_dir / "home"
        self.work_files_base = self.agent_files_dir / "work_files"

        # 容器名称（标准化）
        self.container_name = f"agent_{agent_name}"

        # 容器对象（延迟创建）
        self.container = None

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
        创建 Docker 容器

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
            self.container = self.client.containers.create(
                image=self.image_name,
                name=self.container_name,
                volumes=volumes,
                detach=True,
                tty=True,  # 保持容器运行
                auto_remove=False,  # 不自动删除，便于调试
                # 可选：资源限制
                # mem_limit='1g',
                # cpu_quota=100000,
            )

            self.logger.info(f"✅ 容器创建成功: {self.container_name} ({self.container.short_id})")

        except APIError as e:
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

            self.logger.info("✅ 默认工作区符号链接已创建: /work_files -> /work_files_base/default")

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
            try:
                self.container = self.client.containers.get(self.container_name)
                self.logger.info(f"📦 找到已存在的容器: {self.container_name}")
            except APIError:
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

        except APIError as e:
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
                    f"容器未运行，无需休眠: {self.container_name} (status: {self.container.status})"
                )

            return True

        except APIError as e:
            raise RuntimeError(f"容器休眠失败: {e}") from e

    def switch_workspace(self, user_session_id: str) -> bool:
        """
        切换工作区符号链接

        在容器内重新创建 /work_files 符号链接，指向：
        /work_files_base/{user_session_id}/

        Args:
            user_session_id: 用户会话 ID

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
            session_dir = self.work_files_base / user_session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            # 3. 容器内删除旧链接
            rm_cmd = "rm -rf /work_files"
            exit_code, _ = self.container.exec_run(rm_cmd, workdir="/")
            if exit_code != 0:
                self.logger.warning(f"删除旧链接失败（可能不存在）: {rm_cmd}")

            # 4. 容器内创建新符号链接
            ln_cmd = f"ln -s /work_files_base/{user_session_id} /work_files"
            exit_code, output = self.container.exec_run(ln_cmd, workdir="/")

            if exit_code != 0:
                error_msg = output.decode('utf-8', errors='ignore').strip()
                raise RuntimeError(f"符号链接创建失败: {error_msg}")

            self.logger.info(f"🔄 工作区已切换: /work_files -> /work_files_base/{user_session_id}")

            return True

        except APIError as e:
            raise RuntimeError(f"工作区切换失败: {e}") from e

    async def exec_command(
        self,
        command: str
    ) -> Tuple[int, str, str]:
        """
        在容器内执行命令（async 版本）

        所有命令在 /work_files 目录下执行（内部使用 cd 处理符号链接）

        Args:
            command: 要执行的命令

        Returns:
            Tuple[int, str, str]: (退出码, stdout, stderr)

        Raises:
            RuntimeError: 命令执行失败
        """
        try:
            self._ensure_container()

            # 确保容器已运行
            if self.container.status.lower() != "running":
                self.wakeup()

            # 执行命令（在线程池中执行，避免阻塞事件循环）
            # 使用列表形式，在命令内部 cd 到 /work_files
            import asyncio
            loop = asyncio.get_event_loop()

            # 在命令内部 cd，避免 Docker workdir 参数的符号链接问题
            full_command = f"cd /work_files && {command}"

            exit_code, output = await loop.run_in_executor(
                None,
                lambda: self.container.exec_run(
                    ["sh", "-c", full_command],  # 列表形式
                    demux=True
                )
            )

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

        except APIError as e:
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
        """
        try:
            self._ensure_container()

            self.container.reload()  # 刷新状态

            return {
                "name": self.container_name,
                "id": self.container.short_id,
                "status": self.container.status,
                "image": self.image_name,
                "created": self.container.attrs.get('Created'),
            }

        except APIError as e:
            return {
                "name": self.container_name,
                "status": "error",
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

        except APIError as e:
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

        except APIError as e:
            raise RuntimeError(f"容器删除失败: {e}") from e

    def __del__(self):
        """析构函数：清理资源"""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
        except Exception:
            pass
