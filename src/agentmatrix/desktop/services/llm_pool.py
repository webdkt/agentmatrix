"""
LLMPool — 共享 LLM 客户端池

类似数据库连接池的设计：
- Pool 持有真正的 LLMClient 实例（按 model_name 复用）
- 全局 semaphore 控制并发请求数（所有 service 共享一个上限）
- PoolClient 是 facade，接口兼容 LLMClient，内部通过 pool 控制并发
- MicroAgent 完全无感知背后是 pool

架构：
  Service.brain (PoolClient facade)
         │
         ▼
     LLMPool (持有 LLMClient + 全局 semaphore)
         │
         ▼
     LLM API
"""

import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LLMPool:
    """共享 LLM 客户端池。

    从 runtime 的 llm_config 创建和管理 LLMClient 实例。
    全局 semaphore 控制并发请求数，所有 service 共享。
    """

    def __init__(self, llm_config: dict, max_concurrent: int = 3):
        self._clients: Dict[str, object] = {}  # model_name → LLMClient
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._llm_config = llm_config
        self._lock = asyncio.Lock()

    async def get_client(self, model_name: str):
        """获取 LLMClient 实例（懒创建，线程安全）。"""
        if model_name not in self._clients:
            async with self._lock:
                if model_name not in self._clients:
                    self._clients[model_name] = self._create_client(model_name)
                    logger.info(f"LLMPool: created client for '{model_name}'")
        return self._clients[model_name]

    def create_pool_client(self, model_name: str = "default_llm") -> "PoolClient":
        """为 service 创建一个 PoolClient facade。"""
        return PoolClient(self, model_name)

    def _create_client(self, model_name: str):
        from ...core.backends.llm_client import LLMClient

        config = self._llm_config[model_name]
        return LLMClient(
            url=config["url"],
            api_key=config["API_KEY"],
            model_name=config["model_name"],
        )


class PoolClient:
    """LLMClient 的 pool 代理 — 接口兼容 LLMClient，内部通过 pool 控制并发。

    MicroAgent 调 self.brain.think_with_retry() 时完全无感知背后是 pool。
    """

    def __init__(self, pool: LLMPool, model_name: str):
        self._pool = pool
        self._model_name = model_name

    async def think(self, *args, **kwargs):
        async with self._pool._semaphore:
            client = await self._pool.get_client(self._model_name)
            return await client.think(*args, **kwargs)

    async def think_with_retry(self, *args, **kwargs):
        async with self._pool._semaphore:
            client = await self._pool.get_client(self._model_name)
            return await client.think_with_retry(*args, **kwargs)
