"""
LLM 服务监控器

负责定期检查 LLM 服务的可用性，并提供全局状态。
"""

import asyncio
import logging
from typing import Dict, Optional
from ..backends.llm_client import LLMClient
from ..core.log_util import AutoLoggerMixin
from ..core.log_config import LogConfig


class LLMServiceMonitor(AutoLoggerMixin):
    """
    LLM 服务监控器

    功能：
    - 定期检查 LLM 服务（default_llm 和 default_slm）的可用性
    - 维护全局可用性状态（llm_available Event）
    - 智能去重：如果两个服务指向同一个配置，只检查一次
    - 严格判断：brain 和 cerebellum 都必须可用
    """

    def __init__(
        self,
        llm_config: Dict,
        check_interval: int = 60,
        parent_logger: Optional[logging.Logger] = None
    ):
        """
        初始化监控器

        Args:
            llm_config: LLM 配置字典（从 loader.llm_config 获取）
            check_interval: 检查间隔（秒），默认 60 秒
            parent_logger: 父组件的 logger（用于共享日志）
        """
        self.llm_config = llm_config
        self.check_interval = check_interval
        self._parent_logger = parent_logger

        # 状态管理
        self.llm_available = asyncio.Event()
        self.llm_available.set()  # 初始状态：假设可用
        self.status_map: Dict[str, bool] = {}  # {service_name: is_available}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # 检查 default_llm 和 default_slm 是否指向同一个服务
        self._analyze_services()

        self.echo(f"LLMServiceMonitor initialized (interval: {check_interval}s)")
        self.echo(f"Services to check: {self.services_to_check}")

    def _get_log_context(self) -> dict:
        """提供日志上下文变量"""
        return {
            "monitor": "LLM",
        }

    def _analyze_services(self):
        """分析 default_llm 和 default_slm 是否为同一个服务"""
        if 'default_llm' not in self.llm_config or 'default_slm' not in self.llm_config:
            raise ValueError("llm_config must contain 'default_llm' and 'default_slm'")

        llm_cfg = self.llm_config['default_llm']
        slm_cfg = self.llm_config['default_slm']

        # 判断是否同一个服务（URL 和 model_name 都相同）
        is_same = (
            llm_cfg.get('url') == slm_cfg.get('url') and
            llm_cfg.get('model_name') == slm_cfg.get('model_name')
        )

        if is_same:
            self.echo(
                "✓ default_llm and default_slm point to the same service, "
                "will check once to save resources"
            )
            self.services_to_check = ['default_llm']
            self.is_same_service = True
        else:
            self.echo(
                "✓ default_llm and default_slm are different services, "
                "will check both"
            )
            self.services_to_check = ['default_llm', 'default_slm']
            self.is_same_service = False

    async def start(self):
        """启动监控任务"""
        if self._running:
            self.logger.warning("Monitor is already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._health_check_loop())
        self.echo("✓ LLM service monitor started")

    async def stop(self):
        """停止监控任务"""
        if not self._running:
            return

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        self.echo("✓ LLM service monitor stopped")

    async def _health_check_loop(self):
        """健康检查主循环"""
        self.logger.info(
            f"Starting health check loop (interval: {self.check_interval}s)"
        )

        while self._running:
            try:
                # 检查所有需要检查的服务
                results = {}
                for service_name in self.services_to_check:
                    is_available = await self._check_service(service_name)
                    results[service_name] = is_available

                # 更新状态映射
                self.status_map.update(results)

                # 判断全局可用性：所有检查的服务都必须可用
                all_available = all(results.values())

                # 更新全局 Event
                if all_available:
                    if not self.llm_available.is_set():
                        # 服务从未可用变为可用 → 重要事件，用 echo
                        self.echo(
                            f"✅ All LLM services recovered! Status: {results}"
                        )
                        self.llm_available.set()
                    else:
                        # 服务持续可用 → 普通日志，只记录文件
                        self.logger.debug(f"LLM services OK: {results}")
                else:
                    if self.llm_available.is_set():
                        # 服务从可用变为不可用 → 重要事件，用 echo
                        self.echo(
                            f"⚠️  LLM service unavailable! Status: {results}"
                        )
                        self.llm_available.clear()
                    else:
                        # 服务持续不可用 → 普通日志
                        self.logger.warning(f"LLM services still down: {results}")

                # 定期输出当前状态到控制台（每次检查后都显示）
                status_str = ", ".join([
                    f"{k}={'✅' if v else '❌'}" for k, v in results.items()
                ])
                self.echo(f"🔍 LLM Service Status: {status_str}")

            except asyncio.CancelledError:
                # 捕获取消异常，优雅退出
                self.logger.info("Health check loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Health check failed: {e}", exc_info=True)
                # 不改变状态，保持当前状态

            # 等待下一次检查（使用可中断的 sleep）
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                # 捕获取消异常，立即退出
                self.logger.info("Health check loop cancelled during sleep")
                break

        self.logger.info("Health check loop stopped")

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
        url = config.get('url')
        api_key = config.get('API_KEY')
        model_name = config.get('model_name')

        try:
            # 创建临时 LLMClient 用于测试
            # 使用简单日志配置
            log_config = LogConfig(prefix=f"[HealthCheck:{service_name}]")
            test_client = LLMClient(
                url=url,
                api_key=api_key,
                model_name=model_name,
                parent_logger=self._parent_logger,
                log_config=log_config
            )

            # 发送最简单的测试请求
            test_messages = [{"role": "user", "content": "hi"}]

            # 设置较短的超时（10秒）
            # 注意：这里使用 asyncio.wait_for 来限制总时间
            response = await asyncio.wait_for(
                test_client.think(messages=test_messages),
                timeout=10.0
            )

            # 检查响应
            if response and 'reply' in response:
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
            self.logger.warning(
                f"✗ Service '{service_name}' check failed: {str(e)}"
            )
            return False

    def is_available(self, service_name: Optional[str] = None) -> bool:
        """
        查询服务是否可用

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
            return self.llm_available.is_set()

        # 查询特定服务的状态
        if service_name in self.status_map:
            return self.status_map[service_name]

        # 如果没有检查过该服务，假设可用（向后兼容）
        return True

    def get_status(self) -> Dict[str, bool]:
        """
        获取所有服务的详细状态

        Returns:
            Dict[str, bool]: 服务状态映射
        """
        return self.status_map.copy()
