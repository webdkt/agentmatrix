import asyncio
from typing import Dict, Optional
from ..db.agent_matrix_db import AgentMatrixDB
import os
import json
import textwrap
from pathlib import Path
from datetime import datetime
from ..core.message import Email
from ..core.log_util import AutoLoggerMixin


class PostOffice(AutoLoggerMixin):
    def __init__(self, paths, user_agent_name: str = "User"):
        self.paths = paths

        self.directory = {}
        self.queue = asyncio.Queue()
        email_db_path = str(self.paths.database_path)
        self.email_db = AgentMatrixDB(email_db_path)
        self._paused = False

        # Store user agent name
        self.user_agent_name = user_agent_name

        # Email sent hook list
        self.on_email_sent = []

    async def init_db(self):
        """Initialize the async database connection. Must be called after construction."""
        await self.email_db.connect()

    def register(self, agent):
        self.directory[agent.name] = agent
        agent.post_office = self

    def unregister(self, agent):
        del self.directory[agent.name]

    def yellow_page(self):
        yellow_page = ""
        for name, agent in self.directory.items():
            description = textwrap.indent(agent.description, "  ")
            yellow_page += f"- {name}: \n"
            yellow_page += f"{description} \n"
        return yellow_page

    def yellow_page_exclude_me(self, myname):
        yellow_page = ""
        for name, agent in self.directory.items():
            if name == myname:
                continue
            description = textwrap.indent(agent.description, "  ")
            yellow_page += f"- {name}: \n"
            yellow_page += f"{description} \n"
        return yellow_page

    def get_contact_list(self, exclude=None):
        contact_list = []
        for name, agent in self.directory.items():
            if name == exclude:
                continue
            contact_list.append(name)
        return contact_list

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    async def close(self):
        """关闭 PostOffice，释放资源"""
        await self.email_db.close()
        self.logger.info("PostOffice DB connection closed.")

    async def dispatch(self, email):
        await self.email_db.log_email(email)
        self.logger.debug(f"Sending email from {email.sender} to {email.recipient} ")
        await self.queue.put(email)
        self.logger.debug("Mail delivered")

        # Trigger email sent hooks
        for callback in self.on_email_sent:
            try:
                await callback(email)
            except Exception as e:
                self.logger.error(f"Email sent hook error: {e}", exc_info=True)

    async def run(self):
        self.logger.info("[PostOffice] Service Started")
        try:
            while True:
                if not self._paused:
                    email = await self.queue.get()
                    if email.recipient in self.directory:
                        target = self.directory[email.recipient]
                        await self.email_db.mark_email_delivered(email.id)
                        await target.inbox.put(email)
                    else:
                        self.logger.warning(f"Dropped mail to {email.recipient}")
                    self.queue.task_done()
                else:
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self.logger.info("[PostOffice] Service Stopped")
            raise  # Re-raise to properly propagate cancellation

    async def get_mails_by_range(self, task_id, agent_name, start=0, end=1):
        """查询某个Agent的指定Range的邮件
        Args:
            agent_name: Agent名称
            start: 起始索引（0表示最新邮件）
            end: 结束索引
        Returns:
            指定范围内的邮件列表
        """
        email_records = await self.email_db.get_mails_by_range(
            task_id, agent_name, start, end
        )
        emails = []
        for record in email_records:
            metadata = {}
            if record.get("metadata"):
                try:
                    metadata = json.loads(record["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            email = Email(
                id=record["id"],
                timestamp=datetime.fromisoformat(record["timestamp"]),
                sender=record["sender"],
                recipient=record["recipient"],
                subject=record["subject"],
                body=record["body"],
                in_reply_to=record["in_reply_to"],
                task_id=record.get("task_id", None),
                sender_session_id=record.get("sender_session_id"),
                recipient_session_id=record.get("recipient_session_id"),
                metadata=metadata,
            )
            emails.append(email)
        return emails

    async def update_email_receiver_session(
        self, email_id: str, recipient_session_id: str, receiver_name: str
    ):
        """
        更新邮件的 recipient_session_id（由收件人调用）

        Args:
            email_id: 邮件ID
            recipient_session_id: 收件人的 session
            receiver_name: 收件人名称

        Raises:
            RuntimeError: 如果更新失败
        """
        await self.email_db.update_receiver_session(
            email_id,
            recipient_session_id,
            receiver_name,
        )

    async def get_emails_by_session(self, session_id: str, agent_name: str):
        """
        获取某个 session 的所有邮件（发出去的 + 收到的）

        Args:
            session_id: 会话ID
            agent_name: Agent名称

        Returns:
            Email对象列表
        """
        email_records = await self.email_db.get_emails_by_session(session_id, agent_name)
        emails = []
        for record in email_records:
            metadata = {}
            if record.get("metadata"):
                try:
                    metadata = json.loads(record["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            email = Email(
                id=record["id"],
                timestamp=datetime.fromisoformat(record["timestamp"]),
                sender=record["sender"],
                recipient=record["recipient"],
                subject=record["subject"],
                body=record["body"],
                in_reply_to=record["in_reply_to"],
                task_id=record.get("task_id"),
                sender_session_id=record.get("sender_session_id"),
                recipient_session_id=record.get("recipient_session_id"),
                metadata=metadata,
            )
            emails.append(email)
        return emails

    async def get_session_emails_for_user(self, session_id):
        """获取某个用户会话中所有与User相关的邮件
        Args:
            session_id: 会话ID
        Returns:
            Email对象列表，每个Email包含额外的 is_from_user 布尔字段
        """
        email_records = await self.email_db.get_emails_by_session(
            session_id, self.user_agent_name
        )
        emails = []
        for record in email_records:
            metadata = {}
            if record.get("metadata"):
                try:
                    metadata = json.loads(record["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            email = Email(
                id=record["id"],
                timestamp=datetime.fromisoformat(record["timestamp"]),
                sender=record["sender"],
                recipient=record["recipient"],
                subject=record["subject"],
                body=record["body"],
                in_reply_to=record["in_reply_to"],
                task_id=record.get("task_id", None),
                sender_session_id=record.get("sender_session_id"),
                recipient_session_id=record.get("recipient_session_id"),
                metadata=metadata,
            )
            email.is_from_user = email.sender == self.user_agent_name
            emails.append(email)
        return emails
