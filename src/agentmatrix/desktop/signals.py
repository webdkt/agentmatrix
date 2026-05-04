"""
Desktop 层信号类型。

core/signals.py 定义 Signal 协议和内置信号，
core/message.py 的 Email 也实现了 Signal 协议，
这里定义 Desktop 特有的额外信号类型。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class BrowserSignal:
    """浏览器事件信号 — 前端 UI 交互产生，遵循 Signal 协议。"""
    agent_name: str
    agent_session_id: str
    event_type: str
    url: str = ""
    title: str = ""
    data: dict = field(default_factory=dict)
    cdp_session_id: str = ""
    target_id: str = ""

    @property
    def signal_type(self) -> str:
        return "browser_event"

    @property
    def signal_id(self) -> Optional[str]:
        # 浏览器事件 fire-and-forget
        return None

    def to_text(self) -> str:
        lines = [f"[浏览器事件] {self.event_type}"]
        if self.target_id:
            lines.append(f"  tab: {self.target_id}")
        if self.url:
            display_url = self.url[:80] + "..." if len(self.url) > 80 else self.url
            lines.append(f"  页面: {display_url}")
        if self.title:
            lines.append(f"  标题: {self.title}")
        for k, v in self.data.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def log_detail(self) -> Dict[str, Any]:
        return {
            "signal_type": "browser_event",
            "agent_name": self.agent_name,
            "event_type": self.event_type,
        }
