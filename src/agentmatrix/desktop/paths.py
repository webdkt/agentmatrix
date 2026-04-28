"""
MatrixPaths - Matrix路径管理器

职责：
1. 统一管理所有路径
2. 提供清晰的路径访问接口
3. 隐藏系统目录的复杂性
"""

from pathlib import Path
from typing import Optional
import os


class MatrixPaths:
    """
    Matrix路径管理器

    统一管理所有路径，提供清晰的访问接口
    """

    def __init__(self, matrix_root: str):
        """
        初始化路径管理器

        Args:
            matrix_root: Matrix World根目录
        """
        self.matrix_root = Path(matrix_root).resolve()

    @property
    def system_dir(self) -> Path:
        """系统目录：.matrix"""
        return self.matrix_root / ".matrix"

    @property
    def workspace_dir(self) -> Path:
        """工作区目录：workspace"""
        return self.matrix_root / "workspace"

    @property
    def config_dir(self) -> Path:
        """配置目录：.matrix/configs"""
        return self.system_dir / "configs"

    @property
    def agent_config_dir(self) -> Path:
        """Agent配置目录：.matrix/configs/agents"""
        return self.config_dir / "agents"

    @property
    def llm_config_path(self) -> Path:
        """LLM配置文件：.matrix/configs/llm_config.json"""
        return self.config_dir / "llm_config.json"

    @property
    def system_config_path(self) -> Path:
        """系统配置文件：.matrix/configs/system_config.yml"""
        return self.config_dir / "system_config.yml"

    @property
    def env_path(self) -> Path:
        """环境变量文件：.matrix/configs/.env"""
        return self.config_dir / ".env"

    @property
    def email_proxy_config_path(self) -> Path:
        """Email Proxy配置文件：.matrix/configs/email_proxy_config.yml"""
        return self.config_dir / "email_proxy_config.yml"

    @property
    def prompts_dir(self) -> Path:
        """Prompt 目录：.matrix/configs/prompts"""
        return self.config_dir / "prompts"

    @property
    def backup_dir(self) -> Path:
        """备份目录：.matrix/configs/backups/"""
        return self.config_dir / "backups"

    @property
    def agent_backup_dir(self) -> Path:
        """Agent备份目录：.matrix/configs/backups/agents/"""
        return self.backup_dir / "agents"

    @property
    def database_dir(self) -> Path:
        """数据库目录：.matrix/database"""
        return self.system_dir / "database"

    @property
    def database_path(self) -> Path:
        """数据库文件：.matrix/database/agentmatrix.db"""
        return self.database_dir / "agentmatrix.db"

    @property
    def logs_dir(self) -> Path:
        """日志目录：.matrix/logs"""
        return self.system_dir / "logs"

    @property
    def sessions_dir(self) -> Path:
        """Session目录：.matrix/sessions"""
        return self.system_dir / "sessions"

    @property
    def browser_profile_dir(self) -> Path:
        """Browser profile目录：.matrix/browser_profile"""
        return self.system_dir / "browser_profile"

    @property
    def snapshot_path(self) -> Path:
        """Matrix快照文件：.matrix/matrix_snapshot.json"""
        return self.system_dir / "matrix_snapshot.json"

    def get_agent_session_dir(self, agent_name: str, session_id: str) -> Path:
        """
        获取Agent的特定session目录

        Args:
            agent_name: Agent名称
            session_id: Session ID

        Returns:
            Path: .matrix/sessions/{agent_name}/{session_id}/
        """
        return self.sessions_dir / agent_name / session_id

    def get_agent_session_history_dir(self, agent_name: str, session_id: str) -> Path:
        """
        获取Agent的session history目录

        Args:
            agent_name: Agent名称
            session_id: Session ID

        Returns:
            Path: .matrix/sessions/{agent_name}/{session_id}/history.json
        """
        return self.sessions_dir / agent_name / session_id / "history.json"

    def get_agent_work_base_dir(self, agent_name: str) -> Path:
        """
        获取Agent的work_files目录

        Args:
            agent_name: Agent名称
            task_id: 用户会话ID

        Returns:
            Path: workspace/agent_files/{agent_name}/work_files/{task_id}/
        """
        return self.workspace_dir / "agent_files" / agent_name / "work_files"

    def get_agent_work_files_dir(self, agent_name: str, task_id: str) -> Path:
        """
        获取Agent的work_files目录

        Args:
            agent_name: Agent名称
            task_id: 用户会话ID

        Returns:
            Path: workspace/agent_files/{agent_name}/work_files/{task_id}/
        """
        return self.workspace_dir / "agent_files" / agent_name / "work_files" / task_id

    def get_agent_home_dir(self, agent_name: str) -> Path:
        """
        获取Agent的home目录

        Args:
            agent_name: Agent名称

        Returns:
            Path: workspace/agent_files/{agent_name}/home/
        """
        return self.workspace_dir / "agent_files" / agent_name / "home"

    def get_agent_attachments_dir(self, agent_name: str, task_id: str) -> Path:
        """
        获取Agent的attachments目录

        Args:
            agent_name: Agent名称
            task_id: 用户会话ID

        Returns:
            Path: workspace/agent_files/{agent_name}/work_files/{task_id}/attachments/
        """
        return self.get_agent_work_files_dir(agent_name, task_id) / "attachments"

    def get_browser_profile_dir(self, agent_name: str) -> Path:
        """
        获取Agent的browser profile目录

        Args:
            agent_name: Agent名称

        Returns:
            Path: .matrix/browser_profile/{agent_name}/
        """
        return self.browser_profile_dir / agent_name

    def get_skills_dir(self) -> Path:
        """
        获取workspace的skills目录（共享）

        Returns:
            Path: workspace/SKILLS/
        """
        return self.workspace_dir / "SKILLS"

    def get_agent_skills_dir(self, agent_name: str) -> Path:
        """
        获取Agent私有的Skills目录

        Args:
            agent_name: Agent名称

        Returns:
            Path: workspace/agent_files/{agent_name}/home/SKILLS/
        """
        return self.get_agent_home_dir(agent_name) / "SKILLS"

    def ensure_directories(self) -> None:
        """
        确保所有必需的目录存在

        创建以下目录：
        - .matrix/
        - .matrix/configs/
        - .matrix/configs/agents/
        - .matrix/database/
        - .matrix/logs/
        - .matrix/sessions/
        - .matrix/email_attachments/
        - .matrix/browser_profile/
        - workspace/
        - workspace/agent_files/
        - workspace/SKILLS/
        """
        directories = [
            self.system_dir,
            self.config_dir,
            self.agent_config_dir,
            self.database_dir,
            self.logs_dir,
            self.sessions_dir,
            self.browser_profile_dir,
            self.workspace_dir,
            self.workspace_dir / "agent_files",
            self.get_skills_dir(),
            self.backup_dir,
            self.agent_backup_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return f"MatrixPaths(matrix_root='{self.matrix_root}')"

    def container_path_to_host(
        self, container_path: str, agent_name: str, task_id: str
    ) -> Optional[Path]:
        """
        将容器内路径转换为宿主路径

        路径映射规则：
        - ~ → workspace/agent_files/{agent_name}/home/
        - ~/current_task → workspace/agent_files/{agent_name}/work_files/{task_id}/
        - /data/agents/{agent_name}/ → workspace/agent_files/{agent_name}/

        Args:
            container_path: 容器内路径（如 ~/current_task/data.txt）
            agent_name: Agent 名称
            task_id: 任务 ID

        Returns:
            宿主路径对象，如果路径无法转换则返回 None
        """
        # 1. 处理 ~ 开头的路径
        if container_path.startswith("~"):
            # ~/current_task → 工作目录
            if container_path == "~/current_task" or container_path.startswith(
                "~/current_task/"
            ):
                relative_path = container_path[len("~/current_task/") :].lstrip("/")
                host_dir = self.get_agent_work_files_dir(agent_name, task_id)
                return host_dir / relative_path if relative_path else host_dir

            # ~ 或 ~/xxx → home目录
            relative_path = container_path[len("~/") :].lstrip("/")
            host_dir = self.get_agent_home_dir(agent_name)
            return host_dir / relative_path if relative_path else host_dir

        # 2. 处理 /data/agents/{agent_name}/ 开头的路径
        container_base = f"/data/agents/{agent_name}/"
        if container_path.startswith(container_base):
            relative_path = container_path[len(container_base) :].lstrip("/")
            host_base = self.workspace_dir / "agent_files" / agent_name
            return host_base / relative_path

        # 3. 其他路径（如 /tmp, /proc 等）返回 None，需要通过容器执行
        return None

