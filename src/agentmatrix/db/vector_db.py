
import asyncio
import chromadb
from chromadb.config import Settings
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional
from contextlib import asynccontextmanager
from ..core.log_util import AutoLoggerMixin
from chromadb.utils import embedding_functions
import os

# ==========================================
# 1. 手写一个 Async ReadWriteLock (写优先)
# ==========================================
class AsyncReadWriteLock:
    def __init__(self):
        self._readers = 0
        self._writers = 0           # 当前活跃的写者（0或1）
        self._waiting_writers = 0   # 正在排队的写者（用于防止写饥饿）
        self._condition = asyncio.Condition()

    @asynccontextmanager
    async def read_lock(self):
        """读锁上下文管理器：允许多个Reader，除非有Writer在写或在等"""
        async with self._condition:
            # 如果有活跃写者 OR 有写者在排队，读者必须等（写优先策略）
            while self._writers > 0 or self._waiting_writers > 0:
                await self._condition.wait()
            self._readers += 1
        
        try:
            yield
        finally:
            async with self._condition:
                self._readers -= 1
                # 如果没有读者了，唤醒所有等待者（包括写者）
                if self._readers == 0:
                    self._condition.notify_all()

    @asynccontextmanager
    async def write_lock(self):
        """写锁上下文管理器：独占，需要等待所有Reader和Writer退出"""
        async with self._condition:
            self._waiting_writers += 1
            # 等待直到没有活跃写者 且 没有活跃读者
            while self._writers > 0 or self._readers > 0:
                await self._condition.wait()
            self._waiting_writers -= 1
            self._writers = 1
        
        try:
            yield
        finally:
            async with self._condition:
                self._writers = 0
                self._condition.notify_all()

# ==========================================
# 2. 改进后的 VectorDB
# ==========================================
class VectorDB(AutoLoggerMixin):
    _instance = None
    _init_lock = asyncio.Lock() # 仅用于单例创建的简单锁

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, persist_directory, collection_names):
        """
        collection_names: 必须在初始化时传入所有需要管理的集合名称列表
        """
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.persist_directory = persist_directory

        
        # 初始化 Chroma Client
        try:
            # 设置 SQLite WAL 模式有助于并发，但 Python 层仍需控制
            settings = Settings(anonymized_telemetry=False, allow_reset=False, )
            self.client = chromadb.PersistentClient(path=persist_directory, settings=settings)
            
            # --- 关键策略：读写分离线程池 ---
            # 1. 读线程池：并发数设为 CPU 核心数 x 2 或固定值，用于 Query
            self.read_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ChromaReader")
            # 2. 写线程池：必须是 1，用于 Add/Update/Delete
            self.write_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ChromaWriter")
            
            # --- 关键组件：读写锁 ---
            self.rw_lock = AsyncReadWriteLock()
            self.echo(">>> Loading Embedding Function...")
            os.environ["HF_HUB_OFFLINE"] = "1"  # 完全离线模式
            os.environ["TRANSFORMERS_OFFLINE"] = "1"  # transformers 库离线模式
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-large-zh-v1.5")
            self.echo(">>> Embedding Function Loaded.")
            # --- 预加载 Collections ---
            self.collections = {}
            if collection_names:
                for name in collection_names:
                    # 同步获取，初始化时不需要异步，保证启动即就绪
                    self.collections[name] = self.client.get_or_create_collection(name=name, embedding_function=self.embedding_function)
                    self.logger.info(f"Collection '{name}' loaded.")
            
            self._initialized = True
            self.logger.info("VectorDB initialized with ReadWrite separation.")
            
        except Exception as e:
            self.logger.exception(f"Initialization failed: {e}")
            raise

    def get_collection(self, collection_name: str):
        """获取已加载的 Collection"""
        return self.collections.get(collection_name, None)

    # 辅助：获取 EventLoop
    def _get_loop(self):
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()

    # ==========================
    # 写操作 (串行，独占)
    # ==========================
    async def add_documents(self, collection_name: str, documents: List[str], metadatas=None, ids=None):
        if collection_name not in self.collections:
            self.logger.error(f"Collection {collection_name} not found in pre-loaded list.")
            return

        # 1. 获取应用层写锁 (会等待所有正在进行的读操作结束)
        async with self.rw_lock.write_lock():
            loop = self._get_loop()
            collection = self.collections[collection_name]
            
            def _sync_add():
                # 这里运行在单线程池中
                collection.add(documents=documents, metadatas=metadatas, ids=ids)

            # 2. 扔到 写线程池 执行
            await loop.run_in_executor(self.write_executor, _sync_add)
            self.logger.info(f"Write complete: {len(documents)} docs to {collection_name}")

    # ==========================
    # 读操作 (并行，共享)
    # ==========================
    async def query(self, collection_name: str, query_texts: List[str],where, n_results=10):
        if collection_name not in self.collections:
            raise ValueError(f"Collection {collection_name} does not exist")

        # 1. 获取应用层读锁 (允许多个 Query 同时进入，但如果有 Writer 排队则等待)
        async with self.rw_lock.read_lock():
            loop = self._get_loop()
            collection = self.collections[collection_name]
            
            def _sync_query():
                # 这里运行在多线程池中，真正的并行读取
                return collection.query(query_texts=query_texts,where=where, n_results=n_results)

            # 2. 扔到 读线程池 执行
            results = await loop.run_in_executor(self.read_executor, _sync_query)
            return results

    async def close(self):
        self.logger.info("Shutting down executors...")
        self.read_executor.shutdown(wait=False)
        self.write_executor.shutdown(wait=True) # 写操作最好等待完成
        self.logger.info("Shutdown complete.")

    

# ==========================
# 验证代码
# ==========================
async def main():
    # 初始化：明确指定需要的集合
    db = VectorDB(collection_names=["knowledge_base", "user_logs"])

    # 1. 写入数据 (独占)
    print("--- Start Writing ---")
    await db.add_documents(
        "knowledge_base", 
        documents=["Python is cool", "Asyncio is tricky"], 
        ids=["id1", "id2"]
    )

    # 2. 并发读取测试
    print("--- Start Concurrent Reading ---")
    async def simulate_query(idx):
        print(f"Query {idx} starting...")
        # 这里的 query 会并行执行
        res = await db.query("knowledge_base", ["Python"], n_results=1)
        print(f"Query {idx} finished. Result ID: {res['ids'][0]}")

    # 模拟 5 个并发查询
    tasks = [simulate_query(i) for i in range(5)]
    
    # 模拟在查询中间插入一个写入，验证写锁是否能阻断读
    async def delayed_write():
        await asyncio.sleep(0.01) # 让读先跑一点
        print("!!! Urgent Write Trying to acquire lock !!!")
        await db.add_documents("knowledge_base", ["Interrupted"], ids=["id3"])
        print("!!! Urgent Write Finished !!!")

    tasks.append(delayed_write())
    
    await asyncio.gather(*tasks)
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())