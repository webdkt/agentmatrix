"""
Single Container Manager - 单容器多用户架构

所有 Agent 共享一个容器，每个 Agent 拥有独立的 Linux 用户。
- Linux 用户名: sanitize_username(agent_name) — 仅用于 useradd/su/chown
- 所有目录路径: 使用原始 agent_name
- 工作区: /data/agents/{agent_name}/work_files/
- 主目录: /data/agents/{agent_name}/home/
"""

import hashlib
import logging
import os
import platform
import re
from pathlib import Path
from typing import Tuple, Dict, Optional, Any

from .runtime_factory import ContainerRuntimeFactory
from .runtime_adapter import ContainerAdapter, ContainerHandle
from .compat import ContainerCompat
from .container_session import ContainerSession
from ..log_util import AutoLoggerMixin


def sanitize_username(agent_name: str) -> str:
    """
    将 Agent 名称转换为合法的 Linux 用户名。

    Linux 用户名规则:
    - 最多 32 个字符
    - 只能包含 [a-zA-Z0-9_-]
    - 必须以字母或下划线开头

    对于中文名称或其他非 ASCII 字符，使用 SHA256 哈希生成唯一短名。

    Args:
        agent_name: Agent 原始名称

    Returns:
        str: 合法的 Linux 用户名
    """
    # 尝试直接清理
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", agent_name)
    slug = slug.lower().strip("_")

    # 确保以字母开头
    if slug and slug[0].isalpha() and len(slug) <= 32:
        return slug

    # 回退到哈希方案
    hash_obj = hashlib.sha256(agent_name.encode("utf-8"))
    short_hash = hash_obj.hexdigest()[:8]
    return f"agent_{short_hash}"


class SingleContainerManager(AutoLoggerMixin):
    """
    单容器多用户管理器

    所有 Agent 共享一个 Linux 容器，每个 Agent 是容器内的一个独立 Linux 用户。

    命名约定：
    - agent_name: Agent 原始名称（用于所有目录路径）
    - username: sanitize_username(agent_name) 结果（仅用于 Linux 用户名）

    目录结构（容器内，使用 agent_name）:
    /data/agents/{agent_name}/
    ├── home/          # Agent 主目录
    └── work_files/    # 工作目录 (→ 当前 session 的工作区)
    """

    # 共享容器的固定名称
    SHARED_CONTAINER_NAME = "agentmatrix_shared"
    DEFAULT_IMAGE = "agentmatrix:latest"

    def __init__(
        self,
        workspace_root: Path,
        image_name: str = None,
        runtime_type: str = None,
        parent_logger: Optional[logging.Logger] = None,
        proxy_config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化单容器管理器

        Args:
            workspace_root: 工作区根目录
            image_name: 镜像名称
            runtime_type: 运行时类型 ('docker', 'podman', 'auto')
            parent_logger: 父级 logger
            proxy_config: HTTP 代理配置
        """
        self.workspace_root = workspace_root
        self.image_name = image_name or self.DEFAULT_IMAGE
        self.proxy_config = proxy_config

        if parent_logger:
            self._parent_logger = parent_logger.getChild("single_container")
        else:
            self._parent_logger = logging.getLogger("single_container")

        # 初始化容器运行时适配器
        self.adapter: ContainerAdapter = ContainerRuntimeFactory.create(
            runtime_type=runtime_type, logger=self.logger
        )

        # 检测运行时类型
        self.runtime_type = ContainerCompat.detect_runtime_type(self.adapter)
        self.logger.info(f"使用容器运行时: {self.runtime_type}")

        # 容器句柄
        self.container: Optional[ContainerHandle] = None

        # 已注册的 Agent 用户 {username: ContainerSession}
        self._container_sessions: Dict[str, ContainerSession] = {}

        # 已注册的用户名集合
        self._registered_users: set = set()

        # 宿主机目录
        self.agents_root = workspace_root / "agent_files"

    # ==================== 容器生命周期 ====================

    def _ensure_container(self) -> None:
        """确保共享容器存在且正在运行"""
        if self.container is not None:
            return

        existing = self.adapter.get_container(self.SHARED_CONTAINER_NAME)
        if existing:
            self.container = existing
            self.logger.info(f"找到已存在的共享容器: {self.SHARED_CONTAINER_NAME}")
            if self.container.status.lower() != "running":
                self.container.start()
                self.logger.info("共享容器已启动")
        else:
            self._create_shared_container()

    def _create_shared_container(self) -> None:
        """创建共享容器"""
        # 确保宿主机目录存在
        self.agents_root.mkdir(parents=True, exist_ok=True)

        # 挂载配置
        volumes = {
            str(self.agents_root): {"bind": "/data/agents", "mode": "rw"},
        }

        # 环境变量
        environment = {}

        # HTTP Proxy 支持
        proxy_url = self._resolve_proxy_url()
        if proxy_url:
            environment["HTTP_PROXY"] = proxy_url
            environment["HTTPS_PROXY"] = proxy_url

        # X11 转发支持
        enable_x11 = os.environ.get("AGENTMATRIX_X11", "").lower() == "true"
        ipc_mode = None

        if enable_x11:
            system = platform.system()
            if system == "Linux":
                x11_socket = "/tmp/.X11-unix"
                if os.path.exists(x11_socket):
                    volumes[x11_socket] = {"bind": x11_socket, "mode": "rw"}
                environment["DISPLAY"] = os.environ.get("DISPLAY", ":0")
                ipc_mode = "host"
                self.logger.info("X11 转发已启用 (Linux)")

        create_kwargs = {
            "name": self.SHARED_CONTAINER_NAME,
            "image": self.image_name,
            "volumes": volumes,
            "environment": environment,
            "detach": True,
            "tty": True,
            "auto_remove": False,
        }
        if ipc_mode:
            create_kwargs["ipc_mode"] = ipc_mode

        self.container = self.adapter.create_container(**create_kwargs)
        self.container.start()
        self.logger.info(f"共享容器已创建并启动: {self.SHARED_CONTAINER_NAME}")

    def _resolve_proxy_url(self) -> Optional[str]:
        """解析代理 URL"""
        if self.proxy_config and self.proxy_config.get("enabled"):
            proxy_port = self.proxy_config.get("port")
            if proxy_port:
                if self.runtime_type == "podman":
                    proxy_host = "host.containers.internal"
                else:
                    proxy_host = "host.docker.internal"
                return f"http://{proxy_host}:{proxy_port}"

        system_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        if system_proxy:
            if re.search(r"://(127\.0\.0\.1|localhost)", system_proxy):
                if self.runtime_type == "podman":
                    container_host = "host.containers.internal"
                else:
                    container_host = "host.docker.internal"
                return re.sub(
                    r"://(127\.0\.0\.1|localhost)",
                    f"://{container_host}",
                    system_proxy,
                )
            return system_proxy
        return None

    def wakeup(self) -> bool:
        """唤醒容器（确保正在运行）"""
        try:
            self._ensure_container()
            self.container.reload()
            status = self.container.status.lower()

            if status == "paused":
                self.container.unpause()
                self.logger.info("共享容器已恢复")
            elif status in ("created", "exited"):
                self.container.start()
                self.logger.info("共享容器已启动")
            elif status == "running":
                pass
            else:
                raise RuntimeError(f"未知的容器状态: {status}")

            return True
        except Exception as e:
            raise RuntimeError(f"容器唤醒失败: {e}") from e

    def hibernate(self) -> bool:
        """
        休眠容器。

        注意：在单容器架构中，容器被所有 Agent 共享，
        不应因单个 Agent 空闲而暂停。此方法保留为 no-op 以保持接口兼容。
        """
        return True

    # ==================== 用户管理 ====================

    def ensure_user(self, agent_name: str) -> str:
        """
        确保 Agent 对应的 Linux 用户存在。

        流程：
        1. 在宿主机创建目录（workspace/agent_files/{agent_name}/）
        2. 因为 volume mount，容器内自动有了 /data/agents/{agent_name}/
        3. 在容器内创建用户，home 指向 /data/agents/{agent_name}/home

        注意：username（sanitize 结果）只用于 Linux 用户名。
        所有目录路径使用原始 agent_name。

        Args:
            agent_name: Agent 名称

        Returns:
            str: 用户名
        """
        username = sanitize_username(agent_name)
        self._ensure_container()

        if self.container.status.lower() != "running":
            self.wakeup()

        # 第一步：在宿主机创建目录（无论用户是否存在都要创建）
        # 因为 workspace/agent_files/ 挂载到 /data/agents/，
        # 宿主机创建的目录会自动出现在容器内
        agent_home = self.agents_root / agent_name / "home"
        agent_work = self.agents_root / agent_name / "work_files"

        self.logger.debug(f"Creating directories on host: home={agent_home}, work={agent_work}")
        agent_home.mkdir(parents=True, exist_ok=True)
        agent_work.mkdir(parents=True, exist_ok=True)

        # 验证目录是否创建成功
        if not agent_home.exists():
            self.logger.error(f"Failed to create home directory: {agent_home}")
        if not agent_work.exists():
            self.logger.error(f"Failed to create work directory: {agent_work}")

        # 检查用户是否已存在
        check_cmd = f"id -u {username} 2>/dev/null"
        exit_code, output = self._exec_as_root(check_cmd)

        if exit_code == 0:
            self.logger.debug(f"用户已存在: {username}")
            self._registered_users.add(username)
            # 校验 home 目录是否正确（修复旧版本用 username 建路径的 bug）
            expected_home = f"/data/agents/{agent_name}/home"
            actual_home_cmd = f"eval echo ~{username}"
            ec, actual_home = self._exec_as_root(actual_home_cmd)
            if ec == 0 and actual_home.strip() != expected_home:
                self.logger.info(
                    f"修正用户 {username} 的 home 目录: {actual_home.strip()} -> {expected_home}"
                )
                # 修改用户的 home 目录（宿主机目录已创建，只需修改用户配置）
                self._exec_as_root(
                    f"chown -R {username}:{username} /data/agents/{agent_name}"
                )
                # 修改用户的 home 目录
                self._exec_as_root(f"usermod -d {expected_home} {username}")
            return username

        # 第二步：在容器内创建用户
        # -M: 不创建默认 home（我们用宿主机创建的目录）
        # -d: 指定 home 目录为 /data/agents/{agent_name}/home
        # 注意：路径用 agent_name，用户名用 username
        setup_commands = [
            f"useradd -M -d /data/agents/{agent_name}/home -s /bin/bash {username}",
            f"chown -R {username}:{username} /data/agents/{agent_name}",
            f"ls -la /data/agents/{agent_name}/ || echo 'Directory check failed'",
        ]

        for cmd in setup_commands:
            exit_code, output = self._exec_as_root(cmd)
            if exit_code != 0:
                if "already exists" in output:
                    self.logger.debug(f"用户 {username} 已存在（并发创建）")
                    break
                self.logger.warning(f"命令失败 [{cmd}]: {output}")

        self._registered_users.add(username)
        self.logger.info(
            f"用户已创建: {username} (agent: {agent_name}), home={agent_home}"
        )
        return username

    def remove_user(self, agent_name: str) -> bool:
        """
        删除 Agent 对应的 Linux 用户。

        Args:
            agent_name: Agent 名称

        Returns:
            bool: 是否成功
        """
        username = sanitize_username(agent_name)
        self._ensure_container()

        # 停止该用户的会话
        if username in self._container_sessions:
            self._container_sessions[username].stop()
            del self._container_sessions[username]

        # 删除用户（保留数据目录，仅删除系统用户）
        exit_code, output = self._exec_as_root(f"userdel {username} 2>&1")
        if exit_code != 0 and "does not exist" not in output:
            self.logger.warning(f"删除用户失败: {output}")
            return False

        self._registered_users.discard(username)
        self.logger.info(f"用户已删除: {username}")
        return True

    def get_username(self, agent_name: str) -> str:
        """获取 Agent 对应的用户名"""
        return sanitize_username(agent_name)

    # ==================== 会话管理 ====================

    def get_container_session(self, agent_name: str) -> ContainerSession:
        """
        获取或创建 Agent 的持久终端连接。

        这是一个到容器的终端连接（类似 SSH），用于执行命令。
        与 Agent 的业务 session 无关，仅确保终端连接存活。

        Args:
            agent_name: Agent 名称

        Returns:
            ContainerSession: Agent 的持久终端连接
        """
        username = sanitize_username(agent_name)

        # 确保用户存在
        self.ensure_user(agent_name)

        # 检查现有终端连接（用 username 作为 key）
        if username in self._container_sessions:
            container_session = self._container_sessions[username]
            if container_session.is_alive():
                return container_session
            # 连接已断开，重新创建
            container_session.stop()

        # 创建新终端连接
        self._ensure_container()
        if self.container.status.lower() != "running":
            self.wakeup()

        container_session = ContainerSession(
            container_name=self.SHARED_CONTAINER_NAME,
            runtime_type=self.runtime_type,
            initial_workdir=None,
            logger=self.logger,
            username=username,
        )
        container_session.start()
        self._container_sessions[username] = container_session
        self.logger.info(
            f"终端连接已建立: {username} (agent: {agent_name}, container_session: {container_session.session_id})"
        )
        return container_session

    def stop_container_session(self, agent_name: str) -> None:
        """停止 Agent 的持久会话"""
        username = sanitize_username(agent_name)
        if username in self._container_sessions:
            self._container_sessions[username].stop()
            del self._container_sessions[username]

    # ==================== 命令执行 ====================

    async def exec_command(
        self,
        command: str,
        agent_name: str,
        timeout: int = 3600,
    ) -> Tuple[int, str, str]:
        """
        以 Agent 用户身份在容器内执行命令。

        Args:
            command: 要执行的命令
            agent_name: Agent 名称（用于确定执行用户）
            timeout: 超时时间（秒）

        Returns:
            Tuple[int, str, str]: (退出码, stdout, stderr)
        """
        import asyncio

        session = self.get_container_session(agent_name)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: session.execute(command, timeout)
        )

    # ==================== 工作区管理 ====================

    # ==================== 状态查询 ====================

    def get_status(self) -> Dict:
        """获取容器状态"""
        try:
            self._ensure_container()
            self.container.reload()
            return {
                "name": self.SHARED_CONTAINER_NAME,
                "id": self.container.short_id,
                "status": self.container.status,
                "image": self.image_name,
                "runtime": self.runtime_type,
                "registered_users": list(self._registered_users),
            }
        except Exception as e:
            return {
                "name": self.SHARED_CONTAINER_NAME,
                "status": "error",
                "runtime": self.runtime_type,
                "error": str(e),
            }

    def stop(self) -> bool:
        """停止容器"""
        try:
            # 停止所有会话
            for session in self._container_sessions.values():
                session.stop()
            self._container_sessions.clear()

            self._ensure_container()
            if self.container.status.lower() == "running":
                self.container.stop(timeout=5)
                self.logger.info("共享容器已停止")
            return True
        except Exception as e:
            raise RuntimeError(f"容器停止失败: {e}") from e

    def remove(self) -> bool:
        """删除容器"""
        try:
            for session in self._container_sessions.values():
                session.stop()
            self._container_sessions.clear()

            self._ensure_container()
            if self.container.status.lower() in ("running", "paused"):
                self.stop()
            self.container.remove()
            self.container = None
            self.logger.info("共享容器已删除")
            return True
        except Exception as e:
            raise RuntimeError(f"容器删除失败: {e}") from e

    # ==================== 内部工具 ====================

    def _exec_as_root(self, command: str) -> Tuple[int, str]:
        """
        以 root 身份在容器内执行命令。

        通过容器 SDK（Docker/Podman Python SDK）执行，而不是 subprocess CLI，
        避免在 macOS .app 环境下找不到 docker/podman CLI 的问题。

        Args:
            command: 要执行的命令

        Returns:
            Tuple[int, str]: (退出码, 输出)
        """
        try:
            if self.container is None:
                return -1, "容器未初始化"

            exit_code, output = self.container.exec_run(
                ["sh", "-c", command],
                user="0",
            )
            if isinstance(output, bytes):
                # Strip Docker/Podman stream header (8-byte framing: type + padding + length)
                # First byte is stream type (0x01=stdout, 0x02=stderr), followed by 7 bytes padding/length
                if len(output) > 8 and output[0] in (0x01, 0x02):
                    output = output[8:]
                output_str = output.decode("utf-8", errors="replace")
            else:
                output_str = str(output)
            return exit_code, output_str.strip()
        except Exception as e:
            return -1, str(e)

    def __del__(self):
        """析构函数：清理资源"""
        try:
            for session in self._container_sessions.values():
                session.stop()
        except Exception:
            pass
        try:
            if hasattr(self, "adapter") and self.adapter:
                self.adapter.close()
        except Exception:
            pass
