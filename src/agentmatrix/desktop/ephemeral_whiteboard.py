"""
EphemeralWhiteboard — 纯内存、不落盘的临时 whiteboard。

挂在服务层（如 WikiMaintenanceService），通过 micro 参数隔离不同 MicroAgent 的数据。
用于 MicroAgent 暂存中间结果（如知识提取过程中的知识点列表和状态跟踪）。
"""

from typing import TYPE_CHECKING

from .whiteboard_base import WhiteboardBase

if TYPE_CHECKING:
    from ..core.micro_agent import MicroAgent


class EphemeralWhiteboard(WhiteboardBase):
    """纯内存临时 whiteboard，按 MicroAgent 隔离数据，不做文件 I/O。"""

    def __init__(self):
        # 用 micro.name 作 key —— service 内 worker 名唯一且稳定，
        # 比 id(micro) 更可读，也避免 GC 后地址复用导致的潜在 bug。
        self._per_micro: dict = {}  # {micro.name: sections dict}

    def clear(self):
        """清空所有 MicroAgent 的 whiteboard 数据。"""
        self._per_micro.clear()

    def cleanup(self, micro: "MicroAgent"):
        """清理指定 micro 的 whiteboard 数据（task 结束时调用）。"""
        self._per_micro.pop(micro.name, None)

    def _get_sections(self, micro: "MicroAgent") -> dict:
        key = micro.name
        if key not in self._per_micro:
            self._per_micro[key] = {}
        return self._per_micro[key]
