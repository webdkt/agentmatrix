"""
系统电源管理器

功能：
- 防止系统休眠（保持CPU运行）
- 允许显示器休眠（省电）
- 跨平台支持（Mac优先，Windows预留）

设计原则：
- 只管理系统级电源，不涉及具体业务
- 简单可靠，使用系统自带工具
- 可配置：可以启用/禁用防休眠
"""

import sys
import subprocess
import logging
from typing import Optional
from .log_util import AutoLoggerMixin


class PowerManager(AutoLoggerMixin):
    """系统电源管理器"""

    def __init__(self, enabled: bool = True, parent_logger: Optional[logging.Logger] = None):
        """
        初始化电源管理器

        Args:
            enabled: 是否启用电源管理
            parent_logger: 父组件的logger
        """
        self.enabled = enabled
        self.platform = sys.platform
        self._active = False
        self._parent_logger = parent_logger
        self.caffeinate_proc = None

    def _get_log_context(self) -> dict:
        """提供日志上下文变量"""
        return {
            "service": "PowerManager",
        }

    async def start(self):
        """启动电源管理（防止系统休眠）"""
        self.start_sync()

    def start_sync(self):
        """启动电源管理（同步版本）"""
        if not self.enabled:
            self.echo("PowerManager disabled by configuration")
            return

        if self.platform == "darwin":
            self._start_mac()
        elif self.platform == "win32":
            self._start_windows()
        else:
            self.echo(f"Platform {self.platform} not supported, skipping")

    async def stop(self):
        """停止电源管理（恢复默认行为）"""
        self.stop_sync()

    def stop_sync(self):
        """停止电源管理（同步版本）"""
        if not self._active:
            return

        if self.platform == "darwin":
            self._stop_mac()
        elif self.platform == "win32":
            self._stop_windows()

    def _start_mac(self):
        """macOS: 防止系统休眠，允许显示器休眠"""
        # 使用 caffeinate -i 只防止系统空闲休眠
        # -i: 防止系统空闲休眠（系统保持运行）
        # 不使用 -d: 允许显示器休眠（省电）
        self.caffeinate_proc = subprocess.Popen(
            ['caffeinate', '-i', 'tail', '-f', '/dev/null'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self._active = True
        self.echo("✓ macOS: System sleep prevented, display may sleep")

    def _stop_mac(self):
        """停止macOS防休眠"""
        if self.caffeinate_proc:
            self.caffeinate_proc.terminate()
            self.caffeinate_proc.wait()
            self.caffeinate_proc = None
            self._active = False
            self.echo("✓ macOS: Power management restored")

    def _start_windows(self):
        """Windows: 防止系统休眠，允许显示器休眠"""
        try:
            import ctypes
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            # 不使用 ES_DISPLAY_REQUIRED: 允许显示器休眠
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001

            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            )
            self._active = True
            self.echo("✓ Windows: System sleep prevented, display may sleep")
        except Exception as e:
            self.logger.error(f"Failed to set Windows power state: {e}")

    def _stop_windows(self):
        """停止Windows防休眠"""
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            # 恢复默认行为
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            self._active = False
            self.echo("✓ Windows: Power management restored")
        except Exception as e:
            self.logger.error(f"Failed to restore Windows power state: {e}")

    def __enter__(self):
        """支持 with 语句"""
        self.start_sync()
        return self

    def __exit__(self, *args):
        """退出 with 语句时自动停止"""
        self.stop_sync()
