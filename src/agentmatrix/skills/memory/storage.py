"""
SQLite 数据库管理器（支持 WAL 模式）

管理两个数据库文件：
- global_memory.db: Agent 级别的全局实体记忆
- session_memory.db: User session 级别的实体记忆 + timeline
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

    def init_global_tables(self):
        """初始化全局数据库表结构（Entity_Profiles）"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS Entity_Profiles (
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
            CREATE INDEX IF NOT EXISTS idx_name
            ON Entity_Profiles(canonical_name)
        """)

        self.conn.commit()

    def init_session_tables(self):
        """初始化会话数据库表结构（Entity_Profiles + Timeline_Log）"""
        # Session 实体档案表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS Entity_Profiles (
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
            CREATE INDEX IF NOT EXISTS idx_name
            ON Entity_Profiles(canonical_name)
        """)

        # Timeline 日志表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS Timeline_Log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_text TEXT NOT NULL,
                entities JSON,
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed
            ON Timeline_Log(processed)
        """)

        self.conn.commit()

    # ==================== CRUD 操作 ====================

    def insert_entity(self, uid: str, canonical_name: str, aliases: list,
                      summary: str, profile_text: str) -> bool:
        """插入实体档案"""
        try:
            import json
            self.conn.execute("""
                INSERT INTO Entity_Profiles (uid, canonical_name, aliases, summary, profile_text)
                VALUES (?, ?, ?, ?, ?)
            """, (uid, canonical_name, json.dumps(aliases), summary, profile_text))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def update_entity(self, uid: str, summary: str = None, profile_text: str = None,
                      aliases: list = None) -> bool:
        """更新实体档案"""
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
            UPDATE Entity_Profiles
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE uid = ?
        """, params)

        self.conn.commit()
        return True

    def search_entities(self, entity_name: str) -> List[Dict[str, Any]]:
        """
        搜索实体档案（精确匹配 canonical_name 或 aliases）

        查询原则：
        - canonical_name 完全相等，或
        - entity_name 是 aliases 之一（完全相等）

        Args:
            entity_name: 要查找的实体名称（精确匹配）

        Returns:
            匹配的实体档案列表（按更新时间倒序）
        """
        # 使用 JSON 函数精确匹配
        cursor = self.conn.execute("""
            SELECT DISTINCT * FROM Entity_Profiles
            WHERE canonical_name = ?
               OR EXISTS (
                   SELECT 1 FROM json_each(aliases)
                   WHERE json_each.value = ?
               )
            ORDER BY updated_at DESC
        """, (entity_name, entity_name))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_entity(self, uid: str) -> Optional[Dict[str, Any]]:
        """获取单个实体档案"""
        cursor = self.conn.execute("""
            SELECT * FROM Entity_Profiles WHERE uid = ?
        """, (uid,))

        row = cursor.fetchone()
        return dict(row) if row else None

    def append_timeline(self, event_text: str, entities: List[str] = None) -> int:
        """追加 timeline 日志

        Args:
            event_text: 事件描述文本
            entities: 实体列表（可选）

        Returns:
            int: 新记录的 ID
        """
        import json

        entities_json = json.dumps(entities) if entities else None

        cursor = self.conn.execute("""
            INSERT INTO Timeline_Log (event_text, entities, processed)
            VALUES (?, ?, FALSE)
        """, (event_text, entities_json))

        self.conn.commit()
        return cursor.lastrowid

    def fetch_unprocessed_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取未处理的 timeline 事件"""
        cursor = self.conn.execute("""
            SELECT * FROM Timeline_Log
            WHERE processed = FALSE
            ORDER BY created_at ASC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def mark_event_processed(self, event_id: int) -> bool:
        """标记事件为已处理"""
        self.conn.execute("""
            UPDATE Timeline_Log
            SET processed = TRUE
            WHERE id = ?
        """, (event_id,))

        self.conn.commit()
        return True


# ==================== 工厂函数 ====================

async def get_global_db(workspace_root: str, agent_name: str) -> StorageManager:
    """获取全局记忆数据库连接"""
    db_path = os.path.join(
        workspace_root,
        ".matrix",
        agent_name,
        "memory",
        "global_memory.db"
    )
    # 示例：MyWorld/workspace/.matrix/Tom/memory/global_memory.db

    storage = StorageManager(db_path)
    await storage.connect()
    storage.init_global_tables()

    return storage


async def get_session_db(workspace_root: str, agent_name: str,
                        user_session_id: str) -> StorageManager:
    """获取会话记忆数据库连接"""
    db_path = os.path.join(
        workspace_root,
        ".matrix",
        agent_name,
        "memory",
        user_session_id,
        "session_memory.db"
    )
    # 示例：MyWorld/workspace/.matrix/Tom/memory/session_abc123/session_memory.db

    storage = StorageManager(db_path)
    await storage.connect()
    storage.init_session_tables()

    return storage


# ==================== 高层 API ====================

async def search_entities_merged(
    workspace_root: str,
    agent_name: str,
    session_id: str,
    entity_name: str
) -> List[Dict[str, Any]]:
    """
    查询并合并 session + global profiles

    并发查询两个数据库，然后按 canonical_name 合并结果。

    Args:
        workspace_root: 工作区根目录
        agent_name: Agent 名称
        session_id: 用户会话 ID
        entity_name: 要查询的实体名称（精确匹配）

    Returns:
        合并后的 profile 列表，每个 profile 包含:
        - canonical_name: str (实体名称)
        - session_profile: dict or None (session 记录)
        - global_profile: dict or None (global 记录)
    """
    # 并发查询
    session_db = await get_session_db(workspace_root, agent_name, session_id)
    global_db = await get_global_db(workspace_root, agent_name)

    try:
        session_profiles = session_db.search_entities(entity_name)
        global_profiles = global_db.search_entities(entity_name)
    finally:
        await session_db.close()
        await global_db.close()

    # 按 canonical_name 合并
    merged = {}  # canonical_name -> {session, global}

    for p in session_profiles:
        name = p['canonical_name']
        if name not in merged:
            merged[name] = {'session': None, 'global': None}
        merged[name]['session'] = p

    for p in global_profiles:
        name = p['canonical_name']
        if name not in merged:
            merged[name] = {'session': None, 'global': None}
        merged[name]['global'] = p

    # 转换为列表
    result = []
    for name, profiles in merged.items():
        result.append({
            'canonical_name': name,
            'session_profile': profiles['session'],
            'global_profile': profiles['global']
        })

    return result


async def append_timeline_events(
    workspace_root: str,
    agent_name: str,
    session_id: str,
    events: List[Dict]
) -> None:
    """
    批量追加 timeline 事件

    Args:
        workspace_root: 工作区根目录
        agent_name: Agent 名称
        session_id: 用户会话 ID
        events: 事件对象列表，每个事件包含 {"event": str, "entities": List[str]}
    """
    session_db = await get_session_db(workspace_root, agent_name, session_id)
    try:
        for event_obj in events:
            event_text = event_obj.get("event", "")
            entities = event_obj.get("entities", [])
            session_db.append_timeline(event_text, entities)
    finally:
        await session_db.close()
