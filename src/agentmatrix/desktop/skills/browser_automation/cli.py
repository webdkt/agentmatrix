"""
CDP Browser CLI — interactive test tool.

Usage:
    python -m agentmatrix.skills.cdp_browser.cli

Commands:
    start       — Start Chrome with remote debugging
    connect     — Connect CDP client to Chrome
    status      — Show connection status
    pages       — List all pages in Chrome
    open <url>  — Open a new tab with URL
    tabs        — List tabs tracked by TabManager
    switch <id> — Switch to a tab by target_id
    current     — Get current tab info
    close <id>  — Close a tab
    cleanup     — Close all tracked tabs

    teaching    — Toggle teaching mode (start/stop)
    toolbar     — Inject teaching toolbar into current tab
    indicator <x> <y> <text> — Show indicator on current tab
    range       — Show range selector on current tab
    events      — Show captured teaching events
    result      — Poll indicator result from JS
    range_result — Poll range selector result from JS

    eval <js>   — Execute JS in current tab
    disconnect  — Close CDP connection
    stop        — Stop Chrome
    quit        — Exit
"""

import asyncio
import json
import os
import sys
import time

from .cdp_client import CDPClient
from .chrome_manager import ChromeManager
from .tab_manager import TabManager
from .teaching import (
    TeachingListener,
    build_toolbar_js,
    build_indicator_with_event_js,
    build_range_selector_js,
    CHECK_RESULT_JS,
    CHECK_RANGE_RESULT_JS,
    CLEANUP_INDICATOR_JS,
    CLEANUP_RANGE_JS,
    CLEANUP_TOOLBAR_JS,
)

PROFILE_DIR = "/tmp/cdp_browser_test_profile"
PORT = 9222
AGENT_NAME = "test_agent"


async def main():
    chrome = ChromeManager(profile_dir=PROFILE_DIR, port=PORT)
    cdp: CDPClient | None = None
    tab_mgr: TabManager | None = None
    listener: TeachingListener | None = None

    def get_tab_mgr():
        if tab_mgr is None:
            print("Not connected. Run 'connect' first.")
            return None
        return tab_mgr

    def get_session():
        """Get the session_id of the current agent tab."""
        mgr = get_tab_mgr()
        if not mgr:
            return None
        tabs = asyncio.get_event_loop().run_until_complete(
            mgr.get_agent_tabs(AGENT_NAME)
        )
        if not tabs:
            print("  No tab. Use 'open' first.")
            return None
        return tabs[-1].session_id

    print("CDP Browser CLI")
    print("Type 'help' for commands, 'quit' to exit.\n")

    while True:
        try:
            line = input("cdp> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        try:
            # ==================== Chrome lifecycle ====================
            if cmd == "start":
                if chrome.is_running():
                    print(f"Chrome already running on port {PORT}")
                else:
                    print(f"Starting Chrome on port {PORT}...")
                    ws_url = await chrome.ensure_started()
                    print(f"Chrome started: {ws_url}")

            elif cmd == "connect":
                if cdp and cdp._connected:
                    print("Already connected.")
                    continue
                if not chrome.is_running():
                    print("Chrome not running. Run 'start' first.")
                    continue
                ws_url = chrome.get_ws_url()
                if not ws_url:
                    ws_url = await chrome.ensure_started()
                print(f"Connecting to {ws_url}...")
                cdp = CDPClient(ws_url)
                await cdp.connect()
                tab_mgr = TabManager(cdp)
                print("Connected.")

            elif cmd == "status":
                print(f"Chrome running: {chrome.is_running()}")
                print(f"Chrome port: {PORT}")
                print(f"CDP connected: {cdp is not None and cdp._connected}")
                print(f"Teaching mode: {listener is not None and listener.active}")
                if cdp and cdp._connected:
                    tabs = tab_mgr.get_all_tabs() if tab_mgr else []
                    print(f"Tracked tabs: {len(tabs)}")

            elif cmd == "stop":
                if listener:
                    listener.stop()
                    listener = None
                if tab_mgr:
                    for t in list(tab_mgr.get_all_tabs()):
                        try:
                            await tab_mgr.close_tab(t.target_id)
                        except Exception:
                            pass
                    tab_mgr = None
                if cdp:
                    await cdp.close()
                    cdp = None
                await chrome.stop()
                print("Chrome stopped.")

            # ==================== Raw CDP ====================
            elif cmd == "pages":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                pages = await cdp.get_pages(include_internal=False)
                for i, p in enumerate(pages):
                    print(f"  [{i}] {p['targetId'][:12]}  {p.get('title','')[:50]}  {p.get('url','')[:80]}")
                if not pages:
                    print("  (no pages)")

            elif cmd == "targets":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                targets = await cdp.get_targets()
                for t in targets:
                    print(f"  {t['type']:10} {t['targetId'][:12]}  {t.get('url','')[:80]}")

            # ==================== Tab operations ====================
            elif cmd == "open":
                mgr = get_tab_mgr()
                if not mgr:
                    continue
                url = arg if arg else "about:blank"
                if not url.startswith(("http://", "https://", "about:")):
                    url = "https://" + url
                print(f"Opening: {url}")
                tab = await mgr.create_tab(AGENT_NAME, url)
                if url != "about:blank":
                    try:
                        await cdp.send(
                            "Page.navigate", {"url": url},
                            session_id=tab.session_id, timeout=30,
                        )
                        # Enable Page domain to receive load events
                        await cdp.send("Page.enable", session_id=tab.session_id, timeout=5)
                        await asyncio.sleep(1)
                        tab = await mgr.refresh_tab_info(tab.target_id)
                    except Exception as e:
                        print(f"Navigation error: {e}")
                print(f"Created tab: {tab.target_id}")
                print(f"  URL:   {tab.url}")
                print(f"  Title: {tab.title}")

                # If teaching mode is active, inject toolbar into the new tab
                if listener and listener.active:
                    await listener.inject_toolbar(tab.session_id)
                    print("  (teaching toolbar injected)")

            elif cmd == "tabs":
                mgr = get_tab_mgr()
                if not mgr:
                    continue
                tabs = await mgr.get_agent_tabs(AGENT_NAME)
                if not tabs:
                    print("  (no tabs for this agent)")
                for t in tabs:
                    print(f"  {t.target_id[:12]}  {t.title[:40]:40}  {t.url[:60]}")

            elif cmd == "switch":
                mgr = get_tab_mgr()
                if not mgr:
                    continue
                if not arg:
                    print("Usage: switch <target_id>")
                    continue
                tabs = await mgr.get_agent_tabs(AGENT_NAME)
                target = None
                for t in tabs:
                    if t.target_id.startswith(arg):
                        target = t.target_id
                        break
                if not target:
                    print(f"No tab matching '{arg}'")
                    continue
                tab = await mgr.get_tab(target)
                if tab:
                    await cdp.activate_target(target)
                    tab = await mgr.refresh_tab_info(target)
                    print(f"Switched to: {tab.target_id}")
                    print(f"  URL:   {tab.url}")
                    print(f"  Title: {tab.title}")

            elif cmd == "current":
                mgr = get_tab_mgr()
                if not mgr:
                    continue
                tabs = await mgr.get_agent_tabs(AGENT_NAME)
                if tabs:
                    tab = tabs[-1]
                    tab = await mgr.refresh_tab_info(tab.target_id)
                    print(f"  target_id: {tab.target_id}")
                    print(f"  URL:   {tab.url}")
                    print(f"  Title: {tab.title}")
                else:
                    print("  (no tabs)")

            elif cmd == "close":
                mgr = get_tab_mgr()
                if not mgr:
                    continue
                if not arg:
                    print("Usage: close <target_id>")
                    continue
                tabs = await mgr.get_agent_tabs(AGENT_NAME)
                target = None
                for t in tabs:
                    if t.target_id.startswith(arg):
                        target = t.target_id
                        break
                if not target:
                    print(f"No tab matching '{arg}'")
                    continue
                await mgr.close_tab(target)
                print(f"Closed: {target}")

            elif cmd == "cleanup":
                mgr = get_tab_mgr()
                if not mgr:
                    continue
                await mgr.cleanup_agent(AGENT_NAME)
                print("All tabs closed.")

            # ==================== Teaching Mode ====================
            elif cmd == "teaching":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                if listener and listener.active:
                    listener.stop()
                    print("Teaching mode OFF.")
                else:
                    listener = TeachingListener(cdp, tab_mgr)
                    listener.start()
                    print("Teaching mode ON.")
                    # Inject toolbar into all existing agent tabs
                    tabs = await tab_mgr.get_agent_tabs(AGENT_NAME)
                    for t in tabs:
                        await cdp.send("Page.enable", session_id=t.session_id, timeout=5)
                        await listener.inject_toolbar(t.session_id)
                    print(f"  Toolbar injected into {len(tabs)} tab(s).")

            elif cmd == "toolbar":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                tabs = await tab_mgr.get_agent_tabs(AGENT_NAME)
                if not tabs:
                    print("  No tab.")
                    continue
                sid = tabs[-1].session_id
                await cdp.send(
                    "Runtime.evaluate",
                    {"expression": build_toolbar_js()},
                    session_id=sid,
                )
                print("Toolbar injected.")

            elif cmd == "indicator":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                tabs = await tab_mgr.get_agent_tabs(AGENT_NAME)
                if not tabs:
                    print("  No tab.")
                    continue
                # Parse: indicator <x> <y> <text>
                i_parts = arg.split(maxsplit=2)
                if len(i_parts) < 3:
                    print("Usage: indicator <x> <y> <text>")
                    continue
                try:
                    ix, iy = int(i_parts[0]), int(i_parts[1])
                except ValueError:
                    print("x and y must be integers")
                    continue
                info_text = i_parts[2]
                sid = tabs[-1].session_id
                # Clean up range selector first (mutual exclusion)
                await cdp.send("Runtime.evaluate", {"expression": CLEANUP_RANGE_JS}, session_id=sid)
                # Use toolbar's __bh_show_indicator__ if available, else inject standalone
                js = (
                    f"if(window.__bh_show_indicator__){{"
                    f"window.__bh_show_indicator__({ix},{iy},{json.dumps(info_text)})"
                    f"}}else{{"
                    f"{build_indicator_with_event_js(ix, iy, info_text)}"
                    f"}}"
                )
                await cdp.send(
                    "Runtime.evaluate",
                    {"expression": js},
                    session_id=sid,
                )
                print(f"Indicator shown at ({ix}, {iy})")
                print("  Drag the crosshair, fill the input, click OK.")
                print("  Run 'events' to see the result, or 'result' to poll.")

            elif cmd == "range":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                tabs = await tab_mgr.get_agent_tabs(AGENT_NAME)
                if not tabs:
                    print("  No tab.")
                    continue
                sid = tabs[-1].session_id
                # Clean up indicator first (mutual exclusion)
                await cdp.send("Runtime.evaluate", {"expression": CLEANUP_INDICATOR_JS}, session_id=sid)
                # Use toolbar's __bh_show_range__ if available
                js = (
                    "if(window.__bh_show_range__){"
                    "window.__bh_show_range__()"
                    "}"
                )
                await cdp.send(
                    "Runtime.evaluate",
                    {"expression": js},
                    session_id=sid,
                )
                print("Range selector shown.")
                print("  Drag edges/corners to resize, drag border to move.")
                print("  Fill the input, click OK.")
                print("  Run 'events' to see the result, or 'range_result' to poll.")

            elif cmd == "result":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                tabs = await tab_mgr.get_agent_tabs(AGENT_NAME)
                if not tabs:
                    print("  No tab.")
                    continue
                sid = tabs[-1].session_id
                resp = await cdp.send(
                    "Runtime.evaluate",
                    {"expression": CHECK_RESULT_JS, "returnByValue": True},
                    session_id=sid,
                )
                val = resp.get("result", {}).get("value")
                if val is None:
                    print("  (waiting — user has not clicked OK yet)")
                else:
                    print(f"  Result: x={val.get('x')}, y={val.get('y')}, text={val.get('text')!r}")

            elif cmd == "range_result":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                tabs = await tab_mgr.get_agent_tabs(AGENT_NAME)
                if not tabs:
                    print("  No tab.")
                    continue
                sid = tabs[-1].session_id
                resp = await cdp.send(
                    "Runtime.evaluate",
                    {"expression": CHECK_RANGE_RESULT_JS, "returnByValue": True},
                    session_id=sid,
                )
                val = resp.get("result", {}).get("value")
                if val is None:
                    print("  (waiting — user has not clicked OK yet)")
                else:
                    print(f"  Result: x={val.get('x')}, y={val.get('y')}, w={val.get('width')}, h={val.get('height')}, text={val.get('text')!r}")

            elif cmd == "remove":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                tabs = await tab_mgr.get_agent_tabs(AGENT_NAME)
                if not tabs:
                    print("  No tab.")
                    continue
                sid = tabs[-1].session_id
                await cdp.send(
                    "Runtime.evaluate",
                    {"expression": CLEANUP_INDICATOR_JS},
                    session_id=sid,
                )
                await cdp.send(
                    "Runtime.evaluate",
                    {"expression": CLEANUP_RANGE_JS},
                    session_id=sid,
                )
                print("Indicator and range selector removed.")

            elif cmd == "events":
                if not listener:
                    print("Teaching mode not active. Run 'teaching' first.")
                    continue
                events = listener.drain_events()
                if not events:
                    print("  (no events)")
                for ev in events:
                    ts = time.strftime("%H:%M:%S", time.localtime(ev.timestamp))
                    tab_info = ""
                    if ev.target_id:
                        tab_info = f" tab={ev.target_id[:8]}"
                    print(f"  [{ts}] {ev.event_type}{tab_info}  {ev.data}")

            # ==================== Debug ====================
            elif cmd == "eval":
                if not cdp or not cdp._connected:
                    print("Not connected.")
                    continue
                if not arg:
                    print("Usage: eval <js_expression>")
                    continue
                tabs = await tab_mgr.get_agent_tabs(AGENT_NAME)
                if tabs:
                    sid = tabs[-1].session_id
                    result = await cdp.send(
                        "Runtime.evaluate",
                        {"expression": arg, "returnByValue": True, "awaitPromise": True},
                        session_id=sid,
                    )
                    val = result.get("result", {}).get("value")
                    print(f"  => {val}")
                else:
                    print("  No tab to eval in.")

            # ==================== System ====================
            elif cmd == "disconnect":
                if listener:
                    listener.stop()
                    listener = None
                if tab_mgr:
                    await tab_mgr.cleanup_agent(AGENT_NAME)
                    tab_mgr = None
                if cdp:
                    await cdp.close()
                    cdp = None
                print("Disconnected.")

            elif cmd in ("help", "?"):
                print(__doc__)

            elif cmd in ("quit", "exit", "q"):
                break

            else:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")

        except Exception as e:
            print(f"Error: {e}")

    # Cleanup on exit
    print("Cleaning up...")
    if listener:
        listener.stop()
    if tab_mgr:
        try:
            await tab_mgr.cleanup_agent(AGENT_NAME)
        except Exception:
            pass
    if cdp:
        try:
            await cdp.close()
        except Exception:
            pass
    print("Bye.")


if __name__ == "__main__":
    asyncio.run(main())
