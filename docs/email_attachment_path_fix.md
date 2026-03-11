# 邮件附件路径修复

## 修复时间
2026-03-11

## 问题描述

`_copy_attachments_to_recipient` 方法中的附件源路径逻辑错误：

### 错误的逻辑
```python
# 错误：假设附件已经在发送者的 attachments 目录下
source_attachments_dir = (
    Path(workspace_root) / "agent_files" / source_agent / "work_files" / user_session_id / "attachments"
)
source_file = source_attachments_dir / filename
```

### 正确的逻辑
附件应该从 Agent 的当前工作目录（容器内的 `/work_files`）或其他容器路径中复制，而不是从 `attachments` 目录。

## 修复内容

### 1. 新增 `_resolve_container_path_to_host` 方法

```python
def _resolve_container_path_to_host(self, container_path: str, user_session_id: str) -> str:
    """
    将容器内路径转换为宿主机路径

    路径映射规则：
    - 相对路径（如 'report.pdf'）→ 相对于 /work_files
    - /work_files/test.md → {workspace_root}/agent_files/{agent_name}/work_files/{session_id}/test.md
    - /home/plan.md → {workspace_root}/agent_files/{agent_name}/home/plan.md
    - 其他路径 → 直接返回（假设是宿主机路径）
    """
```

**路径映射逻辑**：

1. **相对路径** (`report.pdf`)
   - 解析为：`{work_files_base}/{user_session_id}/report.pdf`
   - 示例：`/MatrixWorld/agent_files/Mark/work_files/session123/report.pdf`

2. **/work_files/* 路径** (`/work_files/data/report.pdf`)
   - 解析为：`{work_files_base}/{user_session_id}/data/report.pdf`
   - 示例：`/MatrixWorld/agent_files/Mark/work_files/session123/data/report.pdf`

3. **/home/* 路径** (`/home/config.json`)
   - 解析为：`{agent_home}/config.json`
   - 示例：`/MatrixWorld/agent_files/Mark/home/config.json`

4. **其他路径**
   - 直接返回（假设是宿主机路径或会通过其他方式处理）

### 2. 修改 `_copy_attachments_to_recipient` 方法

**主要变更**：
- 移除了错误的 `source_attachments_dir` 逻辑
- 使用 `_resolve_container_path_to_host` 解析容器路径
- 支持多种容器路径格式

**修改前**：
```python
source_attachments_dir = (
    Path(workspace_root) / "agent_files" / source_agent / "work_files" / user_session_id / "attachments"
)
source_file = source_attachments_dir / filename
```

**修改后**：
```python
# 将容器内路径转换为宿主机路径
host_path = self._resolve_container_path_to_host(container_path, user_session_id)

if host_path is None or not Path(host_path).exists():
    self.logger.warning(f"附件文件不存在：{container_path} (解析后的宿主机路径: {host_path})")
    continue

source_file = Path(host_path)
```

## 技术细节

### 复用的组件

该方法复用了 `self.root_agent.docker_manager` 的属性：
- `docker_manager.work_files_base` - 对应容器内的 `/work_files`
- `docker_manager.agent_home` - 对应容器内的 `/home`

### 容器路径映射

容器内的路径映射到宿主机：

| 容器内路径 | 宿主机路径 |
|-----------|----------|
| `/work_files` | `{workspace_root}/agent_files/{agent_name}/work_files/{session_id}` |
| `/home` | `{workspace_root}/agent_files/{agent_name}/home` |
| `/SKILLS` | `{workspace_root}/SKILLS` (只读) |

### 使用示例

```python
# Agent 发送邮件时
await self.send_email(
    to="Mark",
    body="请查收报告",
    attachments=[
        "report.pdf",                    # 相对路径
        "/work_files/data/analysis.xlsx", # 绝对路径
        "/home/config/settings.json"      # home 目录
    ]
)
```

## 测试建议

1. **测试相对路径**
   - 创建文件：`/work_files/test.txt`
   - 发送邮件：`attachments=["test.txt"]`
   - 验证：文件是否被正确复制到收件人的 attachments 目录

2. **测试绝对路径**
   - 创建文件：`/work_files/data/report.pdf`
   - 发送邮件：`attachments=["/work_files/data/report.pdf"]`
   - 验证：文件是否被正确复制

3. **测试 home 目录**
   - 创建文件：`/home/config.json`
   - 发送邮件：`attachments=["/home/config.json"]`
   - 验证：文件是否被正确复制

4. **测试不存在的文件**
   - 发送邮件：`attachments=["nonexistent.pdf"]`
   - 验证：是否正确跳过并记录警告日志

## 相关文件

- 修改：`src/agentmatrix/skills/email/skill.py`
- 相关：`src/agentmatrix/core/docker_manager.py` (DockerContainerManager)
- 相关：`src/agentmatrix/skills/markdown/skill.py` (类似的路由逻辑)

## 总结

修复了邮件附件的源路径解析逻辑，使其能够：
1. ✅ 正确处理相对路径（相对于 `/work_files`）
2. ✅ 正确处理绝对路径（`/work_files/*`, `/home/*`）
3. ✅ 复用现有的 Docker 路径映射逻辑
4. ✅ 提供清晰的错误日志

现在 Agent 可以发送任意位置的文件作为附件，只要文件在容器的标准路径下。
