"""
Knowledge Base — 共享基础设施

KnowledgeDB: SQLite 数据库管理（aiosqlite + WAL）
WikiManager: Wiki 文件系统 + 数据库协调
KBInstance: 知识库数据实例
KBRegistry: 知识库注册表（类级别单例）
resolve_user_path: 用户路径解析
"""

import os
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
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS source_files (
                id                INTEGER PRIMARY KEY,
                source_id         INTEGER REFERENCES sources(id) ON DELETE CASCADE,
                rel_path          TEXT NOT NULL,
                mtime             TEXT,
                size              INTEGER,
                last_ingested_at  TEXT,
                ingested_mtime    TEXT,
                created_at        TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
                UNIQUE(source_id, rel_path)
            )
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_files_source
            ON source_files(source_id)
        """)
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_files_mtime
            ON source_files(source_id, mtime)
        """)
        await self._conn.commit()
        # 迁移：为旧表补缺失的列
        cursor = await self._conn.execute("PRAGMA table_info(source_files)")
        columns = {row["name"] for row in await cursor.fetchall()}
        for col_name, col_def in [
            ("mtime", "TEXT"),
            ("size", "INTEGER"),
            ("last_ingested_at", "TEXT"),
            ("ingested_mtime", "TEXT"),
        ]:
            if col_name not in columns:
                await self._conn.execute(
                    f"ALTER TABLE source_files ADD COLUMN {col_name} {col_def}"
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

    async def check_and_prepare_source_path(self, abs_path: str):
        """检查路径冲突并预处理。
        返回 None 表示无冲突（已准备好），
        返回字符串表示冲突原因（调用方应拒绝）。
        如果新路径是已有 source 的父目录，会自动删除被覆盖的子 source。"""
        abs_resolved = Path(abs_path).resolve()
        cursor = await self._conn.execute("SELECT id, path, source_type FROM sources")
        sources = [dict(r) for r in await cursor.fetchall()]

        child_ids = []
        for src in sources:
            src_resolved = Path(src["path"]).resolve()
            # 完全相同
            if abs_resolved == src_resolved:
                return f"该路径已注册 (ID: {src['id']})"
            # 被 parent 覆盖
            try:
                abs_resolved.relative_to(src_resolved)
                return f"已被已有 source 覆盖: {src['path']}"
            except ValueError:
                pass
            # 是已有 source 的父目录 → 记录待删除的 child
            try:
                src_resolved.relative_to(abs_resolved)
                child_ids.append(src["id"])
            except ValueError:
                pass

        if child_ids:
            for cid in child_ids:
                await self._conn.execute("DELETE FROM source_files WHERE source_id = ?", (cid,))
                await self._conn.execute("DELETE FROM sources WHERE id = ?", (cid,))
            await self._conn.commit()
        return None

    async def get_all_sources(self) -> list:
        cursor = await self._conn.execute("SELECT * FROM sources ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_source_by_id(self, source_id: int) -> Optional[dict]:
        cursor = await self._conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_source_timestamps(self, source_id: int):
        now = datetime.now().isoformat()
        await self._conn.execute(
            "UPDATE sources SET last_scanned = ? WHERE id = ?", (now, source_id)
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
            "SELECT rel_path, mtime, size FROM source_files WHERE source_id = ?",
            (source_id,),
        )
        existing_rows = [dict(r) for r in await cursor.fetchall()]
        existing_map = {r["rel_path"]: r for r in existing_rows}

        new_or_changed = []
        current_rels = set()
        for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
            # 跳过隐藏目录（.git, .DS_Store 等）
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for fname in filenames:
                # 跳过 dotfile（.DS_Store, ._, .gitignore 等系统元数据）
                if fname.startswith('.'):
                    continue
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
                            "UPDATE source_files SET mtime = ?, size = ? WHERE source_id = ? AND rel_path = ?",
                            (mtime, size, source_id, rel),
                        )
                        new_or_changed.append({"rel_path": rel, "mtime": mtime, "size": size, "status": "changed"})
                else:
                    await self._conn.execute(
                        """INSERT OR IGNORE INTO source_files (source_id, rel_path, mtime, size)
                           VALUES (?, ?, ?, ?)""",
                        (source_id, rel, mtime, size),
                    )
                    new_or_changed.append({"rel_path": rel, "mtime": mtime, "size": size, "status": "new"})

        for existing_rel in existing_map:
            if existing_rel not in current_rels:
                await self._conn.execute(
                    "DELETE FROM source_files WHERE source_id = ? AND rel_path = ?",
                    (source_id, existing_rel),
                )

        await self._conn.commit()
        await self.update_source_timestamps(source_id)
        return new_or_changed

    async def get_needs_ingest_files(self, source_id: int) -> list:
        """返回需要 ingest 的文件：从未 ingest 过，或 mtime 与上次 ingest 时不一致。

        用 ingested_mtime（ingest 时的实际 mtime）与当前 mtime 比较，
        避免文件在 ingest 期间被修改后修改丢失的问题。
        """
        cursor = await self._conn.execute(
            """SELECT * FROM source_files
               WHERE source_id = ?
                 AND (ingested_mtime IS NULL OR ingested_mtime != mtime)""",
            (source_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def mark_ingested(self, file_id: int, mtime: str):
        """标记文件已成功 ingest，记录 ingest 时的 mtime。

        mtime 参数是 ingest 时文件的 mtime（来自 file_row["mtime"]），
        下次 get_needs_ingest_files 会用它与当前 mtime 比较。
        """
        now = datetime.now().isoformat()
        await self._conn.execute(
            "UPDATE source_files SET last_ingested_at = ?, ingested_mtime = ? WHERE id = ?",
            (now, mtime, file_id),
        )
        await self._safe_commit()

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

    def get_tree_summary(self) -> str:
        """生成 wiki 目录的精简摘要（top-level overview）。

        返回格式：
        - 列出每个 top-level 目录
        - 子项 ≤5 个时直接展开列出
        - 子项 >5 个时显示 "N 个文件, M 个子目录" 摘要
        - 跳过 _ 开头的系统目录和 raw/
        """
        if not self.wiki_root.exists():
            return "（知识库目录不存在）"

        SKIP_DIRS = {"raw", "log_archive", "__pycache__"}

        def _summarize_dir(path: Path) -> str:
            """返回目录下直接子项的摘要或列表。"""
            try:
                entries = sorted(path.iterdir())
            except (PermissionError, OSError):
                return "  (无法读取)"

            files = [e.name for e in entries
                     if e.is_file() and not e.name.startswith("_")
                     and e.suffix == ".md"
                     and e.name not in ("index.md", "log.md")]
            dirs = [e for e in entries
                    if e.is_dir() and e.name not in SKIP_DIRS
                    and not e.name.startswith("_")]

            total = len(files) + len(dirs)
            if total == 0:
                return "  (空)"
            if total <= 5:
                items = [d.name + "/" for d in dirs] + files
                return "\n".join(f"  - {item}" for item in items)

            parts = []
            if files:
                parts.append(f"{len(files)} 个文件")
            if dirs:
                parts.append(f"{len(dirs)} 个子目录")
            return f"  ({', '.join(parts)})"

        # Top-level directories
        try:
            top_dirs = sorted(
                d for d in self.wiki_root.iterdir()
                if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith("_")
            )
        except (PermissionError, OSError):
            top_dirs = []

        if not top_dirs:
            return "（知识库暂无页面目录）"

        lines = []
        for d in top_dirs:
            sub = _summarize_dir(d)
            lines.append(f"{d.name}/")
            lines.append(sub)

        lines.append("")
        lines.append("（以上仅为顶层目录概览，子目录内容未展开。用 list_dir 查看具体目录内容。）")
        return "\n".join(lines)

