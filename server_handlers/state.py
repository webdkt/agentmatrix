"""
Shared server state.

All mutable global state lives here so every module can import
and mutate the same references.
"""

from pathlib import Path


class _ServerState:
    # Mutable runtime state
    matrix_runtime = None
    active_websockets: list = []

    # CLI args (set by init_paths)
    args = None

    # Actual bound port (set by server startup after sockets are bound)
    actual_port: int = 0

    # Path configuration (set by init_paths)
    matrix_world_dir: Path = None
    workspace_dir: Path = None
    system_dir: Path = None
    configs_dir: Path = None
    agents_dir: Path = None
    llm_config_path: Path = None
    system_config_path: Path = None
    email_proxy_config_path: Path = None


server_state = _ServerState()


def init_paths(parsed_args):
    """Initialize all path variables from parsed CLI arguments."""
    server_state.args = parsed_args

    matrix_world_dir = Path(parsed_args.matrix_world).resolve()
    server_state.matrix_world_dir = matrix_world_dir
    server_state.workspace_dir = matrix_world_dir / "workspace"

    system_dir = matrix_world_dir / ".matrix"
    configs_dir = system_dir / "configs"
    agents_dir = configs_dir / "agents"

    server_state.system_dir = system_dir
    server_state.configs_dir = configs_dir
    server_state.agents_dir = agents_dir
    server_state.llm_config_path = agents_dir / "llm_config.json"
    server_state.system_config_path = configs_dir / "system_config.yml"
    server_state.email_proxy_config_path = configs_dir / "email_proxy_config.yml"
