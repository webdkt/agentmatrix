"""
LocalFileAgent Mixin - 让 Agent 直接操作宿主机文件

通过 LocalSession 提供宿主机持久 bash 会话，HOME 指向
workspace/agent_files/{agent_name}/home/，与容器内机制对称。

任何需要直接操作宿主机文件的 Agent 都可以混入此 Mixin。
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LocalFileAgentMixin:
    """
    本地文件操作 Mixin

    混入后 Agent 将：
    - 持有 local_session（宿主机持久 bash）
    - container_session 指向同一个 local_session（兼容 BaseAgent 现有逻辑）
    - switch_workspace 在宿主机建软链接（而非容器内）

    子类无需额外配置，只需在继承列表中加入此 Mixin（放在 BaseAgent 之前）。
    MRO 会确保 mixin 的方法优先被找到。
    """

    def _init_container_session(self):
        """覆写：初始化本地会话而非容器会话"""
        self._init_local_session()

    def _init_local_session(self):
        """初始化本地持久 bash 会话"""
        if self.runtime is None:
            raise RuntimeError("runtime 未注入，无法初始化 Local Session")

        from .container.local_session import LocalSession

        home_dir = str(self.runtime.paths.get_agent_home_dir(self.name))
        env_bin = self.runtime.paths.get_shared_env_bin()

        session = LocalSession(
            home_dir=home_dir,
            logger=logging.getLogger(f"local_session.{self.name}"),
            env_bin_path=env_bin,
        )
        session.start()

        # 同时设置 local_session 和 container_session
        # container_session 是 BaseAgent 现有逻辑的入口（_on_activate_session 等都检查它）
        self.local_session = session
        self.container_session = session

        self.logger.info(f"Local Session 初始化成功 (HOME={home_dir})")

        # 设置 output mirror
        self._setup_output_mirror()

    async def switch_workspace(self, task_id: str) -> bool:
        """
        覆写：切换工作目录（宿主机软链接）

        与 BaseAgent.switch_workspace 对称：
        - 宿主机创建 work_files/{task_id}/ 目录
        - 在 home 下重建 ~/current_task 软链接
        """
        print("local file agent switch workspace")
        session = self.local_session
        if session is None:
            raise RuntimeError("Local Session 未初始化")

        # 1. 宿主机创建 task 目录
        task_dir = self.runtime.paths.get_agent_work_files_dir(self.name, task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        # 2. 在宿主机 home 下重建软链接
        home_dir = self.runtime.paths.get_agent_home_dir(self.name)
        symlink_path = home_dir / "current_task"
        symlink_target = str(task_dir)

        self.logger.info(f"switch_workspace: {symlink_path} -> {symlink_target}")

        # 先删除旧链接，再创建新的（和容器内逻辑一致）
        if symlink_path.is_symlink() or symlink_path.exists():
            symlink_path.unlink()
        symlink_path.symlink_to(symlink_target)

        # 3. 验证 + cd
        exit_code, stdout, stderr = await asyncio.to_thread(
            session.execute, "cd ~/current_task && pwd"
        )
        if exit_code != 0:
            self.logger.warning(f"cd ~/current_task 失败: {stderr}")
            return False

        self.logger.info(f"工作目录已切换: {self.name} -> {task_id}")
        return True
