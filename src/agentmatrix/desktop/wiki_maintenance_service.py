"""
WikiMaintenanceService — 知识库后台维护服务

继承 AgenticServiceInterface，使用持久 ServiceWorker 池处理 ingest 任务。

## 工作模型

两种触发源，都最终产生 ServiceTask 投递到 ingest worker 池：

1. **周期 scan（普通优先级 priority=1）**
   `_loop`: 全量扫描所有 KB → 提交任务 → `gather` 等所有任务完成 → sleep(rest_interval)
   scan-then-wait 保证两次 scan 不重叠，且任务跑完才进 sleep。

2. **source_added 信号（高优先级 priority=0）**
   `_handle_source_added`: 扫描单个 source → fire-and-forget 提交任务（不 await）
   用户刚添加 source 时希望尽快处理，priority=0 让它跳过 scan 队列。

## 去重

全局 `_inflight: set[(kb_name, file_id)]` 防止同一文件被并发 ingest。
所有 submit 路径都先查 _inflight；on_success / on_error 都清理。
任务失败时不在 DB 标记 ingested，下次 scan 自动重选——天然重试。
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from .agentic_service import AgenticServiceInterface
from .ephemeral_whiteboard import EphemeralWhiteboard
from .service_worker import ServiceWorker, ServiceTask
from .skills.knowledge_base._shared import KBRegistry, BINARY_EXTENSIONS_WARN
from .skills.knowledge_base.prompts import KnowledgePrompts
from .signals import DataSignal

logger = logging.getLogger(__name__)


_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

_WIKI_TREE_RE = re.compile(r'<wiki-tree>.*?</wiki-tree>', re.DOTALL)


class WikiMaintenanceService(AgenticServiceInterface):
    """知识库后台维护服务。

    scan-then-wait + 全局去重 + source_added 高优先级。
    """

    def __init__(self, runtime, scan_interval: int = 300, max_concurrent_ingests: int = 3):
        super().__init__(runtime)
        self._scan_interval = scan_interval
        self._max_workers = max_concurrent_ingests
        self._ingest_workers: list[ServiceWorker] = []
        self._wb = EphemeralWhiteboard()
        # 全局去重：(kb_name, file_id) — 防止同一文件被并发 ingest
        self._inflight: set[tuple[str, int]] = set()
        # scan 周期互斥标志（_loop 和 trigger_scan 不能并发跑）
        self._scanning: bool = False

    def _get_service_skills(self):
        return ["knowledge_base.maintenance", "file", "basic_planning"]

    def get_status(self) -> dict:
        return {
            **super().get_status(),
            "scanning": self._scanning,
            "inflight": len(self._inflight),
        }

    @property
    def whiteboard_manager(self):
        return self._wb

    # ==================== Service 接口 ====================

    def get_actions(self):
        return [
            {"id": "trigger_scan", "name": "Trigger Scan", "description": "立即扫描所有知识库"},
        ]

    async def execute_action(self, action_id, payload=None):
        if action_id == "trigger_scan":
            asyncio.create_task(self._run_scan_cycle())
            return {"status": "started"}
        raise ValueError(f"Unknown action: {action_id}")

    # ==================== 信号处理 ====================

    async def _handle_signal(self, signal):
        """处理外部 signal。

        - source_added: 立即扫描该 source，提交高优先级 ingest 任务
        - 其他 signal: 当前未使用，仅记录日志
        """
        if isinstance(signal, DataSignal) and signal.type_name == "source_added":
            await self._handle_source_added(signal)
        else:
            logger.warning(f"Unhandled signal: {getattr(signal, 'signal_type', type(signal).__name__)}")

    async def _handle_source_added(self, signal: DataSignal):
        """处理 source_added：扫描新 source，提交高优先级 ingest 任务。"""
        kb_name = signal.data.get("kb_name")
        source_id = signal.data.get("source_id")

        if not kb_name or source_id is None:
            logger.warning(f"source_added signal missing kb_name/source_id: {signal.to_text()}")
            return

        ns = KBRegistry.get(kb_name)
        if ns is None:
            logger.warning(f"KB '{kb_name}' not found for source_added signal")
            return

        if not ns.wiki_manager.has_schema():
            logger.info(f"KB '{kb_name}' has no schema, skipping source scan")
            return

        source = await ns.db.get_source_by_id(source_id)
        if not source:
            logger.warning(f"Source {source_id} not found in KB '{kb_name}'")
            return

        system_prompt = self._build_ingest_prompt(kb_name, ns)
        self.emit_service_event("source_received", {
            "kb_name": kb_name,
            "source_path": source["path"],
        })
        # source_added 不检查 auto_scan —— 用户主动添加 source 期望立即处理一次
        # 后续的周期 scan 才受 auto_scan 控制
        await self._process_source(kb_name, ns, source, system_prompt,
                                   priority=0, futs_out=None)

    # ==================== 生命周期 ====================

    async def start(self):
        if self._running:
            return
        self._running = True

        if hasattr(self._runtime, 'get_broadcast_callback'):
            self._broadcast_message_callback = self._runtime.get_broadcast_callback()

        self._ensure_event_consumer()
        self._ensure_signal_loop()

        self._ingest_workers = [
            ServiceWorker(self, f"wiki-ingest-{i}",
                          skills=["knowledge_base.maintenance", "file", "basic_planning"])
            for i in range(self._max_workers)
        ]
        for w in self._ingest_workers:
            self.register_worker(w, group="ingest")
            await w.start()

        self._task = asyncio.create_task(self._loop())
        self.echo(">>> WikiMaintenanceService started")

    async def stop(self):
        self._running = False

        await self._stop_signal_loop()

        # 先停 _loop：停止提交新任务，并让正在 await gather 的 scan 周期收尾
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # 再停 workers：让正在执行的任务走 on_error(CancelledError) 收尾
        for w in self._ingest_workers:
            await w.stop()

        if self._event_task:
            self._event_task.cancel()
            try:
                await asyncio.wait_for(self._event_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        self.echo(">>> WikiMaintenanceService stopped")

    # ==================== 主循环：scan-then-wait ====================

    async def _loop(self):
        """scan → 等所有任务完成 → sleep(rest_interval) → 再 scan。"""
        while self._running:
            try:
                await self._run_scan_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WikiMaintenanceService loop error: {e}")
            await asyncio.sleep(self._scan_interval)

    async def _run_scan_cycle(self):
        """一次完整的 scan-then-wait 周期。

        - 通过 _scanning 标志互斥（_loop 和 trigger_scan 不能同时跑）
        - 提交任务后 await gather，保证本次 scan 的所有 ingest 完成后才返回
        """
        if self._scanning:
            self.emit_service_event("scan_skipped", {"reason": "already running"})
            return
        self._scanning = True
        import time
        t0 = time.monotonic()
        try:
            futs = await self._scan_all()
            self.emit_service_event("scan_started", {"task_count": len(futs)})
            if futs:
                await asyncio.gather(*futs, return_exceptions=True)
            duration = round(time.monotonic() - t0, 1)
            self.emit_service_event("scan_completed", {
                "submitted": len(futs),
                "inflight_remaining": len(self._inflight),
                "duration_sec": duration,
            })
        except Exception as e:
            logger.error(f"Scan cycle error: {e}")
            self.emit_service_event("scan_error", {"error": str(e)})
        finally:
            self._scanning = False

    # ==================== 扫描与分发 ====================

    async def _scan_all(self) -> list:
        """扫描所有 KB 的所有 source，提交 ingest 任务（普通优先级）。

        返回本次提交的所有 task future（供调用方 gather）。
        """
        futs = []
        wiki_base = self._runtime.paths.wiki_dir
        if not wiki_base.exists():
            return futs

        for name in KBRegistry.list_all(wiki_base):
            ns = KBRegistry.get(name)
            if ns is None:
                try:
                    ns = await KBRegistry.get_or_create(name, wiki_base)
                except Exception as e:
                    logger.error(f"Failed to load knowledge base '{name}': {e}")
                    continue

            if not ns.wiki_manager.has_schema():
                continue

            system_prompt = self._build_ingest_prompt(name, ns)
            sources = await ns.db.get_all_sources()
            for src in sources:
                # 周期 scan 受 auto_scan 控制
                if not src.get("auto_scan", 1):
                    continue
                await self._process_source(name, ns, src, system_prompt,
                                           priority=1, futs_out=futs)

        return futs

    async def _process_source(self, kb_name: str, ns, source: dict,
                              system_prompt: str, priority: int,
                              futs_out: Optional[list] = None):
        """扫描单个 source，对每个 needs_ingest 文件提交 ingest 任务。

        futs_out: 若提供，提交成功的 future 会 append 进去（供 batch gather）。
                  若为 None，则 fire-and-forget。
        """
        abs_path = source["path"]
        if not Path(abs_path).exists():
            logger.warning(f"Source path does not exist: {abs_path}")
            return

        try:
            await ns.db.scan_source_directory(source["id"], abs_path)
        except Exception as e:
            logger.error(f"Scan failed for {abs_path}: {e}")
            return

        needs_ingest = await ns.db.get_needs_ingest_files(source["id"])
        for file_row in needs_ingest:
            fut = self._submit_ingest(kb_name, file_row, source, system_prompt, priority)
            if fut is not None and futs_out is not None:
                futs_out.append(fut)

    def _build_ingest_prompt(self, kb_name: str, ns) -> str:
        """构建 ingest 任务的 system_prompt（静态部分：schema + wiki_root + tree 占位符）。"""
        schema = ns.wiki_manager.read_schema()
        wiki_root = str(ns.wiki_manager.wiki_root)
        return KnowledgePrompts.INGEST_AUTONOMOUS.format(
            kb_name=kb_name,
            schema=schema or '（暂无 Schema）',
            wiki_root=wiki_root,
        )

    @staticmethod
    def _make_tree_injection_hook(kb_name: str):
        """构建 before_think_hook：每轮 think 前注入 fresh tree summary。

        每次 think 都重新读 tree，让 agent 感知 ingest 过程中其他 worker 创建的新页面。
        使用 <wiki-tree>...</wiki-tree> 标记块做 replace，避免重复 inject 时累积。
        """
        async def _hook(micro):
            ns = KBRegistry.get(kb_name)
            if not ns:
                return
            tree = ns.wiki_manager.get_tree_summary()
            current = micro.messages[0]["content"]
            block = f"<wiki-tree>\n{tree}\n</wiki-tree>"
            if _WIKI_TREE_RE.search(current):
                new_content = _WIKI_TREE_RE.sub(block, current)
            else:
                new_content = current + f"\n\n{block}"
            micro.update_system_message(new_content)
        return _hook

    def _pick_worker_for_kb(self, kb_name: str) -> Optional[ServiceWorker]:
        """按 KB 名称稳定分区到固定 worker。

        同一 KB 的所有文件 → 同一 worker → 串行执行 → 避免 wiki 写冲突。
        不同 KB → 可能不同 worker → 跨 KB 真并行（KB 间主题不重叠，几乎不会写同一页）。

        hash() 在单进程内稳定（PYTHONHASHSEED 只影响跨进程），符合需求。
        """
        workers = self.get_worker_group("ingest")
        if not workers:
            return None
        idx = hash(kb_name) % len(workers)
        return workers[idx]

    def _submit_ingest(self, kb_name: str, file_row: dict, source: dict,
                       system_prompt: str, priority: int = 1) -> Optional[asyncio.Future]:
        """提交一个 ingest 任务到 worker 池。

        去重逻辑：以 (kb_name, file_id) 为 key 查 _inflight，重复则返回 None。
        验证失败（路径越界/二进制/超大/stat 失败）也返回 None，且不污染 _inflight。
        成功时把 key 加进 _inflight，并设置 on_success/on_error 负责清理。

        返回值：成功提交时为 Future；跳过/失败时为 None。
        """
        file_id = file_row["id"]
        key = (kb_name, file_id)
        if key in self._inflight:
            return None

        source_root = Path(source["path"]).resolve()
        resolved = (source_root / file_row["rel_path"]).resolve()

        if not resolved.is_relative_to(source_root):
            logger.warning(f"Path traversal blocked: {file_row['rel_path']}")
            return None

        ext = resolved.suffix.lower()
        if ext in BINARY_EXTENSIONS_WARN:
            logger.warning(f"Skipping binary file: {resolved}")
            return None

        try:
            file_size = resolved.stat().st_size
            if file_size > _MAX_FILE_SIZE:
                logger.warning(f"File too large ({file_size // 1024 // 1024}MB): {resolved}")
                return None
        except OSError as e:
            logger.warning(f"File stat failed for {resolved}: {e}")
            return None

        worker = self._pick_worker_for_kb(kb_name)
        if worker is None:
            logger.warning("No ingest workers available")
            return None

        # 通过了所有检查 → 加入 in-flight 集合
        self._inflight.add(key)

        # 记录 scan 时该文件的 mtime，ingest 成功后写入 ingested_mtime。
        # 这样下次 get_needs_ingest_files 用 ingested_mtime != mtime 判断，
        # 如果文件在 ingest 期间被修改（mtime 变了），下次 scan 会重新选中。
        file_mtime = file_row["mtime"]

        async def _on_success():
            try:
                ns = KBRegistry.get(kb_name)
                if ns:
                    await ns.db.mark_ingested(file_id, file_mtime)
            except Exception as e:
                logger.error(f"mark_ingested failed for {file_row['rel_path']}: {e}")
            finally:
                self._inflight.discard(key)

        async def _on_error(exc):
            self._inflight.discard(key)
            # 失败时不标记 last_ingested_at —— 下次 scan 会自动重选并重试
            logger.warning(f"Ingest failed for '{file_row['rel_path']}' in '{kb_name}': {exc}")
            self.emit_service_event("task_failed", {
                "file": file_row["rel_path"],
                "kb_name": kb_name,
                "error": str(exc),
            })

        task = ServiceTask(
            label=f"ingest-{kb_name}-{file_row['rel_path']}",
            text=f"本次要分析的原始文件：{resolved}",
            system_prompt=system_prompt,
            before_think_hook=self._make_tree_injection_hook(kb_name),
            on_success=_on_success,
            on_error=_on_error,
        )
        return worker.submit(task, priority=priority)
