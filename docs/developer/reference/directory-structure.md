# Directory Structure

AgentMatrix 目录结构规范。

## 根目录

```
MatrixWorld/                    # matrix_path (默认 ./MatrixWorld/)
├── .matrix/                    # 系统数据（自动生成）
└── workspace/                  # 用户工作区
```

## .matrix/ 系统目录

| 路径 | 用途 |
|------|------|
| `.matrix/configs/` | 配置文件 |
| `.matrix/configs/agents/` | Agent profiles |
| `.matrix/configs/agents/llm_config.json` | LLM 后端配置 |
| `.matrix/database/` | SQLite 数据库 |
| `.matrix/logs/` | 日志文件 |
| `.matrix/sessions/` | Agent 会话历史 |
| `.matrix/browser_profile/` | 浏览器配置文件 |

## workspace/ 工作区

| 路径 | 用途 |
|------|------|
| `workspace/SKILLS/` | 用户自定义 Skills |
| `workspace/agent_files/{agent}/work_files/{task}/` | Agent 工作文件 |
| `workspace/agent_files/{agent}/work_files/{task}/attachments/` | 邮件附件 |
| `workspace/agent_files/{agent}/home/` | Agent home 目录 |

## MatrixPaths API

运行时通过 `runtime.paths` 访问路径：

```python
# 系统目录
paths.system_dir              # .matrix/
paths.config_dir              # .matrix/configs/
paths.agent_config_dir        # .matrix/configs/agents/
paths.database_dir            # .matrix/database/
paths.logs_dir                # .matrix/logs/
paths.sessions_dir            # .matrix/sessions/

# 工作区目录
paths.workspace_dir           # workspace/

# Agent 特定目录
paths.get_agent_session_dir(agent, session)
paths.get_agent_session_history_dir(agent, session)
paths.get_agent_work_base_dir(agent)
paths.get_agent_work_files_dir(agent, task)
paths.get_agent_attachments_dir(agent, task)
paths.get_agent_home_dir(agent)
paths.get_skills_dir()        # workspace/SKILLS/
```

## 路径获取示例

```python
# 在 Agent 或 Skill 中
work_dir = self.runtime.paths.get_agent_work_files_dir(
    self.name, 
    self.current_task_id
)
file_path = work_dir / "output.txt"
```

## 初始化

系统启动时自动创建：

```python
paths.ensure_directories()
```

不应手动创建目录，使用 API 获取路径。
