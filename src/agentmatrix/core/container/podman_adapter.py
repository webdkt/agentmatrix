"""
Podman Runtime Adapter - Podman 运行时适配器

实现 Podman 容器运行时的具体功能。
"""

import io
import logging
import platform
import subprocess
import time
from typing import Tuple, Dict, Optional, Any

try:
    import podman
    from podman import PodmanClient
    from podman.errors import PodmanError, APIError
    PODMAN_AVAILABLE = True
except ImportError:
    PODMAN_AVAILABLE = False
    PodmanClient = None  # type: ignore
    PodmanError = Exception

from .runtime_adapter import ContainerAdapter, ContainerHandle
from .compat import ContainerCompat


class PodmanHandle(ContainerHandle):
    """
    Podman 容器句柄

    封装 Podman Container 对象，实现统一的容器接口。
    """

    def __init__(self, container, logger: logging.Logger = None):
        """
        初始化 Podman 容器句柄

        Args:
            container: Podman Container 对象
            logger: 日志记录器（可选）
        """
        self._container = container
        self._logger = logger or logging.getLogger(__name__)

    def start(self):
        """启动容器"""
        try:
            self._container.start()
            self._logger.info(f"▶️ 容器已启动: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器启动失败: {e}") from e

    def stop(self, timeout: int = 5):
        """停止容器"""
        try:
            self._container.stop(timeout=timeout)
            self._logger.info(f"🛑 容器已停止: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器停止失败: {e}") from e

    def pause(self):
        """暂停容器"""
        try:
            self._container.pause()
            self._logger.info(f"⏸️ 容器已暂停: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器暂停失败: {e}") from e

    def unpause(self):
        """恢复暂停的容器"""
        try:
            self._container.unpause()
            self._logger.info(f"▶️ 容器已恢复: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器恢复失败: {e}") from e

    def reload(self):
        """刷新容器状态"""
        try:
            self._container.reload()
        except APIError as e:
            raise RuntimeError(f"容器状态刷新失败: {e}") from e

    def remove(self):
        """删除容器"""
        try:
            self._container.remove()
            self._logger.info(f"🗑️ 容器已删除: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器删除失败: {e}") from e

    def exec_run(self, cmd: str, **kwargs) -> Tuple[int, bytes]:
        """
        在容器内执行命令

        Podman 的 exec_run 返回格式与 Docker 完全兼容。
        """
        try:
            return self._container.exec_run(cmd, **kwargs)
        except APIError as e:
            raise RuntimeError(f"命令执行失败: {e}") from e

    @property
    def status(self) -> str:
        """获取容器状态"""
        return ContainerCompat.get_container_status(self._container)

    @property
    def short_id(self) -> str:
        """
        获取容器短ID

        Podman 容器没有 short_id 属性，需要从 attrs['Id'] 获取。
        """
        return ContainerCompat.get_short_id(self._container)

    @property
    def attrs(self) -> Dict[str, Any]:
        """获取容器完整属性"""
        return self._container.attrs

    def get_attribute(self, key: str, default: Any = None) -> Any:
        """获取容器指定属性"""
        return self._container.attrs.get(key, default)


class PodmanAdapter(ContainerAdapter):
    """
    Podman 运行时适配器

    实现 Podman 的具体功能，遵循 ContainerAdapter 接口。
    """

    def __init__(self, logger: logging.Logger = None):
        """
        初始化 Podman 适配器

        Args:
            logger: 日志记录器（可选）

        Raises:
            RuntimeError: Podman 未安装或连接失败
        """
        if not PODMAN_AVAILABLE:
            raise RuntimeError(
                "Podman Python SDK 未安装。\n"
                "请安装: pip install podman\n"
                "或使用: pip install -r requirements-podman.txt"
            )

        self._logger = logger or logging.getLogger(__name__)

        try:
            # Podman 使用与 Docker 相同的连接方式
            self.client = PodmanClient()
            self._logger.info("✅ Podman 客户端初始化成功")
        except Exception as e:
            raise RuntimeError(f"Podman 连接失败: {e}") from e

    def ping(self) -> bool:
        """测试与 Podman 的连接"""
        try:
            # Podman 3.x+ 支持 ping()
            if hasattr(self.client, 'ping'):
                self.client.ping()
            else:
                # 回退：尝试获取版本信息
                self.client.version()
            self._logger.info("✅ Podman 连接正常")
            return True
        except Exception as e:
            self._logger.error(f"❌ Podman 连接失败: {e}")
            raise

    def ensure_running(self) -> bool:
        """
        确保 Podman 正在运行

        如果 Podman 未运行，尝试自动启动。

        Returns:
            bool: 成功返回 True
        """
        def log(msg: str, level: int = logging.INFO):
            self._logger.log(level, msg)

        # 首先检查 Podman 是否已经在运行
        try:
            self.ping()
            log("✅ Podman 已在运行")
            return True
        except Exception:
            log("⚠️ Podman 未运行，尝试自动启动...")

        # Podman 未运行，尝试启动
        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                log("🔍 检测到 macOS，尝试启动 Podman VM...")
                subprocess.run(
                    ["podman", "machine", "start"],
                    check=True,
                    capture_output=True
                )
                log("⏳ Podman VM 启动中，等待连接...")

                # 等待 Podman daemon 启动（最多等待 30 秒）
                for i in range(30):
                    time.sleep(1)
                    try:
                        self.ping()
                        log(f"✅ Podman VM 已启动（耗时 {i + 1} 秒）")
                        return True
                    except Exception:
                        if i < 29:
                            log(f"等待中... ({i + 1}/30)", logging.DEBUG)
                        continue

                log("⚠️ Podman VM 启动超时，请手动启动", logging.WARNING)
                return False

            elif system == "Linux":
                log("🔍 检测到 Linux，尝试启动 Podman 服务...")
                # 尝试使用 systemctl
                try:
                    subprocess.run(
                        ["sudo", "systemctl", "start", "podman"],
                        check=True,
                        capture_output=True
                    )
                    log("✅ Podman 服务启动命令已执行，等待就绪...")

                    # 等待 Podman daemon 启动（最多等待 10 秒）
                    for i in range(10):
                        time.sleep(1)
                        try:
                            self.ping()
                            log(f"✅ Podman 服务已就绪（耗时 {i + 1} 秒）")
                            return True
                        except Exception:
                            continue

                    return True  # systemctl 成功，假设会最终启动
                except (subprocess.CalledProcessError, FileNotFoundError):
                    log("⚠️ 无法自动启动 Podman，请手动执行: sudo systemctl start podman", logging.WARNING)
                    return False

            elif system == "Windows":
                log("🔍 检测到 Windows，尝试启动 Podman...")
                # Windows 上 Podman 通常通过 WSL2 运行
                try:
                    subprocess.run(
                        ["podman", "machine", "start"],
                        check=True,
                        capture_output=True,
                        shell=True
                    )
                    log("⏳ Podman 启动中，等待连接...")

                    # 等待 Podman daemon 启动（最多等待 30 秒）
                    for i in range(30):
                        time.sleep(1)
                        try:
                            self.ping()
                            log(f"✅ Podman 已启动（耗时 {i + 1} 秒）")
                            return True
                        except Exception:
                            if i < 29:
                                log(f"等待中... ({i + 1}/30)", logging.DEBUG)
                            continue

                    log("⚠️ Podman 启动超时，请手动启动", logging.WARNING)
                    return False
                except Exception as e:
                    log(f"⚠️ Podman 启动失败: {e}", logging.WARNING)
                    return False

        except Exception as e:
            log(f"⚠️ 自动启动 Podman 失败: {e}", logging.WARNING)
            return False

        return False

    def create_container(
        self,
        name: str,
        image: str,
        volumes: Dict[str, Dict[str, str]],
        **kwargs
    ) -> PodmanHandle:
        """创建容器"""
        try:
            # 标准化卷配置
            normalized_volumes = ContainerCompat.normalize_volume_config(volumes)

            # 创建容器
            container = self.client.containers.create(
                image=image,
                name=name,
                volumes=normalized_volumes,
                **kwargs
            )

            # Podman 容器可能没有 short_id 属性
            container_id = ContainerCompat.get_short_id(container)
            self._logger.info(f"✅ 容器创建成功: {name} ({container_id})")
            return PodmanHandle(container, self._logger)

        except APIError as e:
            raise RuntimeError(f"容器创建失败: {e}") from e

    def get_container(self, name: str) -> Optional[PodmanHandle]:
        """获取已存在的容器"""
        try:
            container = self.client.containers.get(name)
            self._logger.info(f"📦 找到已存在的容器: {name}")
            return PodmanHandle(container, self._logger)
        except APIError:
            return None

    def close(self):
        """关闭 Podman 连接"""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
                self._logger.info("✅ Podman 连接已关闭")
        except Exception as e:
            self._logger.warning(f"关闭 Podman 连接时出错: {e}")
