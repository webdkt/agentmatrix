"""
Async wrapper for AgentMatrixDB

This module provides an async interface to the synchronous AgentMatrixDB,
using asyncio.to_thread to prevent blocking the event loop.
"""

import asyncio
from typing import Optional, Dict, List, Any
from .agent_matrix_db import AgentMatrixDB


class AsyncAgentMatrixDB:
    """
    异步包装器 - 将同步数据库操作移到线程池执行

    使用方式:
        db = AsyncAgentMatrixDB("/path/to/db")
        sessions = await db.get_user_sessions("User")
    """

    def __init__(self, db_path: str):
        self._db = AgentMatrixDB(db_path)

    # ===== Email 相关 =====

    async def log_email(self, email) -> None:
        """记录邮件（异步）"""
        await asyncio.to_thread(self._db.log_email, email)

    async def get_mailbox(self, agent_name: str, limit: int = 50) -> List[Dict]:
        """查询 Agent 收件箱（异步）"""
        return await asyncio.to_thread(self._db.get_mailbox, agent_name, limit)

    async def get_mails_by_range(
        self, agent_name: str, task_id: str, start: int = 0, end: int = 1
    ) -> List[Dict]:
        """查询指定范围邮件（异步）"""
        return await asyncio.to_thread(
            self._db.get_mails_by_range, agent_name, task_id, start, end
        )

    async def get_user_session_emails(
        self, task_id: str, user_agent_name: str = "User"
    ) -> List[Dict]:
        """查询用户会话邮件（异步）"""
        return await asyncio.to_thread(
            self._db.get_user_session_emails, task_id, user_agent_name
        )

    async def update_receiver_session(
        self, email_id: str, recipient_session_id: str, receiver_name: str
    ) -> None:
        """更新收件人 session（异步）"""
        await asyncio.to_thread(
            self._db.update_receiver_session,
            email_id,
            recipient_session_id,
            receiver_name,
        )

    async def get_emails_by_session(
        self, session_id: str, agent_name: str
    ) -> List[Dict]:
        """获取 session 邮件（异步）"""
        return await asyncio.to_thread(
            self._db.get_emails_by_session, session_id, agent_name
        )

    async def get_email_by_id(self, email_id: str) -> Optional[Dict]:
        """根据 ID 查询邮件（异步）"""
        return await asyncio.to_thread(self._db.get_email_by_id, email_id)

    # ===== External Email Map 相关 =====

    async def save_external_email_mapping(
        self,
        external_message_id: str,
        internal_email_id: str,
        agent_name: str = None,
        task_id: str = None,
        user_session_id: str = None,
        agent_session_id: str = None,
    ) -> None:
        """保存外部邮件映射（异步）"""
        await asyncio.to_thread(
            self._db.save_external_email_mapping,
            external_message_id,
            internal_email_id,
            agent_name,
            task_id,
            user_session_id,
            agent_session_id,
        )

    async def get_internal_email_id(self, external_message_id: str) -> Optional[str]:
        """通过外部 ID 查询内部 ID（异步）"""
        return await asyncio.to_thread(
            self._db.get_internal_email_id, external_message_id
        )

    async def get_mapping_by_external_id(
        self, external_message_id: str
    ) -> Optional[Dict]:
        """通过外部 ID 查询完整 mapping（异步）"""
        return await asyncio.to_thread(
            self._db.get_mapping_by_external_id, external_message_id
        )

    async def get_external_message_id(self, internal_email_id: str) -> Optional[str]:
        """通过内部 ID 查询外部 ID（异步）"""
        return await asyncio.to_thread(
            self._db.get_external_message_id, internal_email_id
        )

    # ===== User Sessions 相关 =====

    async def upsert_user_session(
        self, email, user_session_id: str, agent_name: str, is_read: int
    ) -> None:
        """更新/插入用户 session（异步）"""
        await asyncio.to_thread(
            self._db.upsert_user_session, email, user_session_id, agent_name, is_read
        )

    async def mark_session_as_read(self, user_session_id: str) -> None:
        """标记 session 已读（异步）"""
        await asyncio.to_thread(self._db.mark_session_as_read, user_session_id)

    async def get_user_sessions(
        self, user_agent_name: str, page: int = 1, per_page: int = 20
    ) -> Dict:
        """
        获取用户会话列表（异步）

        这是被高频调用的方法，异步化后不会阻塞事件循环
        """
        return await asyncio.to_thread(
            self._db.get_user_sessions, user_agent_name, page, per_page
        )

    # ===== Scheduled Tasks 相关 =====

    async def create_task(self, task_dict: Dict) -> None:
        """创建定时任务（异步）"""
        await asyncio.to_thread(self._db.create_task, task_dict)

    async def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务（异步）"""
        return await asyncio.to_thread(self._db.get_task, task_id)

    async def list_tasks(self, status: str = None, agent: str = None) -> List[Dict]:
        """列出任务（异步）"""
        return await asyncio.to_thread(self._db.list_tasks, status, agent)

    async def update_task(self, task_id: str, updates: Dict) -> None:
        """更新任务（异步）"""
        await asyncio.to_thread(self._db.update_task, task_id, updates)

    async def delete_task(self, task_id: str) -> None:
        """删除任务（异步）"""
        await asyncio.to_thread(self._db.delete_task, task_id)

    async def get_pending_tasks(self) -> List[Dict]:
        """获取待执行任务（异步）"""
        return await asyncio.to_thread(self._db.get_pending_tasks)

    async def mark_triggered(self, task_id: str) -> None:
        """标记任务已触发（异步）"""
        await asyncio.to_thread(self._db.mark_triggered, task_id)

    async def mark_failed(self, task_id: str, reason: str) -> None:
        """标记任务失败（异步）"""
        await asyncio.to_thread(self._db.mark_failed, task_id, reason)

    # ===== Agent Sessions =====

    async def get_agent_sessions(self, agent_name: str) -> List[Dict]:
        """获取 Agent 的 sessions（异步）"""
        return await asyncio.to_thread(self._db.get_agent_sessions, agent_name)
