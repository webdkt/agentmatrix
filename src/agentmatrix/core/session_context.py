"""
Session Context - Session 状态管理对象

设计理念：
- 内部包装 dict 对象
- 自动处理持久化（根据 _persistent 标志）
- 通过对象引用传递，保持持久化能力
- 提供 get() 和 update() 接口
"""

from typing import Any, Optional


class SessionContext:
    """
    Session Context 对象

    特点：
    1. 内部包装 dict 对象（_data）
    2. 根据 _persistent 标志自动处理持久化
    3. 通过对象引用传递，共享持久化能力
    4. 提供 get() 和 update() 方法

    使用场景：
    - BaseAgent: persistent=True（可持久化）
    - MicroAgent 共享模式: 使用 parent 的 SessionContext（可持久化）
    - MicroAgent 独立模式: 创建新的 SessionContext(persistent=False)（不可持久化）
    """

    def __init__(
        self,
        persistent: bool = False,
        session_manager=None,
        session: Optional[dict] = None,
        initial_data: Optional[dict] = None
    ):
        """
        初始化 SessionContext

        Args:
            persistent: 是否可持久化（默认 False）
            session_manager: SessionManager 对象（用于持久化）
            session: session dict（包含 session_id, context 等）
            initial_data: 初始数据
        """
        self._data = initial_data.copy() if initial_data else {}
        self._persistent = persistent
        self._session_manager = session_manager
        self._session = session

    # ==========================================
    # 读取接口
    # ==========================================

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取值

        Args:
            key: 键
            default: 默认值

        Returns:
            值或默认值
        """
        return self._data.get(key, default)

    def to_dict(self) -> dict:
        """
        返回内部 dict 的副本

        Returns:
            dict: 内部数据的副本
        """
        return self._data.copy()

    # ==========================================
    # 更新和持久化
    # ==========================================

    async def update(self, **kwargs):
        """
        更新数据（可持久化时会自动持久化）

        Args:
            **kwargs: 要更新的键值对
        """
        # 1. 更新内存中的 dict
        self._data.update(kwargs)

        # 2. 如果可持久化，自动保存到磁盘
        if self._persistent and self._session_manager and self._session:
            # 同步 session["context"]
            self._session["context"] = self._data
            await self._session_manager.save_session_context_only(self._session)

    def clear(self):
        """清空数据"""
        self._data.clear()

    # ==========================================
    # 属性访问
    # ==========================================

    @property
    def persistent(self) -> bool:
        """是否可持久化"""
        return self._persistent

    def __repr__(self) -> str:
        """字符串表示"""
        persistent_str = "persistent" if self._persistent else "non-persistent"
        return f"<SessionContext({persistent_str}, {len(self._data)} keys)>"
