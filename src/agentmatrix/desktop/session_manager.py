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
from ..core.id_generator import IDGenerator
from .paths import MatrixPaths
import logging

if TYPE_CHECKING:
    from ..core.log_config import LogConfig


class SessionManager(AutoLoggerMixin):
    """
    Session 管理器

    管理 agent 的所有 session，提供透明化的加载/保存/查询功能
    """

    _log_from_attr = "name"

    def __init__(self, agent_name: str, matrixpath: 'MatrixPaths',
                 parent_logger: Optional[logging.Logger] = None,
                 log_config: Optional['LogConfig'] = None,
                 db=None):
        """
        初始化 SessionManager

        Args:
            agent_name: 所属Agent的名称
            paths: MatrixPaths 对象，统一路径管理器
            parent_logger: 父组件的logger（可选，用于共享日志）
            log_config: 日志配置（可选）
            db: AgentMatrixDB 实例（共享连接，可选）
        """
        self.name = f"{agent_name}_SessionManager"
        self.agent_name = agent_name
        self.matrixpath = matrixpath
        self._db = db

        # 可选：使用父 logger（如果不提供则创建独立日志文件）
        if parent_logger and log_config:
            self._parent_logger = parent_logger
            self._log_config = log_config
            self._log_prefix_template = log_config.prefix if log_config else ""

        # 内存缓存
        self.sessions: Dict[str, dict] = {}  # session_id → session dict

        # email-to-session 缓存（替代 reply_mappings）
        self._email_session_cache: Dict[str, str] = {}  # email_id → session_id

    

    async def get_session_by_id(self, session_id: str) -> dict:
        """
        根据 session_id 获取 session（不创建新 session）

        Args:
            session_id: session ID

        Returns:
            dict: session 对象（包含元数据和 history）

        Raises:
            ValueError: 如果 session 不存在
        """
        # 1. 先查内存
        if session_id in self.sessions:
            return self.sessions[session_id]

        # 2. 从磁盘加载（需要知道 task_id）
        # 由于只有 session_id，我们需要遍历所有 task_id 来查找

        # 尝试直接从磁盘结构查找
        


        session_dir = self.matrixpath.get_agent_session_dir(self.agent_name, session_id)
        if session_dir.exists():
            session = await self._load_session_from_disk(session_id)
            if session:
                self.sessions[session_id] = session
                return session

        raise ValueError(f"Session {session_id[:8]} not found")

    async def get_session(self, email) -> dict:
        """
        根据 email 获取或创建 session（主要接口）

        Args:
            email: Email 对象

        Returns:
            dict: session 对象（包含元数据和 history），带 _is_new_session 标记
        """
        # Case A: Reply（恢复已存在的 session）
        if hasattr(email, 'in_reply_to') and email.in_reply_to:
            task_id = getattr(email, 'task_id', 'default')
            session_id = None

            # 1. 先查缓存
            if email.in_reply_to in self._email_session_cache:
                session_id = self._email_session_cache.pop(email.in_reply_to)
                self.logger.debug(f"📋 Found session {session_id[:8]} in cache")
            else:
                # 2. 查询数据库
                original_email = await self._get_email_from_db(email.in_reply_to)

                if original_email and original_email.get('sender_session_id'):
                    session_id = original_email['sender_session_id']
                    self.logger.debug(f"💾 Found session {session_id[:8]} in database")
                else:
                    self.logger.warning(f"⚠️ Cannot find session for email {email.in_reply_to[:8]}")

            # 3. 如果找到了 session_id，恢复 session
            if session_id:
                # 1. 先查内存
                if session_id in self.sessions:
                    session = self.sessions[session_id]
                    session['_is_new_session'] = False
                    self.logger.debug(f"📨 Resumed existing session {session['session_id'][:8]} from memory")
                    return session

                # 2. 内存没有，尝试从磁盘加载（lazy load）
                self.logger.info(f"🔄 Session {session_id[:8]} not in memory, loading from disk...")
                session = await self._load_session_from_disk(session_id)
                if session:
                    session['_is_new_session'] = False
                    self.sessions[session_id] = session
                    return session

                # 3. 磁盘也没有，创建新的
                self.logger.warning(f"⚠️ Session {session_id[:8]} not found on disk, creating new session")
                session = await self._create_new_session(session_id, email.sender, email.task_id)
                session['_is_new_session'] = True
                self.sessions[session_id] = session
                await self._save_session_to_disk(session)
                return session

        # Case B: New Task（创建新 session）
        task_id = getattr(email, 'task_id', 'default')
        # 传递None，让_create_new_session自动生成session_id
        session = await self._create_new_session(None, email.sender, task_id)
        session['_is_new_session'] = True
        self.sessions[session['session_id']] = session

        # 🔑 关键修复：将 User 的邮件 ID 也加入 reply_mapping
        # 这样 User 可以 reply 自己的邮件（在 Agent 回复之前连续发送多封邮件）
        await self.update_reply_mapping(
            msg_id=email.id,
            session_id=session['session_id'],
            task_id=task_id
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

    

    async def update_reply_mapping(self, msg_id: str, session_id: str, task_id: str):
        """
        更新 email-to-session 缓存（不再写磁盘）

        由 BaseAgent.send_email 调用

        Args:
            msg_id: 发送的邮件 ID
            session_id: 当前 session ID
            task_id: 用户会话 ID（此参数保留用于向后兼容，但不再使用）
        """
        self._email_session_cache[msg_id] = session_id
        self.logger.debug(f"📝 Cached email {msg_id[:8]} → session {session_id[:8]}")

    async def _create_new_session(self, session_id: Optional[str], sender: str, task_id: str) -> dict:
        """
        创建新的 session dict

        Args:
            session_id: session ID（如果为None，将自动生成）
            sender: 发送者
            task_id: 用户会话 ID

        Returns:
            dict: 新创建的 session 对象
        """
        # 🆕 如果没有提供session_id，直接使用 task_id
        # 这样 Agent 的 session_id 和 task_id 保持一致
        if not session_id:
            session_id = task_id
            self.logger.debug(f"🆕 Session ID = Task ID: {session_id[:20]}...")

        now = datetime.now().isoformat()
        session = {
            "session_id": session_id,
            "original_sender": sender,
            "last_sender": None,
            "status": "RUNNING",
            "task_id": task_id,
            "created_at": now,
            "last_modified": now,
            "history": [],
            "context": {}  # Session级别的变量存储
        }

        # 创建 session 目录并保存初始文件
        await self._save_session_history(session)


        return session

    async def _get_email_from_db(self, email_id: str) -> Optional[dict]:
        """
        从数据库获取邮件记录

        Args:
            email_id: 邮件ID

        Returns:
            dict: 邮件记录，如果不存在返回 None
        """
        if not self._db:
            self.logger.warning("No DB instance available for _get_email_from_db")
            return None
        try:
            return await self._db.get_email_by_id(email_id)
        except Exception as e:
            self.logger.warning(f"Failed to query email {email_id[:8]} from DB: {e}")
            return None

    async def _load_session_from_disk(self, session_id: str) -> Optional[dict]:
        """
        从磁盘加载 session（lazy load，分别加载 history 和 context）

        Args:
            session_id: session ID
            task_id: 用户会话 ID

        Returns:
            dict: session 对象（包含元数据、history 和 context），如果文件不存在返回 None
        """

        history_file = self.matrixpath.get_agent_session_history_dir(self.agent_name,session_id)
        #history_file = session_dir / "history.json"
        #context_file = session_dir / "context.json"

        if not history_file.exists():
            return None

        try:
            # 加载 history.json（包含元数据 + history）
            session_data = await asyncio.to_thread(
                lambda p=history_file: json.load(open(p, "r", encoding="utf-8"))
            )

            

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
        #await self._save_session_context(session)

    async def _save_session_history(self, session: dict):
        """
        保存 session 的 history 和元数据到磁盘（不包含 context）

        使用原子写入防止中断时文件损坏

        Args:
            session: session dict（包含元数据和 history）
        """

        # 更新 last_modified
        session["last_modified"] = datetime.now().isoformat()
        history_file = self.matrixpath.get_agent_session_history_dir(self.agent_name,session['session_id'])
        

        # 确保父目录存在（文件本身由后续写入创建）
        history_file.parent.mkdir(parents=True, exist_ok=True)

        # 准备保存的数据（不包含 context）
        history_data = {
            "session_id": session["session_id"],
            "original_sender": session["original_sender"],
            "last_sender": session.get("last_sender"),
            "status": session.get("status", "RUNNING"),
            "task_id": session["task_id"],
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


class AgentSessionStore:
    """
    SessionStore 的 Desktop 实现 — 包装 session dict + SessionManager。

    Core 通过 SessionStore 协议读写消息，不接触 session 结构和磁盘 I/O。
    """

    def __init__(self, session: dict, session_manager: SessionManager):
        self._session = session
        self._manager = session_manager

    def load_messages(self) -> list:
        return self._session.get("history", []).copy()

    async def save_messages(self, messages: list) -> None:
        self._session["history"] = messages
        await self._manager.save_session(self._session)

    
