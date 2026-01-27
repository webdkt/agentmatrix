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
from typing import Dict, Optional
from datetime import datetime
from ..core.log_util import AutoLoggerMixin


class SessionManager(AutoLoggerMixin):
    """
    Session 管理器

    管理 agent 的所有 session，提供透明化的加载/保存/查询功能
    """

    _log_from_attr = "name"

    def __init__(self, agent_name: str, workspace_root: Optional[str] = None):
        self.name = f"{agent_name}_SessionManager"
        self.agent_name = agent_name
        self.workspace_root = workspace_root

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

        # 创建空的 session 文件
        await self._save_session_to_disk(session)
        self.logger.debug(f"📄 Created new session file for {session['session_id'][:8]}")

        return session

    async def save_session(self, session: dict):
        """
        保存 session 到磁盘

        Args:
            session: session dict（包含元数据和 history）
        """
        await self._save_session_to_disk(session)

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
        return {
            "session_id": session_id,
            "original_sender": sender,
            "last_sender": None,
            "status": "RUNNING",
            "user_session_id": user_session_id,
            "created_at": now,
            "last_modified": now,
            "history": []
        }

    async def _load_session_from_disk(self, session_id: str, user_session_id: str) -> Optional[dict]:
        """
        从磁盘加载 session（lazy load，加载元数据+history）

        Args:
            session_id: session ID
            user_session_id: 用户会话 ID

        Returns:
            dict: session 对象（包含元数据和 history），如果文件不存在返回 None
        """
        if not self.workspace_root:
            return None

        session_file = Path(self.workspace_root) / user_session_id / "history" / self.agent_name / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            # 异步读取文件（包含元数据 + history）
            session_data = await asyncio.to_thread(
                lambda p=session_file: json.load(open(p, "r", encoding="utf-8"))
            )

            self.logger.info(f"✅ Loaded session {session_id[:8]} from disk ({len(session_data.get('history', []))} messages)")
            return session_data

        except Exception as e:
            self.logger.warning(f"Failed to load session {session_id[:8]} from disk: {e}")
            return None

    async def _save_session_to_disk(self, session: dict):
        """
        保存 session 到磁盘（包含元数据 + history）

        Args:
            session: session dict（包含元数据和 history）
        """
        if not self.workspace_root:
            return

        # 更新 last_modified
        session["last_modified"] = datetime.now().isoformat()

        session_file = Path(self.workspace_root) / session["user_session_id"] / "history" / self.agent_name / f"{session['session_id']}.json"

        # 确保目录存在
        session_file.parent.mkdir(parents=True, exist_ok=True)

        # 异步写入文件（元数据 + history 一起）
        await asyncio.to_thread(
            lambda p=session_file, s=session: json.dump(s, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        )

        self.logger.debug(f"💾 Saved session {session['session_id'][:8]}")

    async def _load_reply_mapping(self, user_session_id: str):
        """
        从磁盘加载 reply_mapping

        Args:
            user_session_id: 用户会话 ID
        """
        if not self.workspace_root:
            return

        mapping_file = Path(self.workspace_root) / user_session_id / "history" / self.agent_name / "reply_mapping.json"

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
        if not self.workspace_root:
            return

        mapping_file = Path(self.workspace_root) / user_session_id / "history" / self.agent_name / "reply_mapping.json"

        # 确保目录存在
        mapping_file.parent.mkdir(parents=True, exist_ok=True)

        # 异步写入
        await asyncio.to_thread(
            lambda p=mapping_file, m=self.reply_mappings[user_session_id]: json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        )

        self.logger.debug(f"💾 Saved reply_mapping for {user_session_id}")
