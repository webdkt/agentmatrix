"""
Signal — AgentCore 循环中所有 input 的统一接口。

Core 处理的一切 input 都是 signal：外部消息、action 结果、内部提示。
每个 signal 自己知道怎么变成 text（给 LLM 消费）和怎么 log（给 Shell 持久化）。

可靠投递机制：
- 外部 signal 有 signal_id，表示需要 at-least-once 保证
- Core think 完成后，将已处理的 signal_id 通知 Shell
- Shell 决定如何 mark processed
- 内部 signal（action 结果等）没有 signal_id，不需要确认

应用层可以定义自己的 Signal 类型（EmailSignal、ChatSignal 等），
只要实现 Signal 协议，Core 就能处理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ── 接口 ──────────────────────────────────────────────────

@runtime_checkable
class Signal(Protocol):
    """
    AgentCore 消费的一切 input 的统一接口。
    """

    @property
    def signal_type(self) -> str:
        """信号类型标识（用于日志）"""
        ...

    @property
    def signal_id(self) -> Optional[str]:
        """
        可靠投递标识。

        有 id：Core think 完成后通知 Shell mark processed。
        无 id（返回 None）：fire-and-forget。
        """
        ...

    def to_text(self) -> str:
        """生成给 LLM 消费的纯文本"""
        ...

    def log_detail(self) -> Dict[str, Any]:
        """返回结构化的日志信息"""
        ...


# ── Core 内置 Signal ──────────────────────────────────────

@dataclass
class TextSignal:
    """
    纯文本信号 — 通用 signal。

    用于 Core 内部提示（reflect、continue），
    应用层也可以直接用它快速构造 signal。
    """
    text: str
    type_name: str = "text"
    _signal_id: Optional[str] = None

    @property
    def signal_type(self) -> str:
        return self.type_name

    @property
    def signal_id(self) -> Optional[str]:
        return self._signal_id

    def to_text(self) -> str:
        return self.text

    def log_detail(self) -> Dict[str, Any]:
        return {"signal_type": self.type_name}


@dataclass
class ActionResultSignal:
    """
    Action 执行完成信号。

    Core 内部产生，不需要可靠投递确认（signal_id 为 None）。
    """
    results: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def signal_type(self) -> str:
        return "actions_completed"

    @property
    def signal_id(self) -> Optional[str]:
        return None

    def to_text(self) -> str:
        lines = []
        for r in self.results:
            label = r.get("label", "")
            display_name = f"{r['action_name']}: {label}" if label else r["action_name"]

            if r["status"] == "ok":
                lines.append(f"[{display_name} Done]: {r['result']}")
            elif r["status"] == "canceled":
                lines.append(f"[{display_name} Canceled]")
            else:
                lines.append(f"[{display_name} Failed]: {r.get('error', '')}")
        return "\n\n".join(lines)

    def log_detail(self) -> Dict[str, Any]:
        return {
            "signal_type": "actions_completed",
            "result_count": len(self.results),
            "action_names": [r.get("action_name", "") for r in self.results],
        }
