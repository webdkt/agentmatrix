# AgentMatrix 目录规范

## Matrix World 结构

```
MatrixWorld/                    ← matrix_path (默认 ./MatrixWorld/)
├── .matrix/                    ← 运行时数据（自动生成）
│   ├── logs/                   ← 日志
│   ├── agentmatrix.db         ← 邮件数据库
│   └── matrix_snapshot.json    ← 世界快照
├── agents/                     ← Agent 配置
├── workspace/                  ← 工作空间
│   └── agent_files/            ← Agent 文件（容器挂载）
│       └── {agent_name}/       ← Agent 名称
│           ├── home/           ← Agent Home（容器内 /home）
│           └── work_files/     ← 工作文件（容器内 /work_files_base）
│               └── {task_id}/  ← 任务ID
│                   └── attachments/      ← 邮件附件（新）
│                       └── {filename}    ← 文件名（可能重命名）
└── matrix_world.yml            ← 配置文件
```

## 容器挂载映射

### Agent 容器挂载点

| 容器内路径 | 宿主机路径 | 权限 | 说明 |
|-----------|-----------|------|------|
| `/SKILLS` | `workspace_root/SKILLS` | ro | 全局技能目录 |
| `/home` | `workspace_root/agent_files/{agent_name}/home` | rw | Agent Home |
| `/work_files_base` | `workspace_root/agent_files/{agent_name}/work_files` | rw | 所有 session 工作文件父目录 |
| `/work_files` | 符号链接 → `/work_files_base/{task_id}` | rw | 当前 task 工作文件（动态切换） |

### 容器内路径说明

- **`/work_files`**：符号链接，通过 `switch_workspace(task_id)` 动态切换
- **`/work_files/attachments/`**：邮件附件保存目录
- 对应宿主机路径：`workspace_root/agent_files/{agent_name}/work_files/{task_id}/attachments/`

## 邮件附件存储（新）

**宿主机路径**：`{workspace_root}/agent_files/{agent_name}/work_files/{task_id}/attachments/{filename}`

**容器内路径**：`/work_files/attachments/{filename}`

**文件覆盖规则**：
- 同名文件直接覆盖（新版本覆盖旧版本）
- 一个 session 里不应该有重名，有需要避开的用户一开始就用不同的文件名

**Email 显示**：
- 用户看到：`Attachments:\n  - abc-1.txt`
- Agent 看到：`附件已保存在 /work_files/attachments/abc-1.txt`

**示例代码**：
```python
# server.py - 保存附件
workspace_root = user_agent.workspace_root
agent_name = user_agent.name
attachments_dir = Path(workspace_root) / "agent_files" / agent_name / "work_files" / task_id / "attachments"
attachments_dir.mkdir(parents=True, exist_ok=True)

# 处理重名并保存
final_filename = get_unique_filename(attachments_dir, original_filename)
final_path = attachments_dir / final_filename
with open(final_path, 'wb') as f:
    f.write(content)

# metadata 只保存最终文件名
attachment_metadata.append({
    'filename': final_filename,
    'size': len(content),
    'container_path': f'/work_files/attachments/{final_filename}'
})
```

## 邮件附件存储（旧 - 已废弃）

**旧路径**：`{matrix_path}/.matrix/email_attachments/{task_id}/{email_id}/{filename}`

**注意**：此路径已废弃，仅保留用于历史记录。新代码请使用 `work_files/attachments/` 路径。

## 路径构建规范

**统一格式**：使用 `pathlib.Path` 或 `os.path.join()`

**示例**：
```python
from pathlib import Path

# 附件目录（新）
attachments_dir = Path(workspace_root) / "agent_files" / agent_name / "work_files" / task_id / "attachments"

# 日志目录
log_path = Path(matrix_path) / ".matrix" / "logs"

# 数据库
db_path = Path(matrix_path) / ".matrix" / "agentmatrix.db"
```

## 关键点

1. **workspace_root** = 工作空间根目录（默认 `./MatrixWorld/workspace/`）
2. **matrix_path** = Matrix World 目录（默认 `./MatrixWorld/`）
3. 容器内 `/work_files` 是符号链接，动态切换到不同 session
4. 附件保存在 Agent 的 work_files 目录下，按 session 隔离
5. 文件重名自动处理，只保留最终文件名
