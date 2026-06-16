"""
EphemeralTodoManager — 纯内存、按 MicroAgent 隔离的 TodoManager dispatcher。

挂在服务层（如 WikiMaintenanceService），用于多 worker 并发场景下，
每个 MicroAgent 拥有独立的 todo 状态，互不污染。

与 EphemeralWhiteboard 平行：
- 每个 micro 第一次访问时懒创建一个 TodoManager（无 file_path，纯内存）
- task 结束时 service worker 调 cleanup(micro) 清理对应状态
"""

from typing import TYPE_CHECKING

from .todo_manager import TodoManager

if TYPE_CHECKING:
    from ..core.micro_agent import MicroAgent


class EphemeralTodoManager:
    """按 MicroAgent 隔离的内存版 TodoManager。"""

    def __init__(self, agent):
        self._agent = agent
        # 用 micro.name 作 key —— service 内 worker 名唯一且稳定，
        # 比 id(micro) 更可读，也避免 GC 后地址复用导致的潜在 bug。
        self._per_micro: dict = {}  # micro.name -> TodoManager

    def _get(self, micro: "MicroAgent") -> TodoManager:
        key = micro.name
        if key not in self._per_micro:
            self._per_micro[key] = TodoManager(self._agent)
        return self._per_micro[key]

    def handle_action(self, micro: "MicroAgent", *args, **kwargs):
        """set_todo action 的委托入口 —— 按 micro 分发到独立 TodoManager。"""
        return self._get(micro).handle_action(micro, *args, **kwargs)

    def cleanup(self, micro: "MicroAgent"):
        """清理指定 micro 的 todo 状态（task 结束时调用）。"""
        self._per_micro.pop(micro.name, None)
