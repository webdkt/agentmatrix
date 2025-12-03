import sqlite3
import json
from datetime import datetime

class AgentDB:
    def __init__(self, db_path="agents.db"):
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
                metadata TEXT -- 存 JSON 格式的附件或其他信息
            )
        ''')
        self.conn.commit()

    def log_email(self, email):
        """记录每一封信"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO emails 
            (id, timestamp, sender, recipient, subject, body, in_reply_to, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            email.id,
            email.timestamp.isoformat(),
            email.sender,
            email.recipient,
            email.subject,
            email.body,
            email.in_reply_to,
            json.dumps({}) # metadata
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