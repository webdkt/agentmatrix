"""
Todo Manager — 任务清单持久化、变更追踪

数据结构:
{
  "todos": {
    "index": { "item": str, "status": str }  # status: planned/working/canceled/done
  }
}
"""

import json
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_agent import BaseAgent
    from ..core.micro_agent import MicroAgent

# 匹配 <Todo List>...</Todo List> 块
_TODO_RE = re.compile(r'\s*<Todo List>.*?</Todo List>', re.DOTALL)
# 匹配 <system task reminder>...</system task reminder> 块
_TASK_REMINDER_RE = re.compile(r'\s*<system task reminder>.*?</system task reminder>', re.DOTALL)

_VALID_STATUSES = {"planned", "working", "canceled", "done"}
_VALID_MODES = {"replace", "insert_after", "insert_before"}


class TodoManager:
    """任务清单管理器：文件持久化 + 变更追踪。"""

    def __init__(self, agent: "BaseAgent"):
        self._agent = agent
        self._todos: dict = {}  # {index: {"item": str, "status": str}}
        self._change_counter: int = 0
        self._change_threshold: int = 8
        self._file_path: Optional[Path] = None

    # ==================== 属性 ====================

    @property
    def data(self) -> dict:
        return self._todos

    @property
    def should_compress(self) -> bool:
        return self._change_counter >= self._change_threshold

    def reset_change_counter(self):
        self._change_counter = 0

    # ==================== 文件路径 ====================

    def set_file_path(self, path: Path):
        self._file_path = path
        self._todos = {}
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

    def handle_action(self, micro: "MicroAgent", index: str = "", todo_str: str = "", status: str = "", mode: str = "replace") -> str:
        """set_todo action 的委托入口。

        - 全空 → 清空所有
        - index + 空 todo_str + 空 status → 删除该条目
        - index + todo_str + status → 根据 mode 操作：
            - replace: 直接设置/更新 index 处的条目
            - insert_before: 在 index 前插入新条目，后续条目 index 后移
            - insert_after: 在 index 后插入新条目，后续条目 index 后移
        """
        # 统一转为 str，允许 agent 传 int
        if index is not None:
            index = str(index)
        if status is not None:
            status = str(status)
        if mode is not None:
            mode = str(mode)

        # 规范化 index：提取数字部分（"1"→"1", "#1"→"1", "第3项"→"3", 1→"1"）
        if index:
            _digits = re.sub(r'\D', '', index)
            if _digits:
                index = str(int(_digits))  # 去除前导零："01"→"1"
            else:
                return f"Invalid index '{index}': no numeric part found. Index must contain a number."

        # 清空所有
        if not index and not todo_str and not status:
            if self._todos:
                self._todos = {}
                self._change_counter += 1
                self._save_memory_to_file()
                self._remove_old_todo_block(micro)
                self._update_first_user_message(micro)
                return "Cleared all todos"
            return "No todos to clear"

        # 删除单个条目（todo_str 为空即删除，忽略 status）
        # 注意：不立即 _renumber()，保持索引稳定以便同批次后续操作引用
        if not todo_str:
            if index in self._todos:
                del self._todos[index]
                self._change_counter += 1
                self._save_memory_to_file()
                self._remove_old_todo_block(micro)
                self._update_first_user_message(micro)
                return f"Deleted todo '{index}'"
            return f"Todo '{index}' not found"

        # 验证 status
        if not status:
            status = "planned"
        if status not in _VALID_STATUSES:
            return f"Invalid status '{status}'. Must be one of: {', '.join(sorted(_VALID_STATUSES))}"

        # 验证 mode
        if not mode:
            mode = "replace"
        if mode not in _VALID_MODES:
            return f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(_VALID_MODES))}"

        # 根据 mode 执行操作
        if mode == "replace":
            self._todos[index] = {"item": todo_str, "status": status}
        elif mode == "insert_before":
            self._insert(index, todo_str, status, before=True)
        elif mode == "insert_after":
            self._insert(index, todo_str, status, before=False)

        self._change_counter += 1
        self._save_memory_to_file()
        self._remove_old_todo_block(micro)
        self._update_first_user_message(micro)

        return self.format_todo_text()

    # ==================== 插入逻辑 ====================

    def _insert(self, index: str, todo_str: str, status: str, before: bool):
        """在指定位置前/后插入新条目，后续条目 index 递增。"""
        # 插入前先重编号，确保基于连续编号操作
        self._renumber()
        sorted_keys = sorted(self._todos.keys(), key=lambda x: (0, int(x)) if x.isdigit() else (1, x))
        target_num = int(index) if index.isdigit() else len(sorted_keys) + 1

        # 从最大 index 开始后移，避免覆盖
        if before:
            # insert_before: 目标位置及之后的条目都 +1
            shift_from = target_num
        else:
            # insert_after: 目标位置之后的条目 +1
            shift_from = target_num + 1

        # 从大到小移动
        for key in reversed(sorted_keys):
            num = int(key) if key.isdigit() else 0
            if num >= shift_from:
                self._todos[str(num + 1)] = self._todos[key]
                del self._todos[key]

        insert_at = target_num if before else target_num + 1
        self._todos[str(insert_at)] = {"item": todo_str, "status": status}

    def _renumber(self):
        """删除后重编号，使 index 连续。"""
        sorted_keys = sorted(self._todos.keys(), key=lambda x: (0, int(x)) if x.isdigit() else (1, x))
        new_todos = {}
        for i, key in enumerate(sorted_keys, 1):
            new_todos[str(i)] = self._todos[key]
        self._todos = new_todos

    # ==================== 状态更新（供 hook 调用）====================

    def set_status_by_index(self, index: str, status: str) -> bool:
        """按 index 更新 todo 状态，不改变 todo_str。返回是否成功。"""
        index = str(index)
        if index not in self._todos:
            return False
        if status not in _VALID_STATUSES:
            return False
        self._todos[index]["status"] = status
        self._change_counter += 1
        self._save_memory_to_file()
        return True

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

        serialized = self._serialize_data()
        file_serialized = {}
        for idx, val in file_data.get("todos", {}).items():
            file_serialized[idx] = {"item": val.get("item", ""), "status": val.get("status", "planned")}

        if file_serialized == serialized:
            return

        self._todos = file_serialized
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

        todo_block = self.format_todo_text()
        content = micro.messages[first_user_idx]["content"]
        if isinstance(content, str):
            if "<Todo List>" in content:
                content = _TODO_RE.sub('', content).rstrip()
            content += "\n\n" + todo_block
            micro.messages[first_user_idx]["content"] = content

    def _remove_old_todo_block(self, micro: "MicroAgent"):
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
            if isinstance(c, str) and "<Todo List>" in c:
                msg["content"] = _TODO_RE.sub('', c).rstrip()

    # ==================== Task Reminder（注入最后一条 user message）====================

    def update_task_reminder(self, micro: "MicroAgent"):
        """在有 working/planned 条目时，在最后一条 user message 注入 task reminder。"""
        self._remove_all_task_reminders(micro)

        working_items = []
        planned_items = []
        for idx in sorted(self._todos.keys(), key=lambda x: (0, int(x)) if x.isdigit() else (1, x)):
            entry = self._todos[idx]
            if entry["status"] == "working":
                working_items.append(entry["item"])
            elif entry["status"] == "planned":
                planned_items.append(entry["item"])

        if not working_items and not planned_items:
            return

        lines = []
        if working_items:
            lines.append(f"当前正在处理：{working_items[0]}")
        if planned_items:
            n = len(planned_items)
            hint = f"还有{n}项计划的Todo，下一项是{planned_items[0]}" if n > 0 else ""
            if hint:
                lines.append(hint)

        if not lines:
            return

        reminder = "<system task reminder>\n" + "\n".join(lines) + "\n</system task reminder>"

        # 注入到最后一条 user message
        last_user_idx = None
        for i in range(len(micro.messages) - 1, -1, -1):
            if micro.messages[i]["role"] == "user":
                last_user_idx = i
                break
        if last_user_idx is None:
            return

        content = micro.messages[last_user_idx]["content"]
        if isinstance(content, str):
            content += "\n\n" + reminder
            micro.messages[last_user_idx]["content"] = content

    def _remove_all_task_reminders(self, micro: "MicroAgent"):
        for msg in micro.messages:
            if msg["role"] != "user":
                continue
            c = msg["content"]
            if isinstance(c, str) and "<system task reminder>" in c:
                msg["content"] = _TASK_REMINDER_RE.sub('', c).rstrip()

    # ==================== 格式化输出 ====================

    def format_todo_text(self) -> str:
        if not self._todos:
            return "<Todo List>No Todo Defined</Todo List>"

        sorted_keys = sorted(self._todos.keys(), key=lambda x: (0, int(x)) if x.isdigit() else (1, x))
        lines = []
        for i, key in enumerate(sorted_keys, 1):
            entry = self._todos[key]
            lines.append(f"{i}. [{entry['status']}] {entry['item']}")

        return "<Todo List>\n" + "\n".join(lines) + "\n</Todo List>"

    # ==================== 文件 I/O ====================

    def _save_memory_to_file(self):
        if self._file_path is None:
            return
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        data = self._serialize_data()
        try:
            self._file_path.write_text(
                json.dumps({"todos": data}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            self._agent.logger.warning(f"Todo save failed: {e}")

    def _serialize_data(self) -> dict:
        sorted_keys = sorted(self._todos.keys(), key=lambda x: (0, int(x)) if x.isdigit() else (1, x))
        result = {}
        for i, key in enumerate(sorted_keys, 1):
            result[str(i)] = {"item": self._todos[key]["item"], "status": self._todos[key]["status"]}
        return result

    def _read_file_into_memory(self):
        raw = self._read_file_raw()
        if raw is None:
            return
        self._todos = {}
        for idx, val in raw.get("todos", {}).items():
            self._todos[idx] = {
                "item": val.get("item", ""),
                "status": val.get("status", "planned"),
            }

    def _read_file_raw(self) -> Optional[dict]:
        if not self._file_path or not self._file_path.exists():
            return None
        try:
            text = self._file_path.read_text(encoding="utf-8")
            return json.loads(text)
        except (json.JSONDecodeError, OSError) as e:
            self._agent.logger.warning(f"Todo file read error: {e}")
            return None
