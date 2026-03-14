"""
SQLite 数据库管理器（支持 WAL 模式）

管理一个统一的数据库文件：
- memory.db: Agent 的统一记忆数据库，包含 3 张表：
  - longterm_entity: 长期实体档案（跨会话）
  - entity_profile: 会话级实体档案（带 task_id）
  - timeline: 时间线日志（带 task_id）
"""

import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any, Optional


class StorageManager:
    """SQLite 数据库管理器（支持 WAL 模式）"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        """连接数据库并开启 WAL 模式"""
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)

        # ✅ 开启 WAL 模式（关键！）
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")  # 平衡性能和安全
        self.conn.execute("PRAGMA cache_size=-64000;")   # 64MB 缓存

        self.conn.row_factory = sqlite3.Row  # 返回字典格式

    async def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def init_tables(self):
        """初始化所有表（longterm_entity, entity_profile, timeline）"""
        # 1. longterm_entity 表（原 global Entity_Profiles）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS longterm_entity (
                uid TEXT PRIMARY KEY,
                canonical_name TEXT,
                aliases JSON,
                summary TEXT,
                profile_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_longterm_name
            ON longterm_entity(canonical_name)
        """)

        # 2. entity_profile 表（原 session Entity_Profiles + task_id）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entity_profile (
                uid TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                canonical_name TEXT,
                aliases JSON,
                summary TEXT,
                profile_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_profile_session_name
            ON entity_profile(task_id, canonical_name)
        """)

        # 3. timeline 表（原 Timeline_Log + task_id）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                event_text TEXT NOT NULL,
                entities JSON,
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timeline_session_processed
            ON timeline(task_id, processed)
        """)

        self.conn.commit()

    # ==================== Session Entity Profile CRUD ====================
    # 所有方法都需要 task_id

    def insert_session_entity(
        self,
        uid: str,
        task_id: str,
        canonical_name: str,
        aliases: list,
        summary: str,
        profile_text: str
    ) -> bool:
        """插入 session 实体档案"""
        try:
            import json
            self.conn.execute("""
                INSERT INTO entity_profile (uid, task_id, canonical_name, aliases, summary, profile_text)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (uid, task_id, canonical_name, json.dumps(aliases), summary, profile_text))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def update_session_entity(
        self,
        uid: str,
        task_id: str,
        summary: str = None,
        profile_text: str = None,
        aliases: list = None
    ) -> bool:
        """更新 session 实体档案"""
        updates = []
        params = []

        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)

        if profile_text is not None:
            updates.append("profile_text = ?")
            params.append(profile_text)

        if aliases is not None:
            updates.append("aliases = ?")
            import json
            params.append(json.dumps(aliases))

        if not updates:
            return False

        params.extend([task_id, uid])

        self.conn.execute(f"""
            UPDATE entity_profile
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ? AND uid = ?
        """, params)

        self.conn.commit()
        return True

    def get_session_entity(
        self,
        uid: str,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取单个 session 实体档案"""
        cursor = self.conn.execute("""
            SELECT * FROM entity_profile
            WHERE task_id = ? AND uid = ?
        """, (task_id, uid))

        row = cursor.fetchone()
        return dict(row) if row else None

    def search_session_entities(
        self,
        task_id: str,
        entity_name: str
    ) -> List[Dict[str, Any]]:
        """搜索 session 实体档案（精确匹配 canonical_name 或 aliases）"""
        cursor = self.conn.execute("""
            SELECT * FROM entity_profile
            WHERE task_id = ?
              AND (canonical_name = ?
                   OR EXISTS (
                       SELECT 1 FROM json_each(aliases)
                       WHERE json_each.value = ?
                   ))
            ORDER BY updated_at DESC
        """, (task_id, entity_name, entity_name))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def delete_session_entity(
        self,
        uid: str,
        task_id: str
    ) -> bool:
        """删除 session 实体档案"""
        cursor = self.conn.execute("""
            DELETE FROM entity_profile
            WHERE task_id = ? AND uid = ?
        """, (task_id, uid))

        self.conn.commit()
        return cursor.rowcount > 0

    # ==================== Longterm Entity Profile CRUD ====================
    # 所有方法都不需要 task_id

    def insert_longterm_entity(
        self,
        uid: str,
        canonical_name: str,
        aliases: list,
        summary: str,
        profile_text: str
    ) -> bool:
        """插入 longterm 实体档案"""
        try:
            import json
            self.conn.execute("""
                INSERT INTO longterm_entity (uid, canonical_name, aliases, summary, profile_text)
                VALUES (?, ?, ?, ?, ?)
            """, (uid, canonical_name, json.dumps(aliases), summary, profile_text))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def update_longterm_entity(
        self,
        uid: str,
        summary: str = None,
        profile_text: str = None,
        aliases: list = None
    ) -> bool:
        """更新 longterm 实体档案"""
        updates = []
        params = []

        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)

        if profile_text is not None:
            updates.append("profile_text = ?")
            params.append(profile_text)

        if aliases is not None:
            updates.append("aliases = ?")
            import json
            params.append(json.dumps(aliases))

        if not updates:
            return False

        params.append(uid)

        self.conn.execute(f"""
            UPDATE longterm_entity
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE uid = ?
        """, params)

        self.conn.commit()
        return True

    def get_longterm_entity(
        self,
        uid: str
    ) -> Optional[Dict[str, Any]]:
        """获取单个 longterm 实体档案"""
        cursor = self.conn.execute("""
            SELECT * FROM longterm_entity WHERE uid = ?
        """, (uid,))

        row = cursor.fetchone()
        return dict(row) if row else None

    def search_longterm_entities(
        self,
        entity_name: str
    ) -> List[Dict[str, Any]]:
        """搜索 longterm 实体档案（精确匹配 canonical_name 或 aliases）"""
        cursor = self.conn.execute("""
            SELECT * FROM longterm_entity
            WHERE canonical_name = ?
               OR EXISTS (
                   SELECT 1 FROM json_each(aliases)
                   WHERE json_each.value = ?
               )
            ORDER BY updated_at DESC
        """, (entity_name, entity_name))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def delete_longterm_entity(
        self,
        uid: str
    ) -> bool:
        """删除 longterm 实体档案"""
        cursor = self.conn.execute("""
            DELETE FROM longterm_entity WHERE uid = ?
        """, (uid,))

        self.conn.commit()
        return cursor.rowcount > 0

    # ==================== 合并查询（用于 recall）====================

    def search_entities_merged(
        self,
        task_id: str,
        entity_name: str
    ) -> List[Dict[str, Any]]:
        """
        跨表查询：合并 session + longterm profiles

        从同一个数据库的两张表查询，然后按 canonical_name 合并。

        Args:
            task_id: 用户会话 ID（用于查询 session 表）
            entity_name: 要查找的实体名称（精确匹配）

        Returns:
            合并后的 profile 列表，每个 profile 包含:
            - canonical_name: str (实体名称)
            - session_profile: dict or None (session 记录)
            - longterm_profile: dict or None (longterm 记录)
        """
        # 1. 查询 entity_profile（session，带 task_id 过滤）
        cursor = self.conn.execute("""
            SELECT * FROM entity_profile
            WHERE task_id = ?
              AND (canonical_name = ?
                   OR EXISTS (
                       SELECT 1 FROM json_each(aliases)
                       WHERE json_each.value = ?
                   ))
            ORDER BY updated_at DESC
        """, (task_id, entity_name, entity_name))
        session_profiles = [dict(row) for row in cursor.fetchall()]

        # 2. 查询 longterm_entity（无 task_id 过滤）
        cursor = self.conn.execute("""
            SELECT * FROM longterm_entity
            WHERE canonical_name = ?
               OR EXISTS (
                   SELECT 1 FROM json_each(aliases)
                   WHERE json_each.value = ?
               )
            ORDER BY updated_at DESC
        """, (entity_name, entity_name))
        longterm_profiles = [dict(row) for row in cursor.fetchall()]

        # 3. 按 canonical_name 合并
        merged = {}

        for p in session_profiles:
            name = p['canonical_name']
            if name not in merged:
                merged[name] = {'session': None, 'longterm': None}
            merged[name]['session'] = p

        for p in longterm_profiles:
            name = p['canonical_name']
            if name not in merged:
                merged[name] = {'session': None, 'longterm': None}
            merged[name]['longterm'] = p

        # 4. 转换为列表
        result = []
        for name, profiles in merged.items():
            result.append({
                'canonical_name': name,
                'session_profile': profiles['session'],
                'longterm_profile': profiles['longterm']
            })

        return result

    # ==================== Timeline CRUD ====================

    def append_timeline(
        self,
        task_id: str,
        event_text: str,
        entities: List[str] = None
    ) -> int:
        """追加 timeline 日志

        Args:
            task_id: 用户会话 ID
            event_text: 事件描述文本
            entities: 实体列表（可选）

        Returns:
            int: 新记录的 ID
        """
        import json

        entities_json = json.dumps(entities) if entities else None

        cursor = self.conn.execute("""
            INSERT INTO timeline (task_id, event_text, entities, processed)
            VALUES (?, ?, ?, FALSE)
        """, (task_id, event_text, entities_json))

        self.conn.commit()
        return cursor.lastrowid

    def fetch_unprocessed_events(
        self,
        task_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取未处理的 timeline 事件

        Args:
            task_id: 用户会话 ID
            limit: 最大返回数量

        Returns:
            未处理的事件列表
        """
        cursor = self.conn.execute("""
            SELECT * FROM timeline
            WHERE task_id = ?
              AND processed = FALSE
            ORDER BY created_at ASC
            LIMIT ?
        """, (task_id, limit))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def mark_event_processed(
        self,
        event_id: int
    ) -> bool:
        """标记事件为已处理

        Args:
            event_id: 事件 ID（主键，不需要 task_id）

        Returns:
            bool: 是否成功
        """
        self.conn.execute("""
            UPDATE timeline
            SET processed = TRUE
            WHERE id = ?
        """, (event_id,))

        self.conn.commit()
        return True


# ==================== 工厂函数 ====================

async def get_db(workspace_root: str, agent_name: str) -> StorageManager:
    """获取 Agent 记忆数据库连接（统一入口）"""
    db_path = os.path.join(
        workspace_root,
        ".matrix",
        agent_name,
        "memory",
        "memory.db"
    )
    # 示例：MyWorld/workspace/.matrix/Tom/memory/memory.db

    storage = StorageManager(db_path)
    await storage.connect()
    storage.init_tables()

    return storage


# ==================== 高层 API ====================

async def search_entities_merged(
    workspace_root: str,
    agent_name: str,
    task_id: str,
    entity_name: str
) -> List[Dict[str, Any]]:
    """
    查询并合并 longterm + session profiles（高层 API）

    现在只需连接一个数据库，调用 StorageManager 的合并查询方法。

    Args:
        workspace_root: 工作区根目录
        agent_name: Agent 名称
        task_id: 用户会话 ID
        entity_name: 要查询的实体名称（精确匹配）

    Returns:
        合并后的 profile 列表，每个 profile 包含:
        - canonical_name: str (实体名称)
        - session_profile: dict or None (session 记录)
        - longterm_profile: dict or None (longterm 记录)
    """
    db = await get_db(workspace_root, agent_name)

    try:
        # 调用 StorageManager 的合并查询方法
        result = db.search_entities_merged(task_id, entity_name)
    finally:
        await db.close()

    return result


async def append_timeline_events(
    workspace_root: str,
    agent_name: str,
    task_id: str,
    events: List[Dict]
) -> None:
    """
    批量追加 timeline 事件（高层 API）

    Args:
        workspace_root: 工作区根目录
        agent_name: Agent 名称
        task_id: 用户会话 ID
        events: 事件对象列表，每个事件包含 {"event": str, "entities": List[str]}
    """
    db = await get_db(workspace_root, agent_name)

    try:
        for event_obj in events:
            event_text = event_obj.get("event", "")
            entities = event_obj.get("entities", [])
            db.append_timeline(task_id, event_text, entities)
    finally:
        await db.close()
