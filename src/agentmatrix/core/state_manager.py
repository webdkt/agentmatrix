"""
StateManagerMixin — Agent 状态管理基础能力。

提供 pause/resume/stop/checkpoint 协作式状态机。
Shell 实现通过继承此 Mixin 获得标准状态管理，
再通过 _on_stop() hook 和 update_status() 添加具体业务逻辑。
"""

from __future__ import annotations

import asyncio
import logging


class StateManagerMixin:
    """
    Agent 状态管理基础能力。

    提供:
    - checkpoint(): 协作式检查点（Core 在关键位置调用）
    - pause() / resume(): 暂停/恢复
    - stop(): 停止当前 session

    子类需要:
    - 提供 self.logger (logging.Logger)
    - 实现 update_status(new_status=...) 方法
    - 可选覆盖 _on_stop() 添加 session 清理逻辑
    """

    def _init_state_manager(self) -> None:
        """初始化状态管理变量。在子类 __init__ 中调用。"""
        self._paused: bool = False
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()  # 初始不阻塞

        self._stopped: bool = False
        self._stop_event: asyncio.Event = asyncio.Event()
        self._stop_event.set()  # 初始不阻塞

        self._is_stopping: bool = False

    # ========== Checkpoint ==========

    async def checkpoint(self) -> None:
        """协作式检查点：在 Agent 关键位置调用。

        如果处于停止或暂停状态，挂起当前协程直到恢复。
        """
        if self._stopped:
            self.logger.debug(f"Agent {self.name} 检查到停止，等待恢复...")
            await self._stop_event.wait()
            self.logger.debug(f"Agent {self.name} 从停止状态恢复")
        if self._paused:
            self.logger.debug(f"Agent {self.name} 检查到暂停，等待恢复...")
            await self._pause_event.wait()
            self.logger.debug(f"Agent {self.name} 已恢复执行")

    # ========== Pause / Resume ==========

    async def pause(self) -> None:
        """暂停 Agent 执行。"""
        if self._paused:
            self.logger.warning(f"Agent {self.name} 已经是暂停状态")
            return

        self._paused = True
        self._pause_event.clear()
        self.logger.info(f"Agent {self.name} 已暂停")
        self.update_status(new_status="PAUSED")

    async def resume(self) -> None:
        """恢复 Agent 执行。"""
        if self._paused:
            self._paused = False
            self._pause_event.set()
            self.logger.info(f"Agent {self.name} 从暂停状态恢复")
            self.update_status(new_status="IDLE")
        else:
            self.logger.warning(f"Agent {self.name} 未暂停")

    # ========== Stop ==========

    def stop(self) -> None:
        """停止 Agent：取消当前 active session。"""
        self._is_stopping = True
        self._on_stop()
        self.update_status(new_status="STOPPED")

    def _on_stop(self) -> None:
        """停止时的清理 hook。子类覆盖以添加具体清理逻辑。"""
        pass

    @property
    def is_paused(self) -> bool:
        """返回 Agent 是否暂停。"""
        return self._paused
