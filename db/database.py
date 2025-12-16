import sqlite3
import json
from datetime import datetime
from core.log_util import AutoLoggerMixin

class AgentMailDB(AutoLoggerMixin):
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
                user_session_id TEXT,
                metadata TEXT -- 存 JSON 格式的附件或其他信息
            )
        ''')
        self.conn.commit()

    def log_email(self, email):
        """记录每一封信"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO emails 
            (id, timestamp, sender, recipient, subject, body, in_reply_to,user_session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            email.id,
            email.timestamp.isoformat(),
            email.sender,
            email.recipient,
            email.subject,
            email.body,
            email.in_reply_to,
            email.user_session_id
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

    def get_mails_by_range(self, agent_name, user_session_id, start=0, end=1):
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
            WHERE user_session_id = ? and (recipient = ? OR sender = ?)
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
        ''', (user_session_id, agent_name, agent_name, end - start + 1, start))
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
        

        
