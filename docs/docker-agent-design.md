# Docker 容器化 Agent 设计方案

## 核心思路

每个 Agent 对应一个 Docker 容器，就像给每个 Agent 分配了一台独立的"电脑"。

## 宿主目录结构

```
/opt/agentmatrix/
├── skills/                    # 全局 SKILLS（只读）
│   ├── git-workflow/
│   │   └── skill.md
│   └── code-review/
│       └── skill.md
│
├── agent_home/                # Agent Home（持久化）
│   ├── MyAgent/
│   │   ├── plan.md
│   │   ├── notes.md
│   │   └── knowledge/
│   └── AnotherAgent/
│       └── ...
│
└── sessions/                  # Session 工作区（临时）
    ├── session_20250223_001/
    │   ├── history.json
    │   ├── context.json
    │   └── workspace/
    │       ├── draft.md
    │       └── output.txt
    │
    └── session_20250223_002/
        └── workspace/
            └── ...
```

## 容器内视角

```bash
/
├── skills/        → /opt/agentmatrix/skills (ro, 只读挂载)
├── home/          → /opt/agentmatrix/agent_home/{AgentName} (rw, 读写挂载)
├── sessions/      → /opt/agentmatrix/sessions (rw, 挂载父目录)
└── workspace/     → /sessions/{session_id}/workspace (符号链接)
```

**Agent 使用体验**：
```python
# 自然路径语义
file.read("skills/git-workflow/skill.md")  # ✅ 全局技能
file.read("~/plan.md")                      # ✅ Agent Home
file.write("workspace/draft.md")            # ✅ 当前工作区
```

## Docker 实现细节

### 1. Dockerfile

见项目根目录的 `Dockerfile`。

**包含内容**：
- Python 3.12
- 基础工具（bash, curl, git, vim）
- Docker SDK

**注意**：容器内只包含 File skill 需要的基础环境，browser skill 等重载依赖在宿主机。

---

### 2. requirements-docker.txt

见项目根目录的 `requirements-docker.txt`。

**包含内容**：
- `docker>=6.0.0`（Docker SDK）

---

### 3. 构建镜像

```bash
# 在项目根目录执行
docker build -t agentmatrix:latest .
```

这一步会：
- 拉取 Python 3.12 基础镜像
- 安装 bash, curl, git 等基础工具
- 安装 Docker SDK
- 创建必要的目录结构

---

### 4. 验证镜像

```bash
# 检查镜像
docker images | grep agentmatrix

# 测试容器
docker run --rm agentmatrix:latest python --version
docker run --rm agentmatrix:latest bash -c "which bash curl git"
```

预期输出：
```
Python 3.12.x
/bin/bash
/usr/bin/curl
/usr/bin/git
```

---

### 5. 容器创建

```python
import docker
from pathlib import Path

def create_agent_container(agent_name: str, workspace_root: str) -> str:
    """创建 Agent 容器"""
    client = docker.from_env()

    # 准备挂载点
    skills_dir = Path(workspace_root) / "skills"
    agent_home = Path(workspace_root) / "agent_home" / agent_name
    sessions_dir = Path(workspace_root) / "sessions"

    agent_home.mkdir(parents=True, exist_ok=True)

    volumes = {
        str(skills_dir): {'bind': '/skills', 'mode': 'ro'},
        str(agent_home): {'bind': '/home', 'mode': 'rw'},
        str(sessions_dir): {'bind': '/sessions', 'mode': 'rw'},  # 挂载父目录
    }

    container = client.containers.run(
        image="agentmatrix:latest",
        name=f"agent_{agent_name}",
        volumes=volumes,
        detach=True,
        remove=False,
        stdin_open=True,
        tty=True
    )

    return container.id
```

### 3. 使用示例

```python
# 创建容器
container_id = create_agent_container("MyAgent", "/opt/agentmatrix")

# 使用示例
client = docker.from_env()
container = client.containers.get(container_id)

# Session 1
attach_workspace(container, "session_20250223_001")
container.exec_run("cat /skills/git-workflow/skill.md")
container.exec_run("echo 'First task' > /home/plan.md")
container.exec_run("echo 'Work here' > /workspace/draft.md")

# Session 2
attach_workspace(container, "session_20250223_002")
container.exec_run("cat /home/plan.md")  # 同一个 Home
container.exec_run("ls /workspace/")    # 新的工作区
```

## Workspace 动态切换

**方案**：挂载 sessions 父目录 + 符号链接切换

```python
def attach_workspace(container, session_id: str):
    """切换 workspace 到指定 session"""
    # 删除旧链接
    container.exec_run("rm -rf /workspace")

    # 创建新符号链接（指向 /sessions/{session_id}/workspace）
    container.exec_run(f"ln -s /sessions/{session_id}/workspace /workspace")
```

**优势**：
- ✅ 无需停止容器
- ✅ 瞬间切换（< 0.01s）
- ✅ 简单可靠

**备选方案**（如果符号链接有问题）：

```python
# bind mount 方案（需要 privileged 权限）
container.exec_run(
    f"mount --bind /sessions/{session_id}/workspace /workspace",
    privileged=True
)
```

---

## File Skill 适配

容器化后，**所有 file 操作都在容器内执行**，不再在宿主机执行。

### 执行流程

```
Agent 调用
  ↓
Docker API (container.exec_run)
  ↓
容器内执行（bash, read, write 等都在容器内）
  ↓
返回结果到 Agent
```

### 容器职责划分

**容器内执行**：
- ✅ File skill（bash, read, write, list, search）
- ✅ 基础文件操作
- ✅ 简单脚本执行

**宿主机执行**：
- ✅ Browser skill（需要 Playwright/浏览器）
- ✅ PDF 处理（需要 marker-pdf）
- ✅ 其他重载依赖

### 关键特性

- ✅ **完全隔离**：所有 file 操作在容器内，无法访问宿主机
- ✅ **无需路径转换**：容器内路径简单自然（/skills, /home, /workspace）
- ✅ **安全边界**：容器文件系统隔离

### 方法示例

```python
class DockerFileSkillMixin:
    """容器化 File Skill"""

    async def bash(self, command: str, timeout: int = 30):
        """容器内执行 bash"""
        result = self.container.exec_run(
            f"bash -c '{command}'",
            workdir='/workspace',
            timeout=timeout
        )
        return result.output.decode('utf-8')

    async def read(self, file_path: str):
        """容器内读取文件"""
        result = self.container.exec_run(f"cat {file_path}")
        return result.output.decode('utf-8')

    async def write(self, file_path: str, content: str):
        """容器内写入文件"""
        cmd = f"cat > {file_path} << 'EOF'\n{content}\nEOF"
        result = self.container.exec_run(cmd)
        return "文件已写入"
```

**注意**：所有 file 操作（bash, read, write, list, search）都通过 `container.exec_run()` 在容器内执行。

---

## 优势总结

### ✅ 安全性
- SKILLS 真正只读（容器级隔离）
- 无法访问宿主文件系统
- 无法访问其他 Agent 的 Home

### ✅ 隔离性
- 每个 Agent 独立环境
- 不会相互干扰
- 资源限制（CPU、内存）

### ✅ 自然语义
- Agent 使用简单路径
- 无需理解复杂的路径映射
- 符合直觉（就像用一台电脑）

### ✅ 持久化
- Agent Home 跨 Session 保存
- Workspace 按 Session 隔离
- SKILLS 全局共享

### ✅ 可管理性
- 容器生命周期管理
- 资源监控
- 日志收集

---

## 容器生命周期管理

### Docker 状态映射

| 概念 | Docker 命令 | 时间 | 说明 |
|------|-----------|------|------|
| 开机 | `docker start` | 0.3s | 从停止状态启动 |
| 关机 | `docker stop` | 0.5s | 停止容器（保留数据） |
| 休眠 | `docker pause` | 0.2s | 冻结容器 |
| 唤醒 | `docker unpause` | 0.1s | 从休眠恢复 |
| 销毁 | `docker rm` | - | 删除容器（慎用） |

### BaseAgent 集成

```python
class BaseAgent:
    def __init__(self, name: str, workspace_root: str):
        self.name = name
        self.container_id = None
        self._ensure_container_exists()  # 检查/创建容器

    def _ensure_container_exists(self):
        """确保容器存在"""
        import docker
        from pathlib import Path

        client = docker.from_env()

        # 查找现有容器
        try:
            container = client.containers.get(f"agent_{self.name}")
            self.container_id = container.id
        except NotFound:
            # 创建新容器
            workspace = Path(self.workspace_root)
            volumes = {
                str(workspace / "skills"): {'bind': '/skills', 'mode': 'ro'},
                str(workspace / "agent_home" / self.name): {'bind': '/home', 'mode': 'rw'},
                str(workspace / "sessions"): {'bind': '/sessions', 'mode': 'rw'},  # 挂载父目录
            }

            container = client.containers.run(
                image="agentmatrix:latest",
                name=f"agent_{self.name}",
                volumes=volumes,
                detach=True,
                remove=False
            )
            self.container_id = container.id

    async def process_email(self, email: dict):
        """处理邮件（主入口）"""
        # 1. 唤醒
        self._wakeup()

        try:
            # 2. 切换 workspace
            session_id = email["user_session_id"]
            self._attach_workspace(session_id)

            # 3. 处理
            await self._process_email_internal(email)

        finally:
            # 4. 休眠
            self._hibernate()

    def _wakeup(self):
        """唤醒容器"""
        import docker
        client = docker.from_env()
        container = client.containers.get(self.container_id)

        if container.status == "paused":
            container.unpause()
        elif container.status == "exited":
            container.start()

    def _hibernate(self):
        """休眠容器"""
        import docker
        client = docker.from_env()
        container = client.containers.get(self.container_id)

        if container.status == "running":
            container.pause()

    def _attach_workspace(self, session_id: str):
        """切换 workspace（符号链接方案）"""
        import docker
        client = docker.from_env()
        container = client.containers.get(self.container_id)

        # 切换符号链接（指向 /sessions/{session_id}/workspace）
        container.exec_run("rm -rf /workspace")
        container.exec_run(f"ln -s /sessions/{session_id}/workspace /workspace")

    @classmethod
    def shutdown_all(cls):
        """系统退出时关机所有容器"""
        import docker
        client = docker.from_env()

        for container in client.containers.list(filters={"name": "agent_"}):
            container.stop()  # 关机，不销毁
```

### 生命周期流程

```
1. BaseAgent.__init__()
   └─ _ensure_container_exists()
      ├─ 找到现有容器 → 复用
      └─ 未找到 → 创建新容器

2. process_email()
   ├─ _wakeup()        ← 唤醒（0.1-0.3s）
   ├─ _attach_workspace() ← 切换工作目录
   ├─ 处理邮件
   └─ _hibernate()     ← 休眠（0.2s）

3. 系统退出
   └─ BaseAgent.shutdown_all()
      └─ docker stop (所有容器，保留数据)
```

### Mac 环境注意

| 特性 | 说明 |
|------|------|
| **内存占用** | 基础 400MB + 每容器 100MB |
| **性能** | Volume 挂载使用 `cached` 模式优化 |
| **路径限制** | 容器内路径短（`/workspace`），宿主机长路径不影响 |
