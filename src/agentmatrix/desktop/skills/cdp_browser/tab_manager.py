"""
Tab Manager — per-agent tab tracking and isolation.

Each agent creates its own tabs. TabManager tracks ownership so agents
don't interfere with each other's browser state.
"""

import logging
from typing import Dict, List, Optional, Set

from .cdp_client import CDPClient

logger = logging.getLogger(__name__)


class TabInfo:
    """Information about a browser tab."""

    __slots__ = ("target_id", "session_id", "url", "title", "agent_name")

    def __init__(
        self,
        target_id: str,
        session_id: str = "",
        url: str = "",
        title: str = "",
        agent_name: str = "",
    ):
        self.target_id = target_id
        self.session_id = session_id
        self.url = url
        self.title = title
        self.agent_name = agent_name

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "session_id": self.session_id,
            "url": self.url,
            "title": self.title,
            "agent_name": self.agent_name,
        }


class TabManager:
    """
    Track which tabs belong to which agent.

    Provides tab-level isolation: each agent manages its own set of tabs.
    When an agent's session ends, all its tabs can be cleaned up.
    """

    def __init__(self, cdp: CDPClient):
        self.cdp = cdp
        # target_id → TabInfo
        self._tabs: Dict[str, TabInfo] = {}
        # agent_name → set of target_ids
        self._agent_tabs: Dict[str, Set[str]] = {}

    async def create_tab(self, agent_name: str, url: str = "about:blank") -> TabInfo:
        """
        Create a new tab for an agent.

        Args:
            agent_name: The agent that owns this tab.
            url: Initial URL (default: about:blank).

        Returns:
            TabInfo with target_id and session_id.
        """
        target_id = await self.cdp.create_target(url)
        session_id = await self.cdp.attach_to_target(target_id)
        await self.cdp.enable_domains(session_id)

        tab = TabInfo(
            target_id=target_id,
            session_id=session_id,
            url=url,
            agent_name=agent_name,
        )

        self._tabs[target_id] = tab
        self._agent_tabs.setdefault(agent_name, set()).add(target_id)

        logger.info(f"Created tab {target_id} for agent '{agent_name}' (url={url})")
        return tab

    async def close_tab(self, target_id: str):
        """Close a tab and remove it from tracking."""
        tab = self._tabs.get(target_id)
        if not tab:
            logger.warning(f"Tab {target_id} not found in tracking")
            return

        try:
            await self.cdp.close_target(target_id)
        except Exception as e:
            logger.warning(f"Failed to close tab {target_id}: {e}")

        # Remove from tracking
        self._tabs.pop(target_id, None)
        agent_tabs = self._agent_tabs.get(tab.agent_name)
        if agent_tabs:
            agent_tabs.discard(target_id)
            if not agent_tabs:
                del self._agent_tabs[tab.agent_name]

        logger.info(f"Closed tab {target_id} (agent='{tab.agent_name}')")

    async def get_agent_tabs(self, agent_name: str) -> List[TabInfo]:
        """Get all tabs owned by an agent."""
        return self.get_agent_tabs_sync(agent_name)

    def get_agent_tabs_sync(self, agent_name: str) -> List[TabInfo]:
        """Synchronous version of get_agent_tabs (just reads internal dict)."""
        target_ids = self._agent_tabs.get(agent_name, set())
        return [self._tabs[tid] for tid in target_ids if tid in self._tabs]

    async def get_tab(self, target_id: str) -> Optional[TabInfo]:
        """Get tab info by target_id."""
        return self._tabs.get(target_id)

    async def attach_to_tab(self, target_id: str) -> str:
        """
        Attach CDP session to an existing tab.

        Returns:
            session_id for subsequent CDP commands.
        """
        tab = self._tabs.get(target_id)
        if tab and tab.session_id:
            return tab.session_id

        # Not tracked or no session — attach fresh
        session_id = await self.cdp.attach_to_target(target_id)
        if tab:
            tab.session_id = session_id
        return session_id

    async def refresh_tab_info(self, target_id: str) -> Optional[TabInfo]:
        """
        Refresh a tab's URL and title from Chrome.

        Useful after navigation to update tracked state.
        """
        tab = self._tabs.get(target_id)
        if not tab:
            return None

        try:
            result = await self.cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "JSON.stringify({url: location.href, title: document.title})",
                    "returnByValue": True,
                },
                session_id=tab.session_id,
            )
            import json
            info = json.loads(result["result"]["value"])
            tab.url = info.get("url", tab.url)
            tab.title = info.get("title", tab.title)
        except Exception as e:
            logger.warning(f"Failed to refresh tab info for {target_id}: {e}")

        return tab

    async def cleanup_agent(self, agent_name: str):
        """Close all tabs owned by an agent (called on session end)."""
        target_ids = list(self._agent_tabs.get(agent_name, set()))
        for target_id in target_ids:
            await self.close_tab(target_id)
        logger.info(f"Cleaned up {len(target_ids)} tabs for agent '{agent_name}'")

    def get_all_tabs(self) -> List[TabInfo]:
        """Get all tracked tabs (for debugging/listing)."""
        return list(self._tabs.values())

    async def sync_from_browser(self):
        """
        Sync tab tracking with actual browser state.

        Removes tracking for tabs that no longer exist in Chrome.
        Called on startup or when tabs might have been closed externally.
        """
        try:
            pages = await self.cdp.get_pages(include_internal=False)
            live_ids = {p["targetId"] for p in pages}

            # Remove dead tabs from tracking
            dead = [tid for tid in self._tabs if tid not in live_ids]
            for tid in dead:
                tab = self._tabs.pop(tid)
                agent_tabs = self._agent_tabs.get(tab.agent_name)
                if agent_tabs:
                    agent_tabs.discard(tid)

            if dead:
                logger.info(f"Synced tabs: removed {len(dead)} dead entries")

        except Exception as e:
            logger.warning(f"Tab sync failed: {e}")
