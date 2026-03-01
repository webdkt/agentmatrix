"""
Session Manager - 管理 agent 的 session 状态和持久化

职责：
1. 内存缓存管理
2. 磁盘加载/保存（lazy load）
3. reply_mapping 管理
4. 自动持久化
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING
from datetime import datetime
from ..core.log_util import AutoLoggerMixin
import logging

if TYPE_CHECKING:
    from ..core.log_config import LogConfig


class SessionManager(AutoLoggerMixin):
    """
    Session 管理器

    管理 agent 的所有 session，提供透明化的加载/保存/查询功能
    """

    _log_from_attr = "name"

    def __init__(self, agent_name: str, workspace_root: Optional[str] = None,
                 matrix_path: Optional[str] = None,
                 parent_logger: Optional[logging.Logger] = None,
                 log_config: Optional['LogConfig'] = None):
        """
        初始化 SessionManager

        Args:
            agent_name: 所属Agent的名称
            workspace_root: 工作区根路径
            matrix_path: matrix 根路径（用于状态目录）
            parent_logger: 父组件的logger（可选，用于共享日志）
            log_config: 日志配置（可选）
        """
        self.name = f"{agent_name}_SessionManager"
        self.agent_name = agent_name
        self.workspace_root = workspace_root
        self.matrix_path = matrix_path

        # 可选：使用父 logger（如果不提供则创建独立日志文件）
        if parent_logger and log_config:
            self._parent_logger = parent_logger
            self._log_config = log_config
            self._log_prefix_template = log_config.prefix if log_config else ""

        # 内存缓存
        self.sessions: Dict[str, dict] = {}  # session_id → session dict

        # reply_mapping（按 user_session_id 分组）
        self.reply_mappings: Dict[str, Dict[str, str]] = {}  # user_session_id → {msg_id: session_id}

    async def get_session(self, email) -> dict:
        """
        根据 email 获取或创建 session（主要接口）

        Args:
            email: Email 对象

        Returns:
            dict: session 对象（包含元数据和 history）
        """
        # Case A: Reply（恢复已存在的 session）
        if hasattr(email, 'in_reply_to') and email.in_reply_to:
            user_session_id = getattr(email, 'user_session_id', 'default')

            # 确保该 user_session 的 reply_mapping 已加载
            if user_session_id not in self.reply_mappings:
                await self._load_reply_mapping(user_session_id)

            reply_mapping = self.reply_mappings[user_session_id]

            if email.in_reply_to in reply_mapping:
                session_id = reply_mapping.pop(email.in_reply_to)

                # 1. 先查内存
                if session_id in self.sessions:
                    session = self.sessions[session_id]
                    self.logger.debug(f"📨 Resumed existing session {session['session_id'][:8]} from memory")
                    return session

                # 2. 内存没有，尝试从磁盘加载（lazy load）
                self.logger.info(f"🔄 Session {session_id[:8]} not in memory, loading from disk...")
                session = await self._load_session_from_disk(session_id, user_session_id)
                if session:
                    self.sessions[session_id] = session
                    return session

                # 3. 磁盘也没有，创建新的
                self.logger.warning(f"⚠️ Session {session_id[:8]} not found on disk, creating new session")
                session = await self._create_new_session(session_id, email.sender, user_session_id)
                self.sessions[session_id] = session
                await self._save_session_to_disk(session)
                return session

        # Case B: New Task（创建新 session）
        user_session_id = getattr(email, 'user_session_id', 'default')
        session = await self._create_new_session(email.id, email.sender, user_session_id)
        self.sessions[email.id] = session

        # 🔑 关键修复：将 User 的邮件 ID 也加入 reply_mapping
        # 这样 User 可以 reply 自己的邮件（在 Agent 回复之前连续发送多封邮件）
        await self.update_reply_mapping(
            msg_id=email.id,
            session_id=session['session_id'],
            user_session_id=user_session_id
        )
        self.logger.debug(f"📄 Created new session {session['session_id'][:8]} and added email {email.id[:8]} to reply_mapping")

        # 创建空的 session 文件
        await self._save_session_to_disk(session)

        return session

    async def save_session(self, session: dict):
        """
        保存 session 到磁盘（保存 history 和 context）

        Args:
            session: session dict（包含元数据和 history）
        """
        await self._save_session_to_disk(session)

    async def save_session_context_only(self, session: dict):
        """
        只保存 session 的 context 到磁盘（不保存 history）

        用于频繁更新 context 而不需要更新 history 的场景

        Args:
            session: session dict
        """
        await self._save_session_context(session)

    async def update_reply_mapping(self, msg_id: str, session_id: str, user_session_id: str):
        """
        更新 reply_mapping（由 BaseAgent.send_email 调用）

        Args:
            msg_id: 发送的邮件 ID
            session_id: 当前 session ID
            user_session_id: 用户会话 ID
        """
        # 确保该 user_session 的 reply_mapping 已加载
        if user_session_id not in self.reply_mappings:
            self.reply_mappings[user_session_id] = {}

        # 更新映射
        self.reply_mappings[user_session_id][msg_id] = session_id

        # 自动保存到磁盘
        await self._save_reply_mapping(user_session_id)

    async def _create_new_session(self, session_id: str, sender: str, user_session_id: str) -> dict:
        """
        创建新的 session dict

        Args:
            session_id: session ID
            sender: 发送者
            user_session_id: 用户会话 ID

        Returns:
            dict: 新创建的 session 对象
        """
        now = datetime.now().isoformat()
        session = {
            "session_id": session_id,
            "original_sender": sender,
            "last_sender": None,
            "status": "RUNNING",
            "user_session_id": user_session_id,
            "created_at": now,
            "last_modified": now,
            "history": [],
            "context": {}  # Session级别的变量存储
        }

        # 创建 session 目录并保存初始文件
        await self._save_session_history(session)
        await self._save_session_context(session)

        return session

    async def _load_session_from_disk(self, session_id: str, user_session_id: str) -> Optional[dict]:
        """
        从磁盘加载 session（lazy load，分别加载 history 和 context）

        Args:
            session_id: session ID
            user_session_id: 用户会话 ID

        Returns:
            dict: session 对象（包含元数据、history 和 context），如果文件不存在返回 None
        """
        if not self.matrix_path:
            return None

        session_dir = Path(self.matrix_path) / ".matrix" / user_session_id / "history" / self.agent_name / session_id
        history_file = session_dir / "history.json"
        context_file = session_dir / "context.json"

        if not history_file.exists():
            return None

        try:
            # 加载 history.json（包含元数据 + history）
            session_data = await asyncio.to_thread(
                lambda p=history_file: json.load(open(p, "r", encoding="utf-8"))
            )

            # 加载 context.json（如果存在）
            if context_file.exists():
                context_data = await asyncio.to_thread(
                    lambda p=context_file: json.load(open(p, "r", encoding="utf-8"))
                )
                session_data["context"] = context_data
            else:
                session_data["context"] = {}

            self.logger.info(f"✅ Loaded session {session_id[:8]} from disk ({len(session_data.get('history', []))} messages)")
            return session_data

        except Exception as e:
            self.logger.warning(f"Failed to load session {session_id[:8]} from disk: {e}")
            return None

    async def _save_session_to_disk(self, session: dict):
        """
        保存 session 到磁盘（包含元数据 + history + context）

        注意：此方法保留用于向后兼容，实际上会分别调用 _save_session_history 和 _save_session_context

        Args:
            session: session dict
        """
        await self._save_session_history(session)
        await self._save_session_context(session)

    async def _save_session_history(self, session: dict):
        """
        保存 session 的 history 和元数据到磁盘（不包含 context）

        使用原子写入防止中断时文件损坏

        Args:
            session: session dict（包含元数据和 history）
        """
        if not self.matrix_path:
            return

        # 更新 last_modified
        session["last_modified"] = datetime.now().isoformat()

        session_dir = Path(self.matrix_path) / ".matrix" / session["user_session_id"] / "history" / self.agent_name / session['session_id']
        history_file = session_dir / "history.json"

        # 确保 session 目录存在
        session_dir.mkdir(parents=True, exist_ok=True)

        # 准备保存的数据（不包含 context）
        history_data = {
            "session_id": session["session_id"],
            "original_sender": session["original_sender"],
            "last_sender": session.get("last_sender"),
            "status": session.get("status", "RUNNING"),
            "user_session_id": session["user_session_id"],
            "created_at": session["created_at"],
            "last_modified": session["last_modified"],
            "history": session["history"]
        }

        # 原子写入：先写入临时文件，然后重命名
        def atomic_write(file_path, data):
            import tempfile
            import shutil

            # 1. 写入临时文件
            temp_fd, temp_path = tempfile.mkstemp(
                dir=str(file_path.parent),
                prefix=".tmp_",
                suffix=".json"
            )
            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                # 2. 原子重命名（OS 保证原子性）
                shutil.move(temp_path, str(file_path))
            except Exception as e:
                # 清理临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise e

        # 异步执行原子写入
        import os
        await asyncio.to_thread(atomic_write, history_file, history_data)

        self.logger.debug(f"💾 Saved session history {session['session_id'][:8]} (atomic)")

    async def _save_session_context(self, session: dict):
        """
        保存 session 的 context 到磁盘（不包含 history）

        Args:
            session: session dict
        """
        if not self.matrix_path:
            return

        session_dir = Path(self.matrix_path) / ".matrix" / session["user_session_id"] / "history" / self.agent_name / session['session_id']
        context_file = session_dir / "context.json"

        # 确保 session 目录存在
        session_dir.mkdir(parents=True, exist_ok=True)

        # 异步写入 context.json
        await asyncio.to_thread(
            lambda p=context_file, c=session.get("context", {}): json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        )

        self.logger.debug(f"💾 Saved session context {session['session_id'][:8]}")

    async def _load_reply_mapping(self, user_session_id: str):
        """
        从磁盘加载 reply_mapping

        Args:
            user_session_id: 用户会话 ID
        """
        if not self.matrix_path:
            return

        mapping_file = Path(self.matrix_path) / ".matrix" / user_session_id / "history" / self.agent_name / "reply_mapping.json"

        if not mapping_file.exists():
            self.reply_mappings[user_session_id] = {}
            return

        try:
            self.reply_mappings[user_session_id] = await asyncio.to_thread(
                lambda p=mapping_file: json.load(open(p, "r", encoding="utf-8"))
            )
            self.logger.info(f"✅ Loaded reply_mapping for {user_session_id} ({len(self.reply_mappings[user_session_id])} entries)")
        except Exception as e:
            self.logger.warning(f"Failed to load reply_mapping: {e}")
            self.reply_mappings[user_session_id] = {}

    async def _save_reply_mapping(self, user_session_id: str):
        """
        保存 reply_mapping 到磁盘

        Args:
            user_session_id: 用户会话 ID
        """
        if not self.matrix_path:
            return

        mapping_file = Path(self.matrix_path) / ".matrix" / user_session_id / "history" / self.agent_name / "reply_mapping.json"

        # 确保目录存在
        mapping_file.parent.mkdir(parents=True, exist_ok=True)

        # 异步写入
        await asyncio.to_thread(
            lambda p=mapping_file, m=self.reply_mappings[user_session_id]: json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        )

        self.logger.debug(f"💾 Saved reply_mapping for {user_session_id}")
