import aiosqlite
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from ..core.log_util import AutoLoggerMixin


class AgentMatrixDB(AutoLoggerMixin):
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn: aiosqlite.Connection = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._configure_pragmas()
        await self.create_tables()

    async def _configure_pragmas(self):
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA busy_timeout=5000")
        await self.conn.execute("PRAGMA synchronous=NORMAL")
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def create_tables(self):
        await self.conn.execute("""
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
                metadata TEXT
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS email_to_deliver (
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
                metadata TEXT
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS email_to_process (
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
                metadata TEXT
            )
        """)
        await self.conn.execute("""
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
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS external_email_map (
                external_message_id TEXT PRIMARY KEY,
                internal_email_id TEXT NOT NULL,
                agent_name TEXT,
                task_id TEXT,
                user_session_id TEXT,
                agent_session_id TEXT
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_session_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                agent_session_id TEXT,
                task_id TEXT,
                subject TEXT,
                is_read INTEGER NOT NULL DEFAULT 0,
                timestamp TEXT,
                created_at TEXT,
                last_email_id TEXT
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS session_events (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_name TEXT NOT NULL,
                event_detail TEXT,
                timestamp TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await self.conn.commit()
        await self._create_indexes()

    async def _create_indexes(self):
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sender_session
            ON emails(sender_session_id, sender, task_id)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_receiver_session
            ON emails(recipient_session_id, recipient, task_id)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_in_reply_to
            ON emails(in_reply_to)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_status
            ON scheduled_tasks(status)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_trigger_time
            ON scheduled_tasks(trigger_time)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_next_trigger
            ON scheduled_tasks(status, trigger_time)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_target_agent
            ON scheduled_tasks(target_agent)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_external_map_internal
            ON external_email_map(internal_email_id)
        """)
        await self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_events_lookup
            ON session_events(owner, session_id, timestamp)
        """)
        await self.conn.commit()

    # ===== Email Pipeline =====

    async def log_email(self, email):
        email_data = (
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
        )
        await self.conn.execute(
            "INSERT OR IGNORE INTO email_to_deliver (id, timestamp, sender, recipient, subject, body, in_reply_to, task_id, sender_session_id, recipient_session_id, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            email_data,
        )
        await self.conn.commit()

    async def mark_email_delivered(self, email_id: str):
        cursor = await self.conn.execute("SELECT * FROM email_to_deliver WHERE id = ?", (email_id,))
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return
        d = dict(row)
        await self.conn.execute(
            "INSERT OR IGNORE INTO email_to_process (id, timestamp, sender, recipient, subject, body, in_reply_to, task_id, sender_session_id, recipient_session_id, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d["id"], d["timestamp"], d["sender"], d["recipient"],
             d["subject"], d["body"], d["in_reply_to"], d["task_id"],
             d["sender_session_id"], d["recipient_session_id"], d["metadata"]),
        )
        await self.conn.execute("DELETE FROM email_to_deliver WHERE id = ?", (email_id,))
        await self.conn.commit()

    async def get_undelivered_emails(self):
        cursor = await self.conn.execute("SELECT * FROM email_to_deliver ORDER BY timestamp ASC")
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(r) for r in rows]

    async def mark_emails_processed(self, email_ids: list):
        if not email_ids:
            return
        for eid in email_ids:
            cursor = await self.conn.execute("SELECT * FROM email_to_process WHERE id = ?", (eid,))
            row = await cursor.fetchone()
            await cursor.close()
            if not row:
                self.logger.warning(f"🔵 mark_emails_processed: {eid[:8]} NOT FOUND in email_to_process")
                continue
            d = dict(row)
            self.logger.info(f"🔵 mark_emails_processed: found {eid[:8]} in email_to_process, inserting to emails...")
            await self.conn.execute(
                "INSERT OR IGNORE INTO emails (id, timestamp, sender, recipient, subject, body, in_reply_to, task_id, sender_session_id, recipient_session_id, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (d["id"], d["timestamp"], d["sender"], d["recipient"],
                 d["subject"], d["body"], d["in_reply_to"], d["task_id"],
                 d["sender_session_id"], d["recipient_session_id"], d["metadata"]),
            )
            cursor2 = await self.conn.execute("DELETE FROM email_to_process WHERE id = ?", (eid,))
            deleted = cursor2.rowcount
            await cursor2.close()
            self.logger.info(f"🔵 mark_emails_processed: delete rowcount={deleted}")
        await self.conn.commit()
        self.logger.info(f"🔵 mark_emails_processed: commit done")

    async def get_unprocessed_emails(self, recipient: str = None):
        if recipient:
            cursor = await self.conn.execute(
                "SELECT * FROM email_to_process WHERE recipient = ? ORDER BY timestamp ASC",
                (recipient,),
            )
        else:
            cursor = await self.conn.execute("SELECT * FROM email_to_process ORDER BY timestamp ASC")
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(r) for r in rows]

    # ===== Email Queries =====

    async def get_mailbox(self, agent_name, limit=50):
        cursor = await self.conn.execute(
            "SELECT * FROM emails WHERE recipient = ? OR sender = ? ORDER BY timestamp DESC LIMIT ?",
            (agent_name, agent_name, limit),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(r) for r in rows]

    async def get_mails_by_range(self, agent_name, task_id, start=0, end=1):
        cursor = await self.conn.execute(
            "SELECT * FROM emails WHERE task_id = ? AND (recipient = ? OR sender = ?) ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (task_id, agent_name, agent_name, end - start + 1, start),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(r) for r in rows]

    async def get_user_session_emails(self, task_id, user_agent_name="User"):
        cursor = await self.conn.execute(
            "SELECT * FROM emails WHERE task_id = ? AND (sender = ? OR recipient = ?) ORDER BY timestamp ASC",
            (task_id, user_agent_name, user_agent_name),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(r) for r in rows]

    async def update_receiver_session(self, email_id: str, recipient_session_id: str, receiver_name: str):
        total_updated = 0
        for table in ("email_to_deliver", "email_to_process", "emails"):
            cursor = await self.conn.execute(
                f"UPDATE {table} SET recipient_session_id = ? WHERE id = ? AND recipient = ?",
                (recipient_session_id, email_id, receiver_name),
            )
            total_updated += cursor.rowcount
            await cursor.close()

        if total_updated == 0:
            raise RuntimeError(
                f"Failed to update recipient_session_id: "
                f"email_id={email_id}, receiver={receiver_name}, "
                f"recipient_session_id={recipient_session_id}. "
                f"Email not found or recipient mismatch."
            )
        await self.conn.commit()

    async def get_emails_by_session(self, session_id: str, agent_name: str):
        condition = """
            (sender_session_id = ? AND sender = ?)
            OR
            (recipient_session_id = ? AND recipient = ?)
        """
        params = (session_id, agent_name, session_id, agent_name)
        result = []
        for table in ("emails", "email_to_process", "email_to_deliver"):
            cursor = await self.conn.execute(
                f"SELECT * FROM {table} WHERE {condition} ORDER BY timestamp ASC",
                params,
            )
            rows = await cursor.fetchall()
            await cursor.close()
            result.extend(dict(r) for r in rows)
        return result

    async def get_email_by_id(self, email_id: str) -> Optional[dict]:
        for table in ("email_to_deliver", "email_to_process", "emails"):
            cursor = await self.conn.execute(f"SELECT * FROM {table} WHERE id = ?", (email_id,))
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                return dict(row)
        return None

    # ===== External Email Map =====

    async def save_external_email_mapping(
        self,
        external_message_id: str,
        internal_email_id: str,
        agent_name: str = None,
        task_id: str = None,
        user_session_id: str = None,
        agent_session_id: str = None,
    ):
        await self.conn.execute(
            """INSERT OR REPLACE INTO external_email_map
               (external_message_id, internal_email_id, agent_name, task_id, user_session_id, agent_session_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (external_message_id, internal_email_id, agent_name, task_id, user_session_id, agent_session_id),
        )
        await self.conn.commit()

    async def get_internal_email_id(self, external_message_id: str) -> Optional[str]:
        cursor = await self.conn.execute(
            "SELECT internal_email_id FROM external_email_map WHERE external_message_id = ?",
            (external_message_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row else None

    async def get_mapping_by_external_id(self, external_message_id: str) -> Optional[dict]:
        cursor = await self.conn.execute(
            "SELECT * FROM external_email_map WHERE external_message_id = ?",
            (external_message_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return dict(row) if row else None

    async def get_external_message_id(self, internal_email_id: str) -> Optional[str]:
        cursor = await self.conn.execute(
            "SELECT external_message_id FROM external_email_map WHERE internal_email_id = ?",
            (internal_email_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row else None

    # ===== User Sessions =====

    async def create_user_session(
        self, user_session_id: str, agent_name: str, task_id: str, subject: str,
        agent_session_id: str = None, timestamp: str = None,
        last_email_id: str = None, last_agent_mail_time: str = None,
        last_check_time: str = None,
    ):
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        await self.conn.execute(
            """INSERT OR IGNORE INTO user_sessions
                (user_session_id, agent_name, agent_session_id, task_id, subject,
                 timestamp, created_at, last_email_id, last_agent_mail_time, last_check_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_session_id, agent_name, agent_session_id, task_id, subject,
             timestamp, timestamp, last_email_id, last_agent_mail_time, last_check_time),
        )
        await self.conn.commit()

    async def update_user_session(
        self, user_session_id: str, timestamp: str = None,
        last_email_id: str = None, agent_session_id: str = None,
        last_agent_mail_time: str = None, last_check_time: str = None,
    ):
        sets = []
        params = []
        if timestamp is not None:
            sets.append("timestamp = ?")
            params.append(timestamp)
        if last_email_id is not None:
            sets.append("last_email_id = ?")
            params.append(last_email_id)
        if agent_session_id is not None:
            sets.append("agent_session_id = ?")
            params.append(agent_session_id)
        if last_agent_mail_time is not None:
            sets.append("last_agent_mail_time = ?")
            params.append(last_agent_mail_time)
        if last_check_time is not None:
            sets.append("last_check_time = ?")
            params.append(last_check_time)
        if not sets:
            return
        params.append(user_session_id)
        await self.conn.execute(
            f"UPDATE user_sessions SET {', '.join(sets)} WHERE user_session_id = ?",
            params,
        )
        await self.conn.commit()

    async def get_user_session(self, user_session_id: str) -> Optional[dict]:
        cursor = await self.conn.execute(
            "SELECT * FROM user_sessions WHERE user_session_id = ?",
            (user_session_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return dict(row) if row else None

    async def update_check_time(self, user_session_id: str, check_time: str = None):
        """
        更新用户查看时间（用于标记已读）

        Args:
            user_session_id: 会话ID
            check_time: 查看时间（默认为当前时间）
        """
        if check_time is None:
            check_time = datetime.now().isoformat()

        await self.conn.execute(
            "UPDATE user_sessions SET last_check_time = ? WHERE user_session_id = ?",
            (check_time, user_session_id),
        )
        await self.conn.commit()

    async def get_user_sessions(self, user_agent_name: str, page: int = 1, per_page: int = 20):
        cursor = await self.conn.execute("SELECT COUNT(*) FROM user_sessions")
        row = await cursor.fetchone()
        await cursor.close()
        total = row[0]
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        offset = (page - 1) * per_page
        cursor = await self.conn.execute(
            """SELECT user_session_id AS session_id, agent_name, agent_session_id,
                      task_id, subject, timestamp AS last_email_time,
                      last_email_id, last_agent_mail_time, last_check_time
               FROM user_sessions
               ORDER BY timestamp DESC
               LIMIT ? OFFSET ?""",
            (per_page, offset),
        )
        rows = await cursor.fetchall()
        await cursor.close()

        sessions = []
        for r in rows:
            d = dict(r)
            # 新逻辑：基于时间比较计算未读状态
            last_agent_time = d.get("last_agent_mail_time")
            last_check_time = d.get("last_check_time")

            if last_agent_time and last_check_time:
                d["is_unread"] = last_agent_time > last_check_time
            elif last_agent_time and not last_check_time:
                d["is_unread"] = True
            else:
                d["is_unread"] = False

            d["participants"] = [d["agent_name"]] if d.get("agent_name") else []
            sessions.append(d)

        return {
            "sessions": sessions,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    # ===== Scheduled Tasks =====

    async def create_task(self, task_dict):
        await self.conn.execute(
            """INSERT INTO scheduled_tasks
               (id, task_name, target_agent, trigger_time, recurrence_rule,
                task_description, task_metadata, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task_dict["id"],
                task_dict["task_name"],
                task_dict["target_agent"],
                task_dict["trigger_time"],
                task_dict.get("recurrence_rule"),
                task_dict.get("task_description"),
                json.dumps(task_dict.get("task_metadata")) if task_dict.get("task_metadata") else None,
                task_dict["status"],
                task_dict["created_at"],
                task_dict["updated_at"],
            ),
        )
        await self.conn.commit()

    async def get_task(self, task_id):
        cursor = await self.conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        await cursor.close()
        return dict(row) if row else None

    async def list_tasks(self, status=None, agent=None):
        query = "SELECT * FROM scheduled_tasks WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if agent:
            query += " AND target_agent = ?"
            params.append(agent)
        query += " ORDER BY created_at DESC"
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(r) for r in rows]

    async def update_task(self, task_id, updates):
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        query = f"UPDATE scheduled_tasks SET {set_clause}, updated_at = ? WHERE id = ?"
        params = list(updates.values()) + [datetime.now(timezone.utc).isoformat(), task_id]
        await self.conn.execute(query, params)
        await self.conn.commit()

    async def delete_task(self, task_id):
        await self.conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        await self.conn.commit()

    async def get_pending_tasks(self):
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self.conn.execute(
            """SELECT * FROM scheduled_tasks
               WHERE status = 'active' AND trigger_time <= ?
               ORDER BY trigger_time ASC""",
            (now,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(r) for r in rows]

    async def mark_triggered(self, task_id):
        task = await self.get_task(task_id)
        if not task:
            return
        if task.get("recurrence_rule"):
            next_time = self._calculate_next_trigger(task["trigger_time"], task["recurrence_rule"])
            await self.update_task(
                task_id,
                {"last_triggered_at": datetime.now(timezone.utc).isoformat(), "trigger_time": next_time},
            )
        else:
            await self.update_task(
                task_id,
                {"last_triggered_at": datetime.now(timezone.utc).isoformat(), "status": "completed"},
            )

    async def mark_failed(self, task_id, reason):
        await self.update_task(task_id, {"status": "failed", "failure_reason": reason})

    def _calculate_next_trigger(self, current_time, recurrence_rule):
        from datetime import timedelta
        current = datetime.fromisoformat(current_time)
        if recurrence_rule == "daily":
            next_time = current + timedelta(days=1)
        elif recurrence_rule == "weekly":
            next_time = current + timedelta(weeks=1)
        elif recurrence_rule == "monthly":
            next_time = current + timedelta(days=30)
        else:
            next_time = current
        return next_time.isoformat()

    # ===== Search =====

    async def search_emails_by_keyword_groups(self, agent_name: str, keywords: list, limit: int = 50) -> list:
        if not keywords:
            return []
        keyword_conditions = []
        keyword_params = []
        for kw in keywords:
            pattern = f"%{kw}%"
            keyword_conditions.append("(subject LIKE ? OR body LIKE ?)")
            keyword_params.extend([pattern, pattern])
        where_clause = " AND ".join(keyword_conditions)
        agent_params = [agent_name, agent_name] * 3
        all_params = agent_params + keyword_params
        query = f"""
            SELECT id, timestamp, sender, recipient, subject, body,
                   sender_session_id, recipient_session_id
            FROM (
                SELECT * FROM emails WHERE sender = ? OR recipient = ?
                UNION ALL
                SELECT * FROM email_to_process WHERE sender = ? OR recipient = ?
                UNION ALL
                SELECT * FROM email_to_deliver WHERE sender = ? OR recipient = ?
            )
            WHERE {where_clause}
        """
        cursor = await self.conn.execute(query, all_params)
        rows = await cursor.fetchall()
        await cursor.close()
        matched_emails = [dict(r) for r in rows]
        if not matched_emails:
            return []
        from collections import defaultdict
        sessions = defaultdict(lambda: {"hit_count": 0, "last_email_time": "", "first_subject": ""})
        for email in matched_emails:
            sid = email.get("sender_session_id") or email.get("recipient_session_id") or ""
            if not sid:
                continue
            s = sessions[sid]
            s["hit_count"] += 1
            ts = email.get("timestamp", "")
            if ts > s["last_email_time"]:
                s["last_email_time"] = ts
                s["first_subject"] = email.get("subject", "")
        result = [{"session_id": sid, **data} for sid, data in sessions.items()]
        result.sort(key=lambda x: (-x["hit_count"], x["last_email_time"]))
        return result[:limit]

    # ===== Agent Sessions =====

    async def get_agent_sessions(self, agent_name: str) -> list:
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
        cursor = await self.conn.execute(query, (agent_name, agent_name))
        results = await cursor.fetchall()
        await cursor.close()

        sessions = []
        for row in results:
            session_id = row["session_id"]
            last_email_time = row["last_email_time"]

            subject_cursor = await self.conn.execute(
                """SELECT subject FROM emails
                   WHERE (sender = ? AND sender_session_id = ?)
                      OR (recipient = ? AND recipient_session_id = ?)
                   ORDER BY timestamp ASC LIMIT 1""",
                (agent_name, session_id, agent_name, session_id),
            )
            subject_row = await subject_cursor.fetchone()
            await subject_cursor.close()
            first_subject = subject_row[0] if subject_row else ""

            count_cursor = await self.conn.execute(
                """SELECT COUNT(*) FROM emails
                   WHERE (sender = ? AND sender_session_id = ?)
                      OR (recipient = ? AND recipient_session_id = ?)""",
                (agent_name, session_id, agent_name, session_id),
            )
            count_row = await count_cursor.fetchone()
            await count_cursor.close()
            email_count = count_row[0]

            sessions.append({
                "session_id": session_id,
                "last_email_time": last_email_time,
                "first_subject": first_subject,
                "email_count": email_count,
            })
        return sessions

    # ===== Session Events =====

    async def insert_session_event(self, owner: str, session_id: str, event_type: str, event_name: str,
                                   event_detail: str = None, timestamp: str = None):
        await self.conn.execute(
            "INSERT INTO session_events (id, owner, session_id, event_type, event_name, event_detail, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), owner, session_id, event_type, event_name, event_detail,
             timestamp or datetime.now().isoformat()),
        )
        await self.conn.commit()

    async def get_session_events(self, owner: str, session_id: str, limit: int = 200, offset: int = 0):
        cursor = await self.conn.execute(
            "SELECT id, event_type, event_name, event_detail, timestamp FROM session_events WHERE owner = ? AND session_id = ? ORDER BY timestamp ASC LIMIT ? OFFSET ?",
            (owner, session_id, limit, offset),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            {"id": r[0], "event_type": r[1], "event_name": r[2], "event_detail": r[3], "timestamp": r[4]}
            for r in rows
        ]

    async def get_latest_session_events(self, owner: str, session_id: str, limit: int = 200):
        """获取最新的 N 条事件，返回按 timestamp ASC 排序"""
        cursor = await self.conn.execute(
            "SELECT id, event_type, event_name, event_detail, timestamp FROM session_events WHERE owner = ? AND session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (owner, session_id, limit),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        rows.reverse()
        return [
            {"id": r[0], "event_type": r[1], "event_name": r[2], "event_detail": r[3], "timestamp": r[4]}
            for r in rows
        ]

    async def get_session_events_before(self, owner: str, session_id: str, before_timestamp: str, limit: int = 200):
        """获取指定时间戳之前的 N 条事件，返回按 timestamp ASC 排序"""
        cursor = await self.conn.execute(
            "SELECT id, event_type, event_name, event_detail, timestamp FROM session_events WHERE owner = ? AND session_id = ? AND timestamp < ? ORDER BY timestamp DESC LIMIT ?",
            (owner, session_id, before_timestamp, limit),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        rows.reverse()
        return [
            {"id": r[0], "event_type": r[1], "event_name": r[2], "event_detail": r[3], "timestamp": r[4]}
            for r in rows
        ]

    async def get_session_event_count(self, owner: str, session_id: str) -> int:
        """获取 session 事件总数"""
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM session_events WHERE owner = ? AND session_id = ?",
            (owner, session_id),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row else 0

    async def get_session_events_by_type(self, owner: str, session_id: str, event_types: list, limit: int = 200):
        placeholders = ",".join("?" * len(event_types))
        query = f"""
            SELECT id, event_type, event_name, event_detail, timestamp
            FROM session_events
            WHERE owner = ? AND session_id = ? AND event_type IN ({placeholders})
            ORDER BY timestamp ASC
            LIMIT ?
        """
        params = [owner, session_id] + event_types + [limit]
        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            {"id": r[0], "event_type": r[1], "event_name": r[2], "event_detail": r[3], "timestamp": r[4]}
            for r in rows
        ]

    # ===== EmailProxyService raw cursor absorption =====

    async def find_sender_session_by_task(self, agent_name: str, sender: str, task_id: str, agent_session_id: str) -> Optional[str]:
        """Find sender_session_id for emails where agent received from sender in a task session."""
        cursor = await self.conn.execute(
            """SELECT sender_session_id FROM emails
               WHERE recipient = ? AND sender = ? AND task_id = ? AND recipient_session_id = ?
               ORDER BY timestamp DESC LIMIT 1""",
            (agent_name, sender, task_id, agent_session_id),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row else None

    async def find_user_session_by_task(self, user_agent_name: str, task_id: str, agent_session_id: str) -> Optional[str]:
        """Find sender_session_id for outbound emails: user sent, agent received in a task session."""
        cursor = await self.conn.execute(
            """SELECT sender_session_id FROM emails
               WHERE sender = ? AND task_id = ? AND recipient_session_id = ?
               ORDER BY timestamp DESC LIMIT 1""",
            (user_agent_name, task_id, agent_session_id),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row else None
