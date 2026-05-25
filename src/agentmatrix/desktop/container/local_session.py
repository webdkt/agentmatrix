"""
Local Session - 宿主机持久 Shell 会话

与 ContainerSession 接口一致，但直接在宿主机启动 bash 进程，
通过设置 HOME 环境变量实现"幻影"效果：Agent 的 ~ 指向 workspace 下的专属目录。
"""

import os
import subprocess
import logging
from typing import Optional

from .container_session import ContainerSession


class LocalSession(ContainerSession):
    """
    宿主机持久 Shell 会话

    继承 ContainerSession 的全部协议（marker 分隔、reader 线程、健康检查等），
    仅覆写 start()：直接启动 bash 而非 podman exec，并通过 HOME 环境变量
    让 Agent 的 ~ 指向 workspace/agent_files/{agent_name}/home/。

    切换 task 时，宿主机上建软链接 ~/current_task -> work_files/{task_id}，
    与容器内机制完全对称。
    """

    def __init__(
        self,
        home_dir: str,
        initial_workdir: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        env_bin_path: Optional[str] = None,
    ):
        """
        Args:
            home_dir: Agent 的 home 目录（宿主机绝对路径）
                      即 workspace/agent_files/{agent_name}/home/
            initial_workdir: 初始工作目录，默认为 home_dir
            logger: 日志器
            env_bin_path: 共享 Python 环境的 bin 目录，会前置到 PATH
        """
        # 调用父类 __init__ 初始化所有协议相关的属性
        # container_name/runtime_type/username 对本地会话无意义，传占位值
        super().__init__(
            container_name="local",
            runtime_type="local",
            initial_workdir=initial_workdir or home_dir,
            logger=logger,
            username=None,
        )
        self.home_dir = home_dir
        self.env_bin_path = env_bin_path

    def start(self) -> None:
        """
        启动宿主机持久 bash 会话

        直接启动 bash，设置 HOME 为 Agent 的 workspace home 目录。
        这样 ~ 自然指向正确位置，无需额外路径转换。
        """
        if self.is_active:
            self.logger.warning(f"LocalSession {self.session_id} 已经在运行")
            return

        # 确保 home 目录存在
        os.makedirs(self.home_dir, exist_ok=True)

        # 干净环境：不继承 app 进程的 conda/tauri 等变量
        env = {
            "HOME": self.home_dir,
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "TERM": "xterm-256color",
            "LANG": "en_US.UTF-8",
        }
        if self.env_bin_path:
            env["PATH"] = f"{self.env_bin_path}:{env['PATH']}"

        self.logger.info(
            f"启动本地会话: HOME={self.home_dir}, workdir={self.initial_workdir}"
        )

        self.process = subprocess.Popen(
            ["bash"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
            cwd=self.initial_workdir,
            env=env,
        )

        self.is_active = True

        # 启动输出读取线程（复用 ContainerSession 的 _read_stdout/_read_stderr）
        import threading
        self._reader_thread = threading.Thread(
            target=self._read_stdout,
            daemon=True,
            name=f"local-{self.session_id}-stdout",
        )
        self._stderr_reader_thread = threading.Thread(
            target=self._read_stderr,
            daemon=True,
            name=f"local-{self.session_id}-stderr",
        )
        self._reader_thread.start()
        self._stderr_reader_thread.start()

        # 进入工作目录
        self._send_raw(f"cd {self.initial_workdir}\n")

        self.logger.info(f"本地会话 {self.session_id} 已启动 (HOME={self.home_dir})")
