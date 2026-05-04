"""
BrowserCollabAgent — 支持浏览器内嵌聊天的 Agent。

继承 BaseAgent，自动将状态更新和事件输出转发到浏览器前端。
浏览器中的聊天组件可以实时显示 Agent 状态和输出，用户也可以直接在浏览器中输入。

使用方式：
    class MyAgent(BrowserCollabAgent):
        ...
"""

import asyncio
import logging
from typing import Optional

from .base_agent import BaseAgent
from ..core.signals import CoreEvent

logger = logging.getLogger(__name__)


class BrowserCollabAgent(BaseAgent):
    """支持浏览器内嵌聊天的 Agent。

    在 BaseAgent 基础上，自动将以下信息转发到浏览器前端：
    - Agent 状态变化（IDLE / THINKING / WORKING 等）
    - CoreEvent（思考输出、action 执行结果等）

    前端通过 __bh_on_event__ 接收这些事件，在聊天组件中展示。
    用户在浏览器中输入的消息通过 __bh_emit__('chat_message') 发回 Agent。
    """

    async def _broadcast_to_browser(self, event_type: str, data: dict):
        """转发事件到浏览器前端。fire-and-forget，不阻塞主流程。"""
        try:
            from .skills.cdp_browser.skill import _event_listener, _agent_current_tab
            if not _event_listener or not _event_listener.active:
                return
            tab = _agent_current_tab.get(self.name)
            if not tab or not tab.session_id:
                return
            await _event_listener.emit_to_browser(tab.session_id, event_type, data)
        except Exception as e:
            logger.debug(f"Browser broadcast failed: {e}")

    def _fire_broadcast(self, event_type: str, data: dict):
        """异步触发浏览器广播（fire-and-forget）。"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast_to_browser(event_type, data))
        except RuntimeError:
            pass

    # ==========================================
    # BaseAgent overrides
    # ==========================================

    def update_status(self, new_status=None):
        """状态更新后转发到浏览器。"""
        super().update_status(new_status)
        if new_status is not None:
            self._fire_broadcast('agent_status', {
                'status': self._status,
            })

    async def _handle_core_event(self, event: CoreEvent, session_id: str):
        """CoreEvent 处理后转发到浏览器。"""
        await super()._handle_core_event(event, session_id)

        et, en, d = event.event_type, event.event_name, event.detail

        # 思考输出
        if et == "think" and en == "brain":
            thought = d.get("thought", "")
            if thought:
                self._fire_broadcast('agent_output', {
                    'type': 'think',
                    'text': thought,
                })

        # action 检测
        elif et == "action" and en == "detected":
            actions = d.get("actions", [])
            if actions:
                self._fire_broadcast('agent_output', {
                    'type': 'action_detected',
                    'text': ', '.join(actions),
                })

        # action 开始
        elif et == "action" and en == "started":
            self._fire_broadcast('agent_output', {
                'type': 'action_started',
                'text': d.get('action_name', '?'),
            })

        # action 完成
        elif et == "action" and en == "completed":
            name = d.get('action_name', '?')
            status = d.get('status', 'ok')
            preview = d.get('result_preview', '')
            self._fire_broadcast('agent_output', {
                'type': 'action_completed',
                'text': f"{name} -> {preview[:200]}" if status == 'ok' else f"{name} 失败: {preview}",
            })
