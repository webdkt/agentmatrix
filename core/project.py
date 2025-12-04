# core/project.py
import os
import json
import shutil
from pathlib import Path

class ProjectContext:
    def __init__(self, root_path: str):
        self.root = Path(root_path).resolve()
        
        # 定义标准目录结构
        self.system_dir = self.root / ".agent_matrix"
        self.input_dir = self.root / "inputs"
        self.output_dir = self.root / "outputs"
        self.workspace_dir = self.root / "workspace"
        
        self.config_file = self.system_dir / "matrix.json"
        self.snapshot_file = self.system_dir / "world_snapshot.json"
        self.db_file = self.system_dir / "matrix.db"

    def init_project(self, name: str, goal: str):
        """初始化一个新的项目结构"""
        # 创建目录
        for p in [self.system_dir, self.input_dir, self.output_dir, self.workspace_dir]:
            p.mkdir(parents=True, exist_ok=True)
            
        # 创建配置文件
        config = {
            "project_name": name,
            "goal": goal,
            "created_at": str(datetime.now())
        }
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        print(f"Project '{name}' initialized at {self.root}")

    def load_config(self):
        if not self.config_file.exists():
            raise FileNotFoundError("不是有效的 AgentMatrix 项目")
        with open(self.config_file, 'r') as f:
            return json.load(f)

    def resolve_path(self, relative_path: str) -> str:
        """
        [安全沙箱] 将 Agent 请求的相对路径转为绝对路径
        并防止 Agent 访问项目外部文件 (Path Traversal Attack)
        """
        # 强制 Agent 只能在 root 下操作
        target = (self.root / relative_path).resolve()
        if not str(target).startswith(str(self.root)):
            raise PermissionError(f"Access Denied: Agent 试图访问项目外部路径 {target}")
        return str(target)