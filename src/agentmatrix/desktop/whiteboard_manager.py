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
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .whiteboard_base import WhiteboardBase

if TYPE_CHECKING:
    from .base_agent import BaseAgent
    from ..core.micro_agent import MicroAgent


class WhiteboardManager(WhiteboardBase):
    """白板管理器：文件持久化 + 协同编辑 + 变更追踪。"""

    def __init__(self, agent: "BaseAgent"):
        self._agent = agent
        self._sections: dict = {}  # {section: {key: {content, last_modified, is_modified}}}
        self._change_counter: int = 0
        self._change_threshold: int = 8
        self._file_path: Optional[Path] = None

    # ==================== 基类实现 ====================

    def _get_sections(self, micro: "MicroAgent") -> dict:
        return self._sections

    def _on_mutate(self, micro: "MicroAgent"):
        self._change_counter += 1
        self._save_memory_to_file()

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
        self._sections.clear()
        self._change_counter = 0
        self._load_initial()

    def _load_initial(self):
        if self._file_path is None:
            return
        if self._file_path.exists():
            self._read_file_into_memory()
        else:
            self._save_memory_to_file()

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

        sections = self._get_sections(micro)
        file_sections = file_data.get("sections", {})
        if file_sections == self._serialize_data(sections):
            return

        now = datetime.now()
        sections.clear()
        for sec_name, entries in file_sections.items():
            sections[sec_name] = {}
            for k, v in entries.items():
                sections[sec_name][k] = {
                    "content": v.get("content", ""),
                    "last_modified": now,
                    "is_modified": True,
                }

        self._change_counter += 1
        self._update_first_user_message(micro)

    # ==================== 文件 I/O ====================

    def _save_memory_to_file(self):
        if self._file_path is None:
            return
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        data = self._serialize_data(self._sections)
        try:
            self._file_path.write_text(
                json.dumps({"sections": data}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            self._agent.logger.warning(f"Whiteboard save failed: {e}")

    @staticmethod
    def _serialize_data(sections: dict) -> dict:
        result = {}
        for sec_name, entries in sections.items():
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
        sections = {}
        for sec_name, entries in raw.get("sections", {}).items():
            sections[sec_name] = {}
            for k, v in entries.items():
                dt_str = v.get("last_modified", "")
                try:
                    dt = datetime.fromisoformat(dt_str)
                except (ValueError, TypeError):
                    dt = datetime.now()
                sections[sec_name][k] = {
                    "content": v.get("content", ""),
                    "last_modified": dt,
                    "is_modified": False,
                }
        self._sections = sections

    def _read_file_raw(self) -> Optional[dict]:
        if not self._file_path or not self._file_path.exists():
            return None
        try:
            text = self._file_path.read_text(encoding="utf-8")
            return json.loads(text)
        except (json.JSONDecodeError, OSError) as e:
            self._agent.logger.warning(f"Whiteboard file read error: {e}")
            return None


