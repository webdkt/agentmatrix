"""
LLM 服务监控器

Lazy Monitoring 模式：
- 启动时检查一次 OK 后进入 idle，不主动轮询
- 有人来问状态时，如果状态不可用，开始轮询检查
- 恢复后通知所有等待者，回到 idle
- 多个 Agent 同时来问时，复用同一个检查任务
"""

import asyncio
import logging
from enum import Enum
from typing import Dict, Optional
from ..backends.llm_client import LLMClient
from ..core.log_util import AutoLoggerMixin
from ..core.log_config import LogConfig


class MonitorState(Enum):
    """监控器状态"""

    IDLE = "idle"  # 初始/恢复后状态，不检查
    CHECKING = "checking"  # 有人问了，开始轮询检查


class LLMServiceMonitor(AutoLoggerMixin):
    """
    LLM 服务监控器 (Lazy Monitoring)

    功能：
    - 启动时检查一次 OK 后进入 idle，不主动轮询
    - 有人来问状态时，如果状态不可用，开始按需轮询检查
    - 恢复后通知所有等待者，回到 idle
    - 智能去重：如果两个服务指向同一个配置，只检查一次
    - 严格判断：brain 和 cerebellum 都必须可用
    """

    def __init__(
        self,
        llm_config: Dict,
        check_interval: int = 5,
        parent_logger: Optional[logging.Logger] = None,
    ):
        """
        初始化监控器

        Args:
            llm_config: LLM 配置字典（从 loader.llm_config 获取）
            check_interval: 按需检查时的轮询间隔（秒），默认 5 秒
            parent_logger: 父组件的 logger（用于共享日志）
        """
        self.llm_config = llm_config
        self.check_interval = check_interval
        self._parent_logger = parent_logger

        # 状态管理
        self.llm_available = asyncio.Event()
        self.llm_available.set()  # 初始状态：假设可用
        self.status_map: Dict[str, bool] = {}  # {service_name: is_available}

        # Lazy Monitoring 状态
        self._state = MonitorState.IDLE
        self._check_task: Optional[asyncio.Task] = None

        # 检查 default_llm 和 default_slm 是否指向同一个服务
        self._analyze_services()

        self.echo(
            f"LLMServiceMonitor initialized (lazy mode, check_interval: {check_interval}s)"
        )
        self.echo(f"Services to check: {self.services_to_check}")

    def _get_log_context(self) -> dict:
        """提供日志上下文变量"""
        return {
            "monitor": "LLM",
        }

    def _analyze_services(self):
        """分析 default_llm 和 default_slm 是否为同一个服务"""
        if "default_llm" not in self.llm_config or "default_slm" not in self.llm_config:
            raise ValueError("llm_config must contain 'default_llm' and 'default_slm'")

        llm_cfg = self.llm_config["default_llm"]
        slm_cfg = self.llm_config["default_slm"]

        # 判断是否同一个服务（URL 和 model_name 都相同）
        is_same = llm_cfg.get("url") == slm_cfg.get("url") and llm_cfg.get(
            "model_name"
        ) == slm_cfg.get("model_name")

        if is_same:
            self.echo(
                "✓ default_llm and default_slm point to the same service, "
                "will check once to save resources"
            )
            self.services_to_check = ["default_llm"]
            self.is_same_service = True
        else:
            self.echo(
                "✓ default_llm and default_slm are different services, will check both"
            )
            self.services_to_check = ["default_llm", "default_slm"]
            self.is_same_service = False

    async def start(self):
        """启动监控任务 - 懒汉模式：只检查一次"""
        self.echo("✓ LLM service monitor starting...")
        await self._initial_check()

    async def stop(self):
        """停止监控任务"""
        if self._check_task is not None and not self._check_task.done():
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None

        self._state = MonitorState.IDLE
        self.echo("✓ LLM service monitor stopped")

    async def _initial_check(self):
        """启动时检查一次"""
        self.logger.info("Running initial health check...")
        result = await self._check_all_services()
        self.status_map = result

        all_available = all(result.values())
        status_str = ", ".join(
            [f"{k}={'✅' if v else '❌'}" for k, v in result.items()]
        )

        if all_available:
            self.llm_available.set()
            self._state = MonitorState.IDLE
            self.echo(f"✅ Initial check OK: {status_str}")
        else:
            self.llm_available.clear()
            self.echo(
                f"⚠️ Initial check failed: {status_str}, starting on-demand check..."
            )
            await self._start_on_demand_check()

    async def _check_all_services(self) -> Dict[str, bool]:
        """检查所有需要检查的服务"""
        results = {}
        for service_name in self.services_to_check:
            is_available = await self._check_service(service_name)
            results[service_name] = is_available
        return results

    async def _start_on_demand_check(self):
        """启动按需检查（已被调用时触发）"""
        if self._check_task is not None and not self._check_task.done():
            return

        self._state = MonitorState.CHECKING
        self.echo("🔄 Starting on-demand health check...")

        async def _check_loop():
            while True:
                result = await self._check_all_services()
                self.status_map = result

                all_available = all(result.values())
                status_str = ", ".join(
                    [f"{k}={'✅' if v else '❌'}" for k, v in result.items()]
                )

                if all_available:
                    self.llm_available.set()
                    self._state = MonitorState.IDLE
                    self._check_task = None
                    self.echo(f"✅ LLM service recovered! Status: {status_str}")
                    return
                else:
                    self.logger.warning(
                        f"LLM still down: {status_str}, retrying in {self.check_interval}s..."
                    )
                    await asyncio.sleep(self.check_interval)

        self._check_task = asyncio.create_task(_check_loop())

    async def _check_service(self, service_name: str) -> bool:
        """
        检查单个服务的可用性

        Args:
            service_name: 服务名称（如 'default_llm', 'default_slm'）

        Returns:
            bool: 服务是否可用
        """
        if service_name not in self.llm_config:
            self.logger.warning(f"Service '{service_name}' not in config, skipping")
            return True  # 不在配置中的服务假设可用

        config = self.llm_config[service_name]
        url = config.get("url")
        api_key = config.get("API_KEY")
        model_name = config.get("model_name")

        try:
            # 创建临时 LLMClient 用于测试
            # 使用简单日志配置
            log_config = LogConfig(prefix=f"[HealthCheck:{service_name}]")
            test_client = LLMClient(
                url=url,
                api_key=api_key,
                model_name=model_name,
                parent_logger=self._parent_logger,
                log_config=log_config,
            )

            # 发送最简单的测试请求
            test_messages = [{"role": "user", "content": "hi"}]

            # 设置较短的超时（10秒）
            # 注意：这里使用 asyncio.wait_for 来限制总时间
            response = await asyncio.wait_for(
                test_client.think(messages=test_messages), timeout=10.0
            )

            # 检查响应
            if response and "reply" in response:
                self.logger.debug(f"✓ Service '{service_name}' is available")
                return True
            else:
                self.logger.warning(
                    f"✗ Service '{service_name}' returned invalid response"
                )
                return False

        except asyncio.TimeoutError:
            self.logger.warning(f"✗ Service '{service_name}' timeout")
            return False

        except Exception as e:
            self.logger.warning(f"✗ Service '{service_name}' check failed: {str(e)}")
            return False

    def is_available(self, service_name: Optional[str] = None) -> bool:
        """
        查询服务是否可用（Lazy模式）

        Args:
            service_name: 可选，指定服务名称
                          - None: 查询全局状态（所有服务）
                          - 'default_llm': 查询 brain 服务
                          - 'default_slm': 查询 cerebellum 服务

        Returns:
            bool: 服务是否可用
        """
        if service_name is None:
            # 查询全局状态
            if not self.llm_available.is_set():
                # 状态不可用，触发按需检查
                self._trigger_check_if_needed()
            return self.llm_available.is_set()

        # 查询特定服务的状态
        if service_name in self.status_map:
            return self.status_map[service_name]

        # 如果没有检查过该服务，假设可用（向后兼容）
        return True

    def _trigger_check_if_needed(self):
        """如果需要，启动按需检查"""
        if self._state == MonitorState.IDLE:
            asyncio.create_task(self._start_on_demand_check())

    def get_status(self) -> Dict[str, bool]:
        """
        获取所有服务的详细状态

        Returns:
            Dict[str, bool]: 服务状态映射
        """
        return self.status_map.copy()
