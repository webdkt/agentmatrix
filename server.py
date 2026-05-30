#!/usr/bin/env python3
"""
AgentMatrix Server

Entry point for the AgentMatrix backend.  All business logic lives in the
``server_handlers`` package; this file only:
  1. Sets up sys.path so ``agentmatrix`` is importable (PyInstaller-aware).
  2. Parses CLI arguments.
  3. Initialises shared path state.
  4. Creates the FastAPI ``app`` (importable as ``server:app``).
  5. Provides a ``main()`` function for direct execution.
"""

import os
import sys
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path setup — PyInstaller bundles data under sys._MEIPASS
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# Re-export so existing ``from agentmatrix import ...`` still works
from agentmatrix import AgentMatrix, __version__          # noqa: F401
# ConfigService has been split into agent_service, llm_service, proxy_service, email_proxy_config_service

# ---------------------------------------------------------------------------
# CLI argument parsing (must happen at import time — uvicorn references
# ``server:app`` as a string, so args are parsed before app is created).
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="AgentMatrix Server")
    parser.add_argument(
        "--matrix-world",
        type=str,
        default="./MatrixWorld",
        help="Path to the Matrix World directory (default: ./MatrixWorld)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=0, help="Port to bind to (default: 0 = OS-assigned)"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    return parser.parse_args()


# Parse args at module import time
args = parse_args()

# ---------------------------------------------------------------------------
# Initialise shared path state
# ---------------------------------------------------------------------------
from server_handlers.state import init_paths
init_paths(args)

# ---------------------------------------------------------------------------
# Create the FastAPI application
# ---------------------------------------------------------------------------
from server_handlers.app_factory import create_app
app = create_app()

# Store args/config in app.state so routes can access them
app.state.config = {
    "matrix_world_dir": args.matrix_world if hasattr(args, 'matrix_world') else None,
    "host": args.host,
    "port": args.port,
    "reload": args.reload,
}
# Will be properly populated after init_paths in the lifespan, but we
# fill in the path values now for cold-start routes that read app.state.config.
from server_handlers.state import server_state
app.state.config.update({
    "matrix_world_dir": server_state.matrix_world_dir,
    "workspace_dir": server_state.workspace_dir,
    "system_dir": server_state.system_dir,
    "configs_dir": server_state.configs_dir,
    "agents_dir": server_state.agents_dir,
    "llm_config_path": server_state.llm_config_path,
    "system_config_path": server_state.system_config_path,
    "email_proxy_config_path": server_state.email_proxy_config_path,
})

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    """Main entry point"""
    import uvicorn
    import signal
    import asyncio

    print("""
    ╔═══════════════════════════════════════╗
    ║       AgentMatrix Server v0.7.0.15    ║
    ╚═══════════════════════════════════════╝
    """)

    try:
        config = uvicorn.Config(app, host=args.host, port=args.port, reload=args.reload)
        server = uvicorn.Server(config)

        def handle_signal(signum, frame):
            print(f"\n🔔 Received signal {signum}, initiating graceful shutdown...")
            server.should_exit = True
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        # Override server startup to write port file (for Tauri discovery)
        original_startup = server.startup
        async def startup_with_port_file(sockets=None):
            await original_startup(sockets=sockets)
            if server.servers:
                actual_port = server.servers[0].sockets[0].getsockname()[1]
                app.state.actual_port = actual_port
                server_state.actual_port = actual_port
                port_file = server_state.matrix_world_dir / ".matrix" / "backend_port"
                port_file.parent.mkdir(parents=True, exist_ok=True)
                port_file.write_text(str(actual_port))
                print(f"🔌 Backend port: {actual_port} (written to {port_file})")
        server.startup = startup_with_port_file

        server.run()
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    main()
