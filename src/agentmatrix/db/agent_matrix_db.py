import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional
from ..core.log_util import AutoLoggerMixin


class AgentMatrixDB(AutoLoggerMixin):
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # 1. 邮件归档表 (The Global Mailbox)
        cursor.execute("""
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
                recipient_session_id TEXT,
                metadata TEXT -- 存 JSON 格式的附件或其他信息
            )
        """)

        # 2. 定时任务表 (Scheduled Tasks)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                target_agent TEXT NOT NULL,
                trigger_time TEXT NOT NULL,
                recurrence_rule TEXT,
                task_description TEXT,
                task_metadata TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_triggered_at TEXT,
                failure_reason TEXT
            )
        """)

        # 3. 外部邮件 Message-ID ↔ 内部 Email ID 映射表（enriched: 包含 session 全量信息）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_email_map (
                external_message_id TEXT PRIMARY KEY,
                internal_email_id TEXT NOT NULL,
                agent_name TEXT,
                task_id TEXT,
                user_session_id TEXT,
                agent_session_id TEXT
            )
        """)

        # 4. 用户会话表（session 元数据物化视图，每个 session 只保留最后一封邮件）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_session_id TEXT PRIMARY KEY,
                agent_name TEXT,
                is_read INTEGER NOT NULL DEFAULT 0,
                timestamp TEXT,
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                body TEXT,
                in_reply_to TEXT,
                task_id TEXT,
                sender_session_id TEXT,
                recipient_session_id TEXT,
                metadata TEXT
            )
        """)

        self.conn.commit()

        # 向后兼容：添加 delivered 列（旧数据库可能没有此列）
        try:
            cursor.execute("ALTER TABLE emails ADD COLUMN delivered INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass  # 列已存在

        self.conn.commit()

        # 创建索引
        self._create_indexes()

    def _create_indexes(self):
        """创建索引以提升查询性能"""
        cursor = self.conn.cursor()

        # sender_session_id 索引（查询发出的邮件）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sender_session
            ON emails(sender_session_id, sender, task_id)
        """)

        # recipient_session_id 索引（查询收到的邮件）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_receiver_session
            ON emails(recipient_session_id, recipient, task_id)
        """)

        # in_reply_to 索引（用于 reply_mapping 查询）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_in_reply_to
            ON emails(in_reply_to)
        """)

        # scheduled_tasks 表索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_status
            ON scheduled_tasks(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_trigger_time
            ON scheduled_tasks(trigger_time)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_next_trigger
            ON scheduled_tasks(status, trigger_time)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_target_agent
            ON scheduled_tasks(target_agent)
        """)

        # external_email_map 索引（反向查询：internal_email_id → external_message_id）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_external_map_internal
            ON external_email_map(internal_email_id)
        """)

        self.conn.commit()

    def log_email(self, email, delivered=True):
        """记录每一封信"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO emails
            (id, timestamp, sender, recipient, subject, body, in_reply_to, task_id, sender_session_id, recipient_session_id, metadata, delivered)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                email.id,
                email.timestamp.isoformat(),
                email.sender,
                email.recipient,
                email.subject,
                email.body,
                email.in_reply_to,
                email.task_id,
                email.sender_session_id,
                email.recipient_session_id,
                json.dumps(email.metadata) if email.metadata else None,
                1 if delivered else 0,
            ),
        )
        self.conn.commit()

    def mark_email_delivered(self, email_id: str):
        """标记邮件为已投递"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE emails SET delivered = 1 WHERE id = ?", (email_id,))
        self.conn.commit()

    def get_undelivered_emails(self, recipient: str = None):
        """获取未投递的邮件"""
        cursor = self.conn.cursor()
        if recipient:
            cursor.execute(
                "SELECT * FROM emails WHERE delivered = 0 AND recipient = ? ORDER BY timestamp ASC",
                (recipient,),
            )
        else:
            cursor.execute(
                "SELECT * FROM emails WHERE delivered = 0 ORDER BY timestamp ASC"
            )
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        result = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            row_dict.pop("delivered", None)
            result.append(row_dict)
        return result

    def get_mailbox(self, agent_name, limit=50):
        """查询某个 Agent 的收件箱历史"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM emails
            WHERE recipient = ? OR sender = ?
            ORDER BY timestamp DESC LIMIT ?
        """,
            (agent_name, agent_name, limit),
        )
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
        cursor.execute(
            """
            SELECT * FROM emails
            WHERE task_id = ? and (recipient = ? OR sender = ?)
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """,
            (task_id, agent_name, agent_name, end - start + 1, start),
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_user_session_emails(self, task_id, user_agent_name="User"):
        """查询某个用户会话中所有与User相关的邮件
        Args:
            task_id: 用户会话ID
            user_agent_name: User agent 的名称（默认 'User'，向后兼容）
        Returns:
            该会话中所有与User相关的邮件列表（按时间升序）
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM emails
            WHERE task_id = ? AND (sender = ? OR recipient = ?)
            ORDER BY timestamp ASC
        """,
            (task_id, user_agent_name, user_agent_name),
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def update_receiver_session(
        self, email_id: str, recipient_session_id: str, receiver_name: str
    ):
        """
        更新邮件的 recipient_session_id

        Args:
            email_id: 邮件ID
            recipient_session_id: 收件人的 session
            receiver_name: 收件人名称

        Raises:
            RuntimeError: 如果更新失败（邮件不存在或收件人不匹配）
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE emails
            SET recipient_session_id = ?
            WHERE id = ? AND recipient = ?
        """,
            (recipient_session_id, email_id, receiver_name),
        )

        if cursor.rowcount == 0:
            raise RuntimeError(
                f"Failed to update recipient_session_id: "
                f"email_id={email_id}, receiver={receiver_name}, "
                f"recipient_session_id={recipient_session_id}. "
                f"Email not found or recipient mismatch."
            )

        self.conn.commit()

    def get_emails_by_session(self, session_id: str, agent_name: str):
        """
        获取某个 session 的所有邮件（发出去的 + 收到的）

        单次 SQL 查询，无需递归！

        Args:
            session_id: 会话ID
            agent_name: Agent名称

        Returns:
            该 session 的所有邮件列表（按时间升序）
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM emails
            WHERE (
                -- 发出去的邮件（View A）
                (sender_session_id = ? AND sender = ?)
                OR
                -- 收到的邮件（View B）
                (recipient_session_id = ? AND recipient = ?)
            )
            ORDER BY timestamp ASC
        """,
            (session_id, agent_name, session_id, agent_name),
        )

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_email_by_id(self, email_id: str) -> Optional[dict]:
        """
        根据 email_id 查询邮件记录

        Args:
            email_id: 邮件ID

        Returns:
            dict: 邮件记录，如果不存在返回 None
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row else None

    # ===== External Email Map 相关方法 =====

    def save_external_email_mapping(
        self,
        external_message_id: str,
        internal_email_id: str,
        agent_name: str = None,
        task_id: str = None,
        user_session_id: str = None,
        agent_session_id: str = None,
    ):
        """保存外部 Message-ID 到内部 Email ID 的映射（enriched: 包含 session 全量信息）"""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO external_email_map
               (external_message_id, internal_email_id, agent_name, task_id, user_session_id, agent_session_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                external_message_id,
                internal_email_id,
                agent_name,
                task_id,
                user_session_id,
                agent_session_id,
            ),
        )
        self.conn.commit()

    def get_internal_email_id(self, external_message_id: str) -> Optional[str]:
        """通过外部 Message-ID 查询内部 Email ID"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT internal_email_id FROM external_email_map WHERE external_message_id = ?",
            (external_message_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def get_mapping_by_external_id(self, external_message_id: str) -> Optional[dict]:
        """通过外部 Message-ID 查询完整 mapping（含 session 信息）"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM external_email_map WHERE external_message_id = ?",
            (external_message_id,),
        )
        row = cursor.fetchone()
        if row:
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        return None

    def get_external_message_id(self, internal_email_id: str) -> Optional[str]:
        """通过内部 Email ID 查询外部 Message-ID"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT external_message_id FROM external_email_map WHERE internal_email_id = ?",
            (internal_email_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    # ===== User Sessions 相关方法 =====

    def upsert_user_session(
        self, email, user_session_id: str, agent_name: str, is_read: int
    ):
        """
        更新或插入用户会话记录（每次用户相关的邮件 dispatch 后调用）

        Args:
            email: Email 对象
            user_session_id: 用户视角的 session_id
            agent_name: 对方名称（收件=sender，发件=recipient）
            is_read: 0 未读，1 已读
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO user_sessions
                (user_session_id, agent_name, is_read, timestamp, sender, recipient,
                 subject, body, in_reply_to, task_id, sender_session_id, recipient_session_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user_session_id,
                agent_name,
                is_read,
                email.timestamp.isoformat()
                if hasattr(email.timestamp, "isoformat")
                else str(email.timestamp),
                email.sender,
                email.recipient,
                email.subject,
                email.body,
                email.in_reply_to,
                email.task_id,
                email.sender_session_id,
                email.recipient_session_id,
                json.dumps(email.metadata) if email.metadata else None,
            ),
        )
        self.conn.commit()

    def mark_session_as_read(self, user_session_id: str):
        """标记用户会话为已读"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE user_sessions SET is_read = 1 WHERE user_session_id = ?",
            (user_session_id,),
        )
        self.conn.commit()

    def get_user_sessions(
        self, user_agent_name: str, page: int = 1, per_page: int = 20
    ):
        """
        获取用户的所有邮件会话（分页）

        Args:
            user_agent_name: 用户 Agent 名称（如 'User'）
            page: 页码（从 1 开始）
            per_page: 每页数量

        Returns:
            dict: {
                'sessions': [...],  # 会话列表
                'total': 总数,
                'page': 当前页,
                'per_page': 每页数量,
                'total_pages': 总页数
            }
        """
        cursor = self.conn.cursor()

        # 获取总数
        cursor.execute("SELECT COUNT(*) FROM user_sessions")
        total = cursor.fetchone()[0]
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        # 分页查询
        offset = (page - 1) * per_page
        cursor.execute(
            """
            SELECT user_session_id AS session_id, agent_name, subject,
                   timestamp AS last_email_time, is_read
            FROM user_sessions
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """,
            (per_page, offset),
        )

        columns = [col[0] for col in cursor.description]
        sessions = []
        for row in cursor.fetchall():
            d = dict(zip(columns, row))
            d["is_unread"] = d.pop("is_read", 0) == 0
            d["participants"] = [d["agent_name"]] if d.get("agent_name") else []
            sessions.append(d)

        return {
            "sessions": sessions,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    # ===== Scheduled Task相关方法 =====

    def create_task(self, task_dict):
        """创建定时任务"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO scheduled_tasks
            (id, task_name, target_agent, trigger_time, recurrence_rule,
             task_description, task_metadata, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_dict["id"],
                task_dict["task_name"],
                task_dict["target_agent"],
                task_dict["trigger_time"],
                task_dict.get("recurrence_rule"),
                task_dict.get("task_description"),
                json.dumps(task_dict.get("task_metadata"))
                if task_dict.get("task_metadata")
                else None,
                task_dict["status"],
                task_dict["created_at"],
                task_dict["updated_at"],
            ),
        )
        self.conn.commit()

    def get_task(self, task_id):
        """获取单个任务"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row else None

    def list_tasks(self, status=None, agent=None):
        """列出任务"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM scheduled_tasks WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if agent:
            query += " AND target_agent = ?"
            params.append(agent)

        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def update_task(self, task_id, updates):
        """更新任务"""
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        query = f"UPDATE scheduled_tasks SET {set_clause}, updated_at = ? WHERE id = ?"
        params = list(updates.values()) + [
            datetime.now(timezone.utc).isoformat(),
            task_id,
        ]

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()

    def delete_task(self, task_id):
        """删除任务"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def get_pending_tasks(self):
        """获取应该触发的任务（status='active' 且 trigger_time <= now）"""
        cursor = self.conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            SELECT * FROM scheduled_tasks
            WHERE status = 'active' AND trigger_time <= ?
            ORDER BY trigger_time ASC
        """,
            (now,),
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def mark_triggered(self, task_id):
        """标记任务已触发"""
        task = self.get_task(task_id)
        if not task:
            return

        # 如果是周期性任务，计算下次触发时间并保持active
        if task.get("recurrence_rule"):
            next_time = self._calculate_next_trigger(
                task["trigger_time"], task["recurrence_rule"]
            )
            self.update_task(
                task_id,
                {
                    "last_triggered_at": datetime.now(timezone.utc).isoformat(),
                    "trigger_time": next_time,
                },
            )
        else:
            # 一次性任务，标记为completed
            self.update_task(
                task_id,
                {
                    "last_triggered_at": datetime.now(timezone.utc).isoformat(),
                    "status": "completed",
                },
            )

    def mark_failed(self, task_id, reason):
        """标记任务失败"""
        self.update_task(task_id, {"status": "failed", "failure_reason": reason})

    def _calculate_next_trigger(self, current_time, recurrence_rule):
        """计算下次触发时间"""
        from datetime import timedelta

        current = datetime.fromisoformat(current_time)

        if recurrence_rule == "daily":
            next_time = current + timedelta(days=1)
        elif recurrence_rule == "weekly":
            next_time = current + timedelta(weeks=1)
        elif recurrence_rule == "monthly":
            # 简化处理：加30天
            next_time = current + timedelta(days=30)
        else:
            next_time = current

        return next_time.isoformat()

    def get_agent_sessions(self, agent_name: str) -> list:
        """
        获取 Agent 的所有 sessions（用于 Matrix View Memory Tab）

        Args:
            agent_name: Agent 名称

        Returns:
            List[dict]: Agent 的所有 sessions
        """
        cursor = self.conn.cursor()

        # 使用索引优化的查询（符合 CONCEPTS.md 的定义）
        # Agent 的 sessions = 作为发送者的 sessions + 作为接收者的 sessions
        query = """
            SELECT 
                sender_session_id as session_id,
                MAX(timestamp) as last_email_time
            FROM emails
            WHERE sender = ?
            GROUP BY sender_session_id
            
            UNION
            
            SELECT 
                recipient_session_id as session_id,
                MAX(timestamp) as last_email_time
            FROM emails
            WHERE recipient = ?
            GROUP BY recipient_session_id
            
            ORDER BY last_email_time DESC
        """

        cursor.execute(query, (agent_name, agent_name))
        results = cursor.fetchall()

        sessions = []
        for row in results:
            session_id, last_email_time = row

            # 获取该 session 的第一封邮件的 subject
            subject_query = """
                SELECT subject FROM emails
                WHERE (sender = ? AND sender_session_id = ?)
                   OR (recipient = ? AND recipient_session_id = ?)
                ORDER BY timestamp ASC
                LIMIT 1
            """
            cursor.execute(
                subject_query, (agent_name, session_id, agent_name, session_id)
            )
            subject_row = cursor.fetchone()
            first_subject = subject_row[0] if subject_row else ""

            # 获取该 session 的邮件数量
            count_query = """
                SELECT COUNT(*) FROM emails
                WHERE (sender = ? AND sender_session_id = ?)
                   OR (recipient = ? AND recipient_session_id = ?)
            """
            cursor.execute(
                count_query, (agent_name, session_id, agent_name, session_id)
            )
            email_count = cursor.fetchone()[0]

            sessions.append(
                {
                    "session_id": session_id,
                    "last_email_time": last_email_time,
                    "first_subject": first_subject,
                    "email_count": email_count,
                }
            )

        return sessions
