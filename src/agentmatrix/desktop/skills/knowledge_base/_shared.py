"""
Knowledge Base — 共享基础设施

KnowledgeDB: SQLite 数据库管理（aiosqlite + WAL）
WikiManager: Wiki 文件系统 + 数据库协调
KBInstance: 知识库数据实例
KBRegistry: 知识库注册表（类级别单例）
resolve_user_path: 用户路径解析
"""

import os
import json
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

import aiosqlite

logger = logging.getLogger(__name__)


def resolve_user_path(path: str) -> Path:
    expanded = os.path.expanduser(path)
    return Path(expanded).resolve()


BINARY_EXTENSIONS_WARN = {
    ".pdf", ".doc", ".docx", ".pptx", ".xlsx", ".xls",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".ico", ".webp", ".svgz",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".dmg", ".iso",
}


class KnowledgeDB:
    """知识库 SQLite 数据库管理（aiosqlite + WAL 模式）"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(self.db_path))
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.commit()
        self._conn = conn
        await self.create_tables()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _safe_commit(self):
        try:
            await self._conn.commit()
        except Exception as commit_err:
            try:
                await self._conn.rollback()
            except Exception:
                logger.warning(f"Rollback also failed after commit error: {commit_err}")
            raise commit_err

    async def create_tables(self):
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id          INTEGER PRIMARY KEY,
                path        TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                source_type TEXT DEFAULT 'directory',
                auto_scan   INTEGER DEFAULT 1,
                last_scanned  TEXT,
                last_processed TEXT,
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS source_files (
                id          INTEGER PRIMARY KEY,
                source_id   INTEGER REFERENCES sources(id) ON DELETE CASCADE,
                rel_path    TEXT NOT NULL,
                mtime       TEXT,
                size        INTEGER,
                status      TEXT DEFAULT 'new',
                wiki_refs   TEXT DEFAULT '[]',
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                UNIQUE(source_id, rel_path)
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS wiki_pages (
                id          INTEGER PRIMARY KEY,
                rel_path    TEXT UNIQUE NOT NULL,
                title       TEXT,
                summary     TEXT,
                category    TEXT,
                source_refs TEXT DEFAULT '[]',
                created_at  TEXT,
                updated_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )
        """)
        await self._migrate_source_files()
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_files_source
            ON source_files(source_id)
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_files_status
            ON source_files(source_id, status)
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_files_mtime
            ON source_files(source_id, mtime)
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wiki_pages_category
            ON wiki_pages(category)
        """)
        await self._conn.commit()

    async def _migrate_source_files(self):
        """迁移旧的 processed 列到新的 status 列（如果存在）"""
        try:
            await self._conn.execute("SELECT processed FROM source_files LIMIT 1")
        except aiosqlite.OperationalError:
            return
        try:
            await self._conn.execute(
                "ALTER TABLE source_files ADD COLUMN status TEXT DEFAULT 'new'"
            )
        except aiosqlite.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
            return
        await self._conn.execute(
            "UPDATE source_files SET status = CASE WHEN processed = 1 THEN 'done' ELSE 'new' END"
        )
        await self._conn.commit()

    # ==================== sources ====================

    async def register_source(self, path: str, description: str = "",
                               source_type: str = "directory") -> int:
        await self._conn.execute(
            """INSERT OR IGNORE INTO sources (path, description, source_type)
               VALUES (?, ?, ?)""",
            (path, description, source_type),
        )
        await self._conn.commit()
        row = await self._conn.execute(
            "SELECT id FROM sources WHERE path = ?", (path,)
        )
        result = await row.fetchone()
        if result:
            return result["id"]
        return -1

    async def get_all_sources(self) -> list:
        cursor = await self._conn.execute("SELECT * FROM sources ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_source_by_id(self, source_id: int) -> Optional[dict]:
        cursor = await self._conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_source_timestamps(self, source_id: int,
                                        scanned: bool = False,
                                        processed: bool = False):
        now = datetime.now().isoformat()
        sets = []
        params = []
        if scanned:
            sets.append("last_scanned = ?")
            params.append(now)
        if processed:
            sets.append("last_processed = ?")
            params.append(now)
        if not sets:
            return
        params.append(source_id)
        await self._conn.execute(
            f"UPDATE sources SET {', '.join(sets)} WHERE id = ?", params
        )
        await self._conn.commit()

    async def delete_source(self, source_id: int):
        await self._conn.execute("DELETE FROM source_files WHERE source_id = ?", (source_id,))
        await self._conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        await self._conn.commit()

    # ==================== source_files ====================

    async def scan_source_directory(self, source_id: int, abs_path: str) -> list:
        root = Path(abs_path)
        if not root.is_dir():
            return []

        source_row = await self.get_source_by_id(source_id)
        if not source_row:
            return []

        cursor = await self._conn.execute(
            "SELECT rel_path, mtime, size, status FROM source_files WHERE source_id = ?",
            (source_id,),
        )
        existing_rows = [dict(r) for r in await cursor.fetchall()]
        existing_map = {r["rel_path"]: r for r in existing_rows}

        new_or_changed = []
        current_rels = set()
        for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if fpath.suffix.lower() in BINARY_EXTENSIONS_WARN:
                    continue
                try:
                    stat = fpath.stat()
                except OSError:
                    continue
                rel = str(fpath.relative_to(root))
                current_rels.add(rel)
                mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
                size = stat.st_size
                if rel in existing_map:
                    old = existing_map[rel]
                    if old["mtime"] != mtime or old["size"] != size:
                        await self._conn.execute(
                            "UPDATE source_files SET mtime = ?, size = ?, status = 'new' WHERE source_id = ? AND rel_path = ? AND status IN ('done', 'new')",
                            (mtime, size, source_id, rel),
                        )
                        new_or_changed.append({"rel_path": rel, "mtime": mtime, "size": size, "status": "changed"})
                else:
                    await self._conn.execute(
                        """INSERT OR IGNORE INTO source_files (source_id, rel_path, mtime, size, status)
                           VALUES (?, ?, ?, ?, 'new')""",
                        (source_id, rel, mtime, size),
                    )
                    new_or_changed.append({"rel_path": rel, "mtime": mtime, "size": size, "status": "new"})

        for existing_rel in existing_map:
            if existing_rel not in current_rels:
                await self._conn.execute(
                    "DELETE FROM source_files WHERE source_id = ? AND rel_path = ? AND status != 'processing'",
                    (source_id, existing_rel),
                )

        await self._conn.commit()
        await self.update_source_timestamps(source_id, scanned=True)
        return new_or_changed

    async def get_unprocessed_files(self, source_id: Optional[int] = None) -> list:
        if source_id is not None:
            cursor = await self._conn.execute(
                "SELECT * FROM source_files WHERE source_id = ? AND status = 'new'",
                (source_id,),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM source_files WHERE status = 'new'"
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_changed_files(self, source_id: int) -> list:
        cursor = await self._conn.execute(
            """SELECT sf.* FROM source_files sf
               JOIN sources s ON sf.source_id = s.id
               WHERE s.id = ? AND (sf.status = 'new' OR sf.mtime > s.last_processed)""",
            (source_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def mark_file_status(self, file_id: int, status: str, wiki_refs: Optional[list] = None) -> bool:
        if wiki_refs is not None:
            refs_json = json.dumps(wiki_refs, ensure_ascii=False)
            cursor = await self._conn.execute(
                "UPDATE source_files SET status = ?, wiki_refs = ? WHERE id = ? AND status = 'processing'",
                (status, refs_json, file_id),
            )
        else:
            cursor = await self._conn.execute(
                "UPDATE source_files SET status = ? WHERE id = ? AND status = 'processing'",
                (status, file_id),
            )
        await self._safe_commit()
        return cursor.rowcount > 0

    async def claim_file(self, file_id: int) -> bool:
        cursor = await self._conn.execute(
            "UPDATE source_files SET status = 'processing' WHERE id = ? AND status = 'new'",
            (file_id,),
        )
        await self._safe_commit()
        return cursor.rowcount > 0

    async def reset_processing_files(self):
        """将所有卡在 processing 的文件重置为 new（用于崩溃恢复）。"""
        await self._conn.execute(
            "UPDATE source_files SET status = 'new' WHERE status = 'processing'"
        )
        await self._safe_commit()

    async def claim_and_mark_done(self, file_id: int, wiki_refs: Optional[list] = None) -> bool:
        """原子操作：从 new 直接转为 done（用于直接 ingest，跳过 processing 中间态）。"""
        if wiki_refs is not None:
            refs_json = json.dumps(wiki_refs, ensure_ascii=False)
            cursor = await self._conn.execute(
                "UPDATE source_files SET status = 'done', wiki_refs = ? WHERE id = ? AND status = 'new'",
                (refs_json, file_id),
            )
        else:
            cursor = await self._conn.execute(
                "UPDATE source_files SET status = 'done' WHERE id = ? AND status = 'new'",
                (file_id,),
            )
        await self._safe_commit()
        return cursor.rowcount > 0

    async def get_source_files(self, source_id: int) -> list:
        cursor = await self._conn.execute(
            "SELECT * FROM source_files WHERE source_id = ? ORDER BY rel_path",
            (source_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_source_files_by_path(self, abs_path: str) -> list:
        results = []
        cursor = await self._conn.execute("SELECT * FROM sources")
        sources = [dict(r) for r in await cursor.fetchall()]
        abs_path_obj = Path(abs_path).resolve()

        for src in sources:
            src_path = Path(src["path"]).resolve()
            if src["source_type"] == "file":
                if abs_path_obj == src_path:
                    cursor2 = await self._conn.execute(
                        "SELECT * FROM source_files WHERE source_id = ?", (src["id"],)
                    )
                    rows = await cursor2.fetchall()
                    results.extend(dict(r) for r in rows)
            else:
                try:
                    rel = str(abs_path_obj.relative_to(src_path))
                except ValueError:
                    continue
                cursor2 = await self._conn.execute(
                    "SELECT * FROM source_files WHERE source_id = ? AND rel_path = ?",
                    (src["id"], rel),
                )
                rows = await cursor2.fetchall()
                results.extend(dict(r) for r in rows)
        return results

    # ==================== wiki_pages ====================

    async def upsert_page(self, rel_path: str, title: str = "",
                          summary: str = "", category: str = "",
                          source_refs: Optional[list] = None) -> int:
        now = datetime.now().isoformat()
        new_refs = source_refs or []

        cursor = await self._conn.execute(
            "SELECT id, source_refs FROM wiki_pages WHERE rel_path = ?", (rel_path,)
        )
        row = await cursor.fetchone()

        merged_refs = new_refs
        if row:
            try:
                old_refs = json.loads(row["source_refs"]) if row["source_refs"] else []
            except (json.JSONDecodeError, TypeError):
                old_refs = []
            seen = set()
            merged_refs = []
            for ref in old_refs + new_refs:
                if ref not in seen:
                    seen.add(ref)
                    merged_refs.append(ref)

        refs_json = json.dumps(merged_refs, ensure_ascii=False)

        await self._conn.execute(
            """INSERT INTO wiki_pages (rel_path, title, summary, category, source_refs, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(rel_path) DO UPDATE SET
                 title = excluded.title,
                 summary = excluded.summary,
                 category = excluded.category,
                 source_refs = excluded.source_refs,
                 updated_at = excluded.updated_at""",
            (rel_path, title, summary, category, refs_json, now, now),
        )
        await self._conn.commit()

        cursor = await self._conn.execute(
            "SELECT id FROM wiki_pages WHERE rel_path = ?", (rel_path,)
        )
        row = await cursor.fetchone()
        return row["id"] if row else -1

    async def get_page(self, rel_path: str) -> Optional[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM wiki_pages WHERE rel_path = ?", (rel_path,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_pages_by_category(self, category: str) -> list:
        cursor = await self._conn.execute(
            "SELECT * FROM wiki_pages WHERE category = ? ORDER BY title", (category,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_all_pages(self) -> list:
        cursor = await self._conn.execute("SELECT * FROM wiki_pages ORDER BY category, title")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def delete_page(self, rel_path: str):
        await self._conn.execute("DELETE FROM wiki_pages WHERE rel_path = ?", (rel_path,))
        await self._conn.commit()

    async def get_stats(self) -> dict:
        cursor = await self._conn.execute(
            "SELECT category, COUNT(*) as cnt FROM wiki_pages GROUP BY category"
        )
        rows = await cursor.fetchall()
        stats = {}
        total = 0
        for r in rows:
            cat = r["category"] or "(uncategorized)"
            stats[cat] = r["cnt"]
            total += r["cnt"]
        stats["total"] = total
        return stats

    async def search_pages(self, keywords: list) -> list:
        if not keywords:
            return []
        conditions = []
        params = []
        for kw in keywords:
            escaped = kw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append("(title LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\' OR rel_path LIKE ? ESCAPE '\\')")
            pattern = f"%{escaped}%"
            params.extend([pattern, pattern, pattern])
        where = " OR ".join(conditions)
        cursor = await self._conn.execute(
            f"SELECT * FROM wiki_pages WHERE {where} ORDER BY category, title",
            params,
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ==================== Knowledge Base ====================

@dataclass
class KBInstance:
    name: str
    wiki_root: Path
    db: KnowledgeDB
    wiki_manager: 'WikiManager'


class KBRegistry:
    _instances: Dict[str, KBInstance] = {}
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def get_or_create(cls, name: str, base_dir: Path) -> KBInstance:
        async with cls._lock:
            if name in cls._instances:
                return cls._instances[name]

            wiki_root = base_dir / name
            wiki_root.mkdir(parents=True, exist_ok=True)

            db_path = wiki_root / "knowledge.db"
            db = KnowledgeDB(db_path=db_path)
            await db.connect()

            wiki_manager = WikiManager(wiki_root, db)
            wiki_manager.ensure_structure()

            ns = KBInstance(
                name=name,
                wiki_root=wiki_root,
                db=db,
                wiki_manager=wiki_manager,
            )
            cls._instances[name] = ns
            return ns

    @classmethod
    def get(cls, name: str) -> Optional[KBInstance]:
        return cls._instances.get(name)

    @classmethod
    def list_all(cls, base_dir: Path) -> List[str]:
        names = []
        if not base_dir.is_dir():
            return names
        try:
            for child in sorted(base_dir.iterdir()):
                if child.is_dir() and (child / "knowledge.db").exists():
                    names.append(child.name)
        except (PermissionError, OSError):
            pass
        for name in cls._instances:
            if name not in names:
                names.append(name)
        return sorted(names)

    @classmethod
    async def shutdown_all(cls):
        for ns in cls._instances.values():
            await ns.db.close()
        cls._instances.clear()


# ==================== 默认文件内容 ====================

DEFAULT_INDEX = """\
# 知识库目录

> 此文件由系统自动维护，请勿手动编辑。

*知识库尚无页面。*
"""

DEFAULT_LOG = """\
# 知识库变更日志

> 此文件记录知识库的变更历史。超过 50 条时旧记录会自动归档到 log_archive/。

"""


class WikiManager:
    """Wiki 文件系统 + 数据库协调管理器"""

    LOG_MAX_ENTRIES = 50

    def __init__(self, wiki_root: Path, db: KnowledgeDB):
        self.wiki_root = wiki_root
        self.db = db

    # ==================== 目录结构 ====================

    def ensure_structure(self):
        for subdir in ["log_archive", "raw"]:
            (self.wiki_root / subdir).mkdir(parents=True, exist_ok=True)

        defaults = {
            "index.md": DEFAULT_INDEX,
            "log.md": DEFAULT_LOG,
        }
        for fname, content in defaults.items():
            fpath = self.wiki_root / fname
            if not fpath.exists():
                fpath.write_text(content, encoding="utf-8")

    def init_with_schema(self, schema_content: str):
        schema_path = self.wiki_root / "_schema.md"
        schema_path.write_text(schema_content, encoding="utf-8")

    # ==================== index.md 自动生成 ====================

    async def regenerate_index(self):
        if not self.wiki_root.is_dir():
            return

        pages = await self.db.get_all_pages()
        stats = await self.db.get_stats()

        categories = set()
        for child in self.wiki_root.iterdir():
            if child.is_dir() and not child.name.startswith("_") and child.name not in ("log_archive", "raw"):
                categories.add(child.name)

        lines = [
            "# 知识库目录\n",
            "> 此文件由系统自动维护，请勿手动编辑。\n",
        ]

        for cat_key in sorted(categories):
            cat_pages = [p for p in pages if p.get("category") == cat_key]
            lines.append(f"\n## {cat_key}/\n")
            if cat_pages:
                for p in cat_pages:
                    summary = p.get("summary", "") or ""
                    summary_line = f" — {summary}" if summary else ""
                    lines.append(f"- [{p.get('title', p['rel_path'])}]({p['rel_path']}){summary_line}")
            else:
                lines.append("> 暂无页面\n")

        uncategorized = [p for p in pages if p.get("category") not in categories]
        if uncategorized:
            lines.append("\n## 其他\n")
            for p in uncategorized:
                summary = p.get("summary", "") or ""
                summary_line = f" — {summary}" if summary else ""
                lines.append(f"- [{p.get('title', p['rel_path'])}]({p['rel_path']}){summary_line}")

        total = stats.get("total", 0)
        lines.append(f"\n---\n*共 {total} 个页面*")

        index_path = self.wiki_root / "index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")

    # ==================== log.md ====================

    def append_log(self, entry_type: str, title: str, details: str = ""):
        log_path = self.wiki_root / "log.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        entry = f"\n## [{timestamp}] {entry_type} | {title}"
        if details:
            entry += f"\n\n{details}"

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

        self._check_log_archive()

    def _check_log_archive(self):
        log_path = self.wiki_root / "log.md"
        if not log_path.exists():
            return
        content = log_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        entry_lines = [i for i, line in enumerate(lines) if line.startswith("## [")]
        if len(entry_lines) <= self.LOG_MAX_ENTRIES:
            return

        header_end = 0
        for i, line in enumerate(lines):
            if line.startswith("## ["):
                header_end = i
                break

        keep_from = entry_lines[-self.LOG_MAX_ENTRIES]
        archive_start = max(header_end, 0)
        archive_lines = lines[archive_start:keep_from]
        recent_lines = lines[:archive_start] + lines[keep_from:]

        now = datetime.now()
        archive_dir = self.wiki_root / "log_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{now.strftime('%Y-%m')}.md"

        archive_content = "\n".join(archive_lines)
        if archive_path.exists():
            existing = archive_path.read_text(encoding="utf-8")
            archive_content = existing + "\n\n" + archive_content

        tmp_path = archive_path.with_suffix(".tmp")
        tmp_path.write_text(archive_content, encoding="utf-8")
        os.replace(str(tmp_path), str(archive_path))

        recent_content = "\n".join(recent_lines)
        tmp_log = log_path.with_suffix(".tmp")
        tmp_log.write_text(recent_content, encoding="utf-8")
        os.replace(str(tmp_log), str(log_path))

    # ==================== schema ====================

    def read_schema(self) -> str:
        schema_path = self.wiki_root / "_schema.md"
        if schema_path.exists():
            return schema_path.read_text(encoding="utf-8")
        return ""

    def write_schema(self, content: str):
        schema_path = self.wiki_root / "_schema.md"
        schema_path.write_text(content, encoding="utf-8")

    def has_schema(self) -> bool:
        schema_path = self.wiki_root / "_schema.md"
        if not schema_path.exists():
            return False
        content = schema_path.read_text(encoding="utf-8").strip()
        return bool(content)

    # ==================== 页面操作 ====================

    def _safe_path(self, rel_path: str) -> Path:
        p = (self.wiki_root / rel_path).resolve()
        if not p.is_relative_to(self.wiki_root.resolve()):
            raise ValueError(f"Path traversal blocked: {rel_path}")
        return p

    def write_page(self, rel_path: str, content: str):
        page_path = self._safe_path(rel_path)
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(content, encoding="utf-8")

    def read_page(self, rel_path: str) -> Optional[str]:
        page_path = self._safe_path(rel_path)
        if page_path.exists():
            return page_path.read_text(encoding="utf-8")
        return None

    def page_exists(self, rel_path: str) -> bool:
        return self._safe_path(rel_path).exists()

    def list_page_files(self) -> list:
        pages = []
        for md_file in self.wiki_root.rglob("*.md"):
            if md_file.name.startswith("_"):
                continue
            if md_file.parent.name == "log_archive":
                continue
            if md_file.name == "log.md" or md_file.name == "index.md":
                continue
            pages.append(str(md_file.relative_to(self.wiki_root)))
        return sorted(pages)

    async def create_page(self, rel_path: str, content: str, title: str = "",
                          summary: str = "", category: str = "",
                          source_refs: Optional[list] = None):
        self.write_page(rel_path, content)
        try:
            await self.db.upsert_page(
                rel_path=rel_path,
                title=title,
                summary=summary,
                category=category,
                source_refs=source_refs,
            )
        except Exception:
            try:
                page_path = self._safe_path(rel_path)
                if page_path.exists():
                    page_path.unlink()
            except (ValueError, OSError):
                pass
            raise
        await self.regenerate_index()

    async def delete_page(self, rel_path: str):
        page_path = self._safe_path(rel_path)
        if page_path.exists():
            page_path.unlink()
        await self.db.delete_page(rel_path)
        await self.regenerate_index()