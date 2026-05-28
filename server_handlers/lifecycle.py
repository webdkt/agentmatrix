"""
Server lifecycle management: runtime initialization, shutdown, and lifespan.
"""

import json
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from agentmatrix import AgentMatrix

from .state import server_state


def load_user_agent_name(matrix_world_dir: Path) -> str:
    """Load user agent name from system_config.yml configuration file"""
    import yaml

    config_path = matrix_world_dir / ".matrix" / "configs" / "system_config.yml"
    if not config_path.exists():
        config_path = matrix_world_dir / ".matrix" / "configs" / "matrix_config.yml"
        if not config_path.exists():
            old_config_path = matrix_world_dir / "matrix_world.yml"
            if old_config_path.exists():
                print(
                    "⚠️  Warning: Using old matrix_world.yml, please migrate to new structure"
                )
                with open(old_config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    return config.get("user_agent_name", "User")
            else:
                print("⚠️  Warning: system_config.yml not found, using default 'User'")
                return "User"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            user_name = config.get("user_agent_name", "User")
            return user_name
    except Exception as e:
        print(f"⚠️  Error loading system_config.yml: {e}, using default 'User'")
        return "User"


async def broadcast_message_to_clients(message: dict):
    """Broadcast message to all WebSocket clients"""
    if not server_state.active_websockets:
        return

    try:
        json_message = json.dumps(message)

        websockets_to_remove = []
        for ws in server_state.active_websockets:
            try:
                await ws.send_text(json_message)
            except Exception as e:
                print(f"⚠️ Error sending to WebSocket: {e}")
                websockets_to_remove.append(ws)

        for ws in websockets_to_remove:
            server_state.active_websockets.remove(ws)

    except Exception as e:
        print(f"⚠️ Error in broadcast: {e}")


async def init_runtime(mw_dir: Path):
    """
    Initialize AgentMatrix runtime. Can be called from lifespan (warm start)
    or from /api/config/init (cold start in-process hot reload).
    """
    user_agent_name = load_user_agent_name(mw_dir)
    print(f"✅ Loaded user agent name: {user_agent_name}")

    print("🔧 Initializing AgentMatrix runtime...")

    async def event_callback(event):
        """Callback to broadcast runtime events to WebSocket clients"""
        try:
            print(f"📡 event_callback called: event_type={event.event_type}")
            if event.event_type == "SYSTEM_STATUS":
                message = json.dumps(
                    {
                        "type": "SYSTEM_STATUS",
                        "data": event.payload.get("status", {})
                        if event.payload
                        else {},
                    }
                )
                print(
                    f"📊 Broadcasting SYSTEM_STATUS to {len(server_state.active_websockets)} clients"
                )
            else:
                message = json.dumps({"type": "runtime_event", "data": event.to_dict()})

            for ws in server_state.active_websockets[:]:
                try:
                    await ws.send_text(message)
                except Exception as e:
                    print(f"⚠️  Error sending to WebSocket: {e}")
                    server_state.active_websockets.remove(ws)
        except Exception as e:
            print(f"⚠️  Error in event callback: {e}")

    runtime = AgentMatrix(
        matrix_root=str(mw_dir),
        async_event_callback=event_callback,
        user_agent_name=user_agent_name,
    )

    await runtime.post_office.init_db()

    runtime.set_broadcast_callback(broadcast_message_to_clients)
    for agent in runtime.agents.values():
        agent._broadcast_message_callback = runtime.get_broadcast_callback()
    print("✅ 广播回调已注入到所有 Agent")

    await runtime.startup()

    runtime._start_llm_monitor()

    if user_agent_name not in runtime.agents:
        raise Exception(
            f"User agent '{user_agent_name}' not found in loaded agents. Available agents: {list(runtime.agents.keys())}"
        )
    user_agent = runtime.agents[user_agent_name]
    print(f"✅ User agent validation passed: '{user_agent_name}'")

    print(f"✅ AgentMatrix runtime initialized successfully")
    print(f"🤖 Loaded agents: {list(runtime.agents.keys())}")

    server_state.matrix_runtime = runtime
    return runtime


async def graceful_shutdown():
    """Gracefully shutdown the AgentMatrix runtime"""
    print("\n👋 Shutting down AgentMatrix Server...")

    if server_state.active_websockets:
        print(f"📡 Closing {len(server_state.active_websockets)} WebSocket connections...")
        for ws in server_state.active_websockets[:]:
            try:
                await ws.close()
            except Exception:
                pass
        server_state.active_websockets.clear()
        print("✅ WebSocket connections closed")

    if server_state.matrix_runtime:
        try:
            print("💾 Saving Matrix state...")
            await asyncio.wait_for(server_state.matrix_runtime.shutdown(), timeout=10.0)
            print("✅ Matrix state saved successfully")
        except asyncio.TimeoutError:
            print("⚠️  Saving matrix state timed out (10s), forcing shutdown...")
        except asyncio.CancelledError:
            print("⚠️  Shutdown cancelled by user")
        except Exception as e:
            print(f"⚠️  Error saving Matrix state: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("🧹 Cleaning up runtime resources...")
            try:
                rt = server_state.matrix_runtime
                if hasattr(rt, "container_manager") and rt.container_manager:
                    cm = rt.container_manager
                    if hasattr(cm, "_container_sessions"):
                        for session in cm._container_sessions.values():
                            if hasattr(session, "process") and session.process:
                                try:
                                    session.process.kill()
                                except Exception:
                                    pass
                                session.process = None
                            session.is_active = False
                        cm._container_sessions.clear()
            except Exception:
                pass
            server_state.matrix_runtime = None
            print("✅ Runtime cleaned up")

    print("👋 AgentMatrix Server shutdown complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    config = app.state.config

    print(f"🚀 Starting AgentMatrix Server...")
    print(f"📁 Matrix World Directory: {config['matrix_world_dir']}")

    runtime = await init_runtime(config["matrix_world_dir"])
    app.state.matrix = runtime
    print("✅ Runtime initialized")

    try:
        yield
    finally:
        await graceful_shutdown()
