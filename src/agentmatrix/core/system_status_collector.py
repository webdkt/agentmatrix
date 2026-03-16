"""
System Status Collector

收集系统所有组件的状态，用于 WebSocket 广播。
"""

from typing import Dict, Any
from datetime import datetime
import logging


class SystemStatusCollector:
    """收集系统状态"""

    def __init__(self, matrix_runtime):
        """
        初始化状态收集器

        Args:
            matrix_runtime: AgentMatrix 实例
        """
        self.matrix_runtime = matrix_runtime
        self.logger = logging.getLogger(__name__)

    def collect_status(self) -> Dict[str, Any]:
        """
        收集完整系统状态

        Returns:
            Dict: {
                "timestamp": str,
                "agents": Dict[str, Dict]
            }
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": self._collect_agent_status()
        }

    def _collect_agent_status(self) -> Dict[str, Dict]:
        """收集所有 Agent 状态"""
        agents = {}

        for name, agent in self.matrix_runtime.agents.items():
            # 🔧 复用 BaseAgent 的 get_status_snapshot() 方法
            if not hasattr(agent, 'get_status_snapshot'):
                raise RuntimeError(f"Agent {name} does not have get_status_snapshot() method")

            agent_info = agent.get_status_snapshot()
            agents[name] = agent_info

        return agents
