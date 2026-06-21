"""
Desktop 层信号类型。

core/signals.py 定义 Signal 协议和内置信号，
core/message.py 的 Email 也实现了 Signal 协议，
这里定义 Desktop 特有的额外信号类型。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class DataSignal:
    """结构化数据信号 — 携带 type_name + dict data，遵循 Signal 协议。

    用于服务间通信（如 source_added），比 TextSignal 更适合携带结构化元数据。
    """
    type_name: str
    data: dict = field(default_factory=dict)
    _signal_id: Optional[str] = None

    @property
    def signal_type(self) -> str:
        return self.type_name

    @property
    def signal_id(self) -> Optional[str]:
        return self._signal_id

    def to_text(self) -> str:
        import json
        return json.dumps({"type": self.type_name, **self.data}, ensure_ascii=False)

    def log_detail(self) -> Dict[str, Any]:
        return {"signal_type": self.type_name, "data_keys": list(self.data.keys())}


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


@dataclass
class ScreenshotSignal:
    """设计预览截图信号 — 前端截预览 iframe 后回传，遵循 Signal 协议。

    截图落盘后只携带文件路径，由 LLM 在下一轮 think 通过 vision skill
    的 look(path) 查看图。这与本仓 vision 既定模式一致 —— 图片不进
    主对话历史，需要时单独调视觉模型。

    session_id 用于 BasicAgent._route_signal 的 session 解析。fire-and-forget。
    """
    file_path: str
    session_id: str
    selector: str = ""
    caption: str = ""
    _signal_id: Optional[str] = None

    @property
    def signal_type(self) -> str:
        return "screenshot"

    @property
    def signal_id(self) -> Optional[str]:
        return self._signal_id

    def to_text(self) -> str:
        sel = f"（selector={self.selector}）" if self.selector else ""
        cap = self.caption or "已截取当前预览"
        return (
            f"[预览截图{sel}] {cap}\n"
            f"截图保存在 {self.file_path}。用 look(\"{self.file_path}\") 查看它来核对布局。"
        )

    def log_detail(self) -> Dict[str, Any]:
        return {
            "signal_type": "screenshot",
            "file_path": self.file_path,
            "selector": self.selector,
        }
