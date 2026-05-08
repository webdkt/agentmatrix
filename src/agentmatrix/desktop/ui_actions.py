from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class UIActionMeta:
    """UI 可调用 action 的元数据。"""
    name: str                              # 唯一标识（如 "view_current_prompt"）
    label: str                             # 按钮文字（如 "System Prompt"）
    icon: Optional[str] = None             # MIcon 图标名
    tooltip: Optional[str] = None          # hover 提示
    placement: str = "floating"            # "floating" | "topbar"
    requires_idle: bool = False            # 是否要求 Agent IDLE
    display_mode: str = "text"             # "text" | "markdown" | "json" | "modal" | "toast"
    handler: Optional[Callable] = None     # bound method（扫描时填充）


def ui_action(
    name: str,
    label: str,
    icon: str = None,
    tooltip: str = None,
    placement: str = "floating",
    requires_idle: bool = False,
    display_mode: str = "text",
):
    """标记一个方法为前端 UI 可调用的 action。

    用法:
        @ui_action(name="view_prompt", label="System Prompt",
                   icon="file-text", display_mode="markdown")
        async def view_current_prompt(self):
            return self.last_system_prompt
    """
    def decorator(func):
        func._is_ui_action = True
        func._ui_action_meta = UIActionMeta(
            name=name, label=label, icon=icon, tooltip=tooltip,
            placement=placement, requires_idle=requires_idle,
            display_mode=display_mode,
        )
        return func
    return decorator
