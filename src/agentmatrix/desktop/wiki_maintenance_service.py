"""
WikiMaintenanceService — 知识库后台维护服务

继承 AgenticServiceInterface，拥有自己的 MicroAgent 能力。
定期扫描所有知识库的源目录，自动接入新文件。
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .agentic_service import AgenticServiceInterface
from .skills.knowledge_base._shared import KBRegistry

logger = logging.getLogger(__name__)


class WikiMaintenanceService(AgenticServiceInterface):
    """知识库后台维护服务。

    定期扫描源目录，对 status='new' 的文件：
    1. CAS 声明（new → processing）
    2. 通过内部 MicroAgent 执行 ingest
    3. 标记结果（done / failed）
    """

    def __init__(self, runtime, scan_interval: int = 300, max_concurrent_ingests: int = 3):
        super().__init__(runtime)
        self._scan_interval = scan_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_tasks: set = set()
        self._semaphore = asyncio.Semaphore(max_concurrent_ingests)

    def _get_service_skills(self):
        return ["knowledge_base", "file"]

    # ==================== 生命周期 ====================

    async def start(self):
        if self._running:
            return
        try:
            await self._recover_processing_files()
        except Exception as e:
            logger.error(f"Recovery failed (non-fatal): {e}")
        self._running = True
        self._task = asyncio.create_task(self._loop())
        self.echo(">>> WikiMaintenanceService started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        if self._active_tasks:
            for t in list(self._active_tasks):
                t.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_tasks, return_exceptions=True),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                pass
            self._active_tasks.clear()
        self.echo(">>> WikiMaintenanceService stopped")

    async def _recover_processing_files(self):
        """启动时将卡在 processing 的文件重置为 new。"""
        wiki_base = self._runtime.paths.wiki_dir
        if not wiki_base.exists():
            return
        for name in KBRegistry.list_all(wiki_base):
            ns = KBRegistry.get(name)
            if ns is None:
                try:
                    ns = await KBRegistry.get_or_create(name, wiki_base)
                except Exception as e:
                    logger.warning(f"Failed to load knowledge base '{name}' during recovery: {e}")
                    continue
            try:
                await ns.db.reset_processing_files()
            except Exception as e:
                logger.error(f"Recovery failed for knowledge base '{name}': {e}")

    # ==================== 主循环 ====================

    async def _loop(self):
        while self._running:
            try:
                await self._scan_and_dispatch()
                await asyncio.sleep(self._scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WikiMaintenanceService error: {e}")
                await asyncio.sleep(self._scan_interval)

    # ==================== 扫描与分发 ====================

    async def _scan_and_dispatch(self):
        wiki_base = self._runtime.paths.wiki_dir
        if not wiki_base.exists():
            return

        kbs = KBRegistry.list_all(wiki_base)
        for name in kbs:
            ns = KBRegistry.get(name)
            if ns is None:
                try:
                    ns = await KBRegistry.get_or_create(name, wiki_base)
                except Exception as e:
                    logger.error(f"Failed to load knowledge base '{name}': {e}")
                    continue

            if not ns.wiki_manager.has_schema():
                continue

            await self._scan_kb(name, ns)

    async def _scan_kb(self, kb_name: str, ns):
        sources = await ns.db.get_all_sources()
        for src in sources:
            if not src.get("auto_scan", 1):
                continue
            abs_path = src["path"]
            if not Path(abs_path).exists():
                continue

            try:
                await ns.db.scan_source_directory(src["id"], abs_path)
            except Exception as e:
                logger.error(f"Scan failed for {abs_path}: {e}")
                continue

            unprocessed = await ns.db.get_unprocessed_files(src["id"])
            for file_row in unprocessed:
                claimed = await ns.db.claim_file(file_row["id"])
                if not claimed:
                    continue
                t = asyncio.create_task(
                    self._dispatch_ingest(kb_name, file_row, src)
                )
                self._active_tasks.add(t)
                t.add_done_callback(self._active_tasks.discard)

    # ==================== 接入任务 ====================

    async def _dispatch_ingest(self, kb_name: str, file_row: dict, source: dict):
        async with self._semaphore:
            await self._do_ingest(kb_name, file_row, source)

    async def _do_ingest(self, kb_name: str, file_row: dict, source: dict):
        source_root = Path(source["path"]).resolve()
        abs_path = source_root / file_row["rel_path"]
        resolved = abs_path.resolve()
        file_id = file_row["id"]

        if not resolved.is_relative_to(source_root):
            logger.warning(f"Path traversal blocked: {file_row['rel_path']}")
            ns = KBRegistry.get(kb_name)
            if ns:
                try:
                    await ns.db.mark_file_status(file_id, "failed")
                except Exception:
                    pass
            return

        abs_path = str(resolved)

        try:
            ns = KBRegistry.get(kb_name)
            if not ns:
                raise RuntimeError(f"知识库 '{kb_name}' not found")

            schema = ns.wiki_manager.read_schema()

            safe_path = abs_path.replace("\n", " ").replace("\r", "").replace('"', '\\"').replace("'", "\\'")[:500]
            safe_kb = kb_name.replace("\n", " ").replace("\r", "").replace('"', '\\"').replace("'", "\\'")[:100]

            result = await self.execute(
                task=(
                    f"将文件接入知识库。\n\n"
                    f"文件路径: {safe_path}\n"
                    f"知识库: {safe_kb}\n\n"
                    f"请调用 ingest_source(source_path=\"{safe_path}\", kb_name=\"{safe_kb}\") 完成接入。"
                ),
                system_prompt=(
                    f"你是一个知识提取助手。你的任务是将指定文件接入知识库。\n\n"
                    f"【知识库 Schema】\n{schema or '（暂无 Schema）'}\n\n"
                    f"执行 ingest_source 后，返回执行结果摘要。"
                ),
                name=f"ingest-{kb_name}-{file_row['rel_path']}",
            )

            if result is None:
                raise RuntimeError("MicroAgent returned None result")

            logger.info(f"Ingested {abs_path} into {kb_name}")

        except Exception as e:
            logger.error(f"Ingest failed for {abs_path}: {e}")
            ns = KBRegistry.get(kb_name)
            if ns:
                try:
                    await ns.db.mark_file_status(file_id, "failed")
                except Exception:
                    pass
            return

        try:
            await ns.db.mark_file_status(file_id, "done")
        except Exception as e:
            logger.warning(f"Failed to mark file done: {e}")

        try:
            await ns.db.update_source_timestamps(source["id"], processed=True)
        except Exception as e:
            logger.warning(f"Failed to update source timestamps: {e}")