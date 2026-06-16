"""
WhiteboardBase — Whiteboard 的公共基类。

封装 sections CRUD、消息注入、格式化等共享逻辑。
子类实现 _get_sections(micro) 和 _on_mutate(micro)。
"""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.micro_agent import MicroAgent

_WHITEBOARD_RE = re.compile(r'\s*<whiteboard>.*?</whiteboard>', re.DOTALL)


class WhiteboardBase(ABC):
    """Whiteboard 公共基类。"""

    @abstractmethod
    def _get_sections(self, micro: "MicroAgent") -> dict:
        """返回指定 MicroAgent 的 sections 字典。"""

    def _on_mutate(self, micro: "MicroAgent"):
        """数据变更后的钩子。默认无操作。"""

    # ==================== CRUD ====================

    def handle_action(self, micro: "MicroAgent", section: str, key: str = "", content: str = "") -> str:
        if not section:
            return "Section 不能为空"

        sections = self._get_sections(micro)
        now = datetime.now()

        # 删除整个 section
        if not key and not content:
            if section in sections:
                del sections[section]
                self._remove_old_whiteboard_block(micro)
                self._update_first_user_message(micro)
                self._on_mutate(micro)
                return self.format_whiteboard_text(micro)
            return f"Section '{section}' not found"

        # 删除单个 key
        if not content:
            sec = sections.get(section)
            if sec and key in sec:
                del sec[key]
                if not sec:
                    del sections[section]
                self._remove_old_whiteboard_block(micro)
                self._update_first_user_message(micro)
                self._on_mutate(micro)
                return self.format_whiteboard_text(micro)
            return f"Key '{key}' not found in section '{section}'"

        # 设置/更新条目
        if section not in sections:
            sections[section] = {}
        sections[section][key] = {
            "content": content,
            "last_modified": now,
            "is_modified": True,
        }
        self._remove_old_whiteboard_block(micro)
        self._update_first_user_message(micro)
        self._on_mutate(micro)

        return self.format_whiteboard_text(micro)

    # ==================== 消息注入 ====================

    def update_first_user_message(self, micro: "MicroAgent"):
        self._update_first_user_message(micro)

    def _update_first_user_message(self, micro: "MicroAgent"):
        first_user_idx = None
        for i, msg in enumerate(micro.messages):
            if msg["role"] == "user":
                first_user_idx = i
                break
        if first_user_idx is None:
            return

        wb_block = self.format_whiteboard_text(micro)
        content = micro.messages[first_user_idx]["content"]
        if isinstance(content, str):
            if "<whiteboard>" in content:
                content = _WHITEBOARD_RE.sub('', content).rstrip()
            content += "\n\n" + wb_block
            micro.messages[first_user_idx]["content"] = content

    def _remove_old_whiteboard_block(self, micro: "MicroAgent"):
        first_user_idx = None
        for i, msg in enumerate(micro.messages):
            if msg["role"] == "user":
                first_user_idx = i
                break
        for i, msg in enumerate(micro.messages):
            if msg["role"] != "user":
                continue
            if i == first_user_idx:
                continue
            c = msg["content"]
            if isinstance(c, str) and "<whiteboard>" in c:
                msg["content"] = _WHITEBOARD_RE.sub('', c).rstrip()

    # ==================== 格式化 ====================

    def format_whiteboard_text(self, micro: "MicroAgent") -> str:
        sections = self._get_sections(micro)
        if not sections:
            return "<whiteboard>无内容</whiteboard>"

        now = datetime.now()
        all_dts = []
        for entries in sections.values():
            for v in entries.values():
                all_dts.append(v["last_modified"])
        if not all_dts:
            return "<whiteboard>无内容</whiteboard>"
        latest_dt = max(all_dts)
        ts_str = latest_dt.strftime("%H:%M") if latest_dt.date() == now.date() else latest_dt.strftime("%Y-%m-%d")

        lines = [f"白板最后更新于：{ts_str}"]
        for sec_name, entries in sections.items():
            lines.append(f"\n## {sec_name}")
            for key, entry in entries.items():
                lines.append(f"{key}: {entry['content']}")

        return "<whiteboard>\n" + "\n".join(lines) + "\n</whiteboard>"
