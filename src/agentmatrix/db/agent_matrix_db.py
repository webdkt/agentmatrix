import sqlite3
import json
from datetime import datetime
from ..core.log_util import AutoLoggerMixin

class AgentMatrixDB(AutoLoggerMixin):
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # 1. 邮件归档表 (The Global Mailbox)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                body TEXT,
                in_reply_to TEXT,
                task_id TEXT,
                sender_session_id TEXT,
                receiver_session_id TEXT,
                metadata TEXT -- 存 JSON 格式的附件或其他信息
            )
        ''')
        self.conn.commit()

        # 创建索引
        self._create_indexes()

    def _create_indexes(self):
        """创建索引以提升查询性能"""
        cursor = self.conn.cursor()

        # sender_session_id 索引（查询发出的邮件）
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sender_session
            ON emails(sender_session_id, sender, task_id)
        ''')

        # receiver_session_id 索引（查询收到的邮件）
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_receiver_session
            ON emails(receiver_session_id, recipient, task_id)
        ''')

        # in_reply_to 索引（用于 reply_mapping 查询）
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_in_reply_to
            ON emails(in_reply_to)
        ''')

        self.conn.commit()

    def log_email(self, email):
        """记录每一封信"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO emails
            (id, timestamp, sender, recipient, subject, body, in_reply_to, task_id, sender_session_id, receiver_session_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            email.id,
            email.timestamp.isoformat(),
            email.sender,
            email.recipient,
            email.subject,
            email.body,
            email.in_reply_to,
            email.task_id,
            email.sender_session_id,
            email.receiver_session_id,
            json.dumps(email.metadata) if email.metadata else None
        ))
        self.conn.commit()

    def get_mailbox(self, agent_name, limit=50):
        """查询某个 Agent 的收件箱历史"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM emails
            WHERE recipient = ? OR sender = ?
            ORDER BY timestamp DESC LIMIT ?
        ''', (agent_name, agent_name, limit))
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_mails_by_range(self, agent_name, task_id, start=0, end=1):
        """查询某个Agent的指定日期范围的邮件
        Args:
            agent_name: Agent名称
            start: 起始索引（0表示最新邮件）
            end: 结束索引
        Returns:
            指定范围内的邮件列表
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM emails
            WHERE task_id = ? and (recipient = ? OR sender = ?)
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        ''', (task_id, agent_name, agent_name, end - start + 1, start))
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_user_session_emails(self, task_id, user_agent_name='User'):
        """查询某个用户会话中所有与User相关的邮件
        Args:
            task_id: 用户会话ID
            user_agent_name: User agent 的名称（默认 'User'，向后兼容）
        Returns:
            该会话中所有与User相关的邮件列表（按时间升序）
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM emails
            WHERE task_id = ? AND (sender = ? OR recipient = ?)
            ORDER BY timestamp ASC
        ''', (task_id, user_agent_name, user_agent_name))
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def update_receiver_session(self, email_id: str, receiver_session_id: str, receiver_name: str):
        """
        更新邮件的 receiver_session_id

        Args:
            email_id: 邮件ID
            receiver_session_id: 收件人的 session
            receiver_name: 收件人名称

        Raises:
            RuntimeError: 如果更新失败（邮件不存在或收件人不匹配）
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE emails
            SET receiver_session_id = ?
            WHERE id = ? AND recipient = ?
        ''', (receiver_session_id, email_id, receiver_name))

        if cursor.rowcount == 0:
            raise RuntimeError(
                f"Failed to update receiver_session_id: "
                f"email_id={email_id}, receiver={receiver_name}, "
                f"receiver_session_id={receiver_session_id}. "
                f"Email not found or recipient mismatch."
            )

        self.conn.commit()

    def get_emails_by_session(self, session_id: str, agent_name: str, task_id: str):
        """
        获取某个 session 的所有邮件（发出去的 + 收到的）

        单次 SQL 查询，无需递归！

        Args:
            session_id: 会话ID
            agent_name: Agent名称
            task_id: 用户会话ID

        Returns:
            该 session 的所有邮件列表（按时间升序）
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM emails
            WHERE task_id = ?
              AND (
                -- 发出去的邮件
                (sender_session_id = ? AND sender = ?)
                OR
                -- 收到的邮件
                (receiver_session_id = ? AND recipient = ?)
              )
            ORDER BY timestamp ASC
        ''', (task_id, session_id, agent_name, session_id, agent_name))

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
