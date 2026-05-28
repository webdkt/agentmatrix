"""
Whiteboard Manager — 白板持久化、协同编辑、变更追踪

数据结构（sections 嵌套）:
{
  "sections": {
    "section_name": {
      "key": { "content": str, "last_modified": iso_str }
    }
  }
}
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_agent import BaseAgent
    from ..core.micro_agent import MicroAgent

# 匹配 <whiteboard>...</whiteboard> 块
_WHITEBOARD_RE = re.compile(r'\s*<whiteboard>.*?</whiteboard>', re.DOTALL)


class WhiteboardManager:
    """白板管理器：文件持久化 + 协同编辑 + 变更追踪。"""

    def __init__(self, agent: "BaseAgent"):
        self._agent = agent
        # {section: {key: {"content": str, "last_modified": datetime, "is_modified": bool}}}
        self._sections: dict = {}
        self._change_counter: int = 0
        self._change_threshold: int = 8
        self._file_path: Optional[Path] = None

    # ==================== 属性 ====================

    @property
    def data(self) -> dict:
        return self._sections

    @property
    def should_compress(self) -> bool:
        return self._change_counter >= self._change_threshold

    def reset_change_counter(self):
        self._change_counter = 0

    # ==================== 文件路径 ====================

    def set_file_path(self, path: Path):
        self._file_path = path
        self._sections = {}
        self._change_counter = 0
        self._load_initial()

    def _load_initial(self):
        if self._file_path is None:
            return
        if self._file_path.exists():
            self._read_file_into_memory()
        else:
            self._save_memory_to_file()

    # ==================== CRUD（由 action 调用）====================

    def handle_action(self, micro: "MicroAgent", section: str, key: str = "", content: str = "") -> str:
        """set_whiteboard action 的委托入口。

        - section + key + content → 设置条目
        - section + key + 空 content → 删除该 key
        - section + 无 key（或空 key）+ 无 content → 删除整个 section
        """
        now = datetime.now()

        if not section:
            return "Section 不能为空"

        # 删除整个 section
        if not key and not content:
            if section in self._sections:
                del self._sections[section]
                self._change_counter += 1
                self._save_memory_to_file()
                self._remove_old_whiteboard_block(micro)
                self._update_first_user_message(micro)
                return f"Deleted section '{section}'"
            return f"Section '{section}' not found"

        # 删除单个 key
        if not content:
            sec = self._sections.get(section)
            if sec and key in sec:
                del sec[key]
                if not sec:
                    del self._sections[section]
                self._change_counter += 1
                self._save_memory_to_file()
                self._remove_old_whiteboard_block(micro)
                self._update_first_user_message(micro)
                return f"Deleted '{section}.{key}'"
            return f"Key '{key}' not found in section '{section}'"

        # 设置/更新条目
        if section not in self._sections:
            self._sections[section] = {}
        self._sections[section][key] = {
            "content": content,
            "last_modified": now,
            "is_modified": True,
        }
        self._change_counter += 1
        self._save_memory_to_file()
        self._remove_old_whiteboard_block(micro)
        self._update_first_user_message(micro)

        return self.format_whiteboard_text()

    # ==================== 文件同步（think 前）====================

    def sync_from_file(self, micro: "MicroAgent"):
        if self._file_path is None:
            return
        if not self._file_path.exists():
            self._save_memory_to_file()
            return

        file_data = self._read_file_raw()
        if file_data is None:
            self._save_memory_to_file()
            return

        if file_data == self._serialize_data():
            return

        now = datetime.now()
        self._sections = {}
        for sec_name, entries in file_data.get("sections", {}).items():
            self._sections[sec_name] = {}
            for k, v in entries.items():
                self._sections[sec_name][k] = {
                    "content": v.get("content", ""),
                    "last_modified": now,
                    "is_modified": True,
                }

        self._change_counter += 1
        self._update_first_user_message(micro)

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

        wb_block = self.format_whiteboard_text()
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

    # ==================== 格式化输出 ====================

    def format_whiteboard_text(self) -> str:
        if not self._sections:
            return "<whiteboard>无内容</whiteboard>"

        now = datetime.now()
        all_dts = []
        for entries in self._sections.values():
            for v in entries.values():
                all_dts.append(v["last_modified"])
        latest_dt = max(all_dts)
        ts_str = latest_dt.strftime("%H:%M") if latest_dt.date() == now.date() else latest_dt.strftime("%Y-%m-%d")

        lines = [f"白板最后更新于：{ts_str}"]
        for sec_name, entries in self._sections.items():
            lines.append(f"\n## {sec_name}")
            for key, entry in entries.items():
                lines.append(f"{key}: {entry['content']}")

        return "<whiteboard>\n" + "\n".join(lines) + "\n</whiteboard>"

    # ==================== 兼容接口 ====================

    def data_as_legacy_format(self) -> dict:
        """返回扁平的 whiteboard dict（兼容 MicroAgent.whiteboard 属性）。"""
        result = {}
        for sec_name, entries in self._sections.items():
            for k, v in entries.items():
                result[f"{sec_name}.{k}"] = {"content": v["content"], "ts": v["last_modified"].timestamp()}
        return result

    # ==================== 文件 I/O ====================

    def _save_memory_to_file(self):
        if self._file_path is None:
            return
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        data = self._serialize_data()
        try:
            self._file_path.write_text(
                json.dumps({"sections": data}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            self._agent.logger.warning(f"Whiteboard save failed: {e}")

    def _serialize_data(self) -> dict:
        result = {}
        for sec_name, entries in self._sections.items():
            result[sec_name] = {}
            for k, v in entries.items():
                dt = v["last_modified"]
                result[sec_name][k] = {
                    "content": v["content"],
                    "last_modified": dt.isoformat() if isinstance(dt, datetime) else str(dt),
                }
        return result

    def _read_file_into_memory(self):
        raw = self._read_file_raw()
        if raw is None:
            return
        self._sections = {}
        for sec_name, entries in raw.get("sections", {}).items():
            self._sections[sec_name] = {}
            for k, v in entries.items():
                dt_str = v.get("last_modified", "")
                try:
                    dt = datetime.fromisoformat(dt_str)
                except (ValueError, TypeError):
                    dt = datetime.now()
                self._sections[sec_name][k] = {
                    "content": v.get("content", ""),
                    "last_modified": dt,
                    "is_modified": False,
                }

    def _read_file_raw(self) -> Optional[dict]:
        if not self._file_path or not self._file_path.exists():
            return None
        try:
            text = self._file_path.read_text(encoding="utf-8")
            return json.loads(text)
        except (json.JSONDecodeError, OSError) as e:
            self._agent.logger.warning(f"Whiteboard file read error: {e}")
            return None
