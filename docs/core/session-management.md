# 会话管理详解

**版本**: v1.0
**最后更新**: 2026-03-19

---

## 📋 目录

- [Session概念](#session概念)
- [SessionManager](#sessionmanager)
- [状态持久化](#状态持久化)
- [最佳实践](#最佳实践)

---

## Session概念

### 什么是Session

Session（会话）是单个Agent的邮件往来视图，代表Agent的主观视角。

**特点**:
- 每个Agent有自己的Session视图
- A和B对话 → 有2个Session（A的和B的）
- 支持自动持久化
- 跨邮件保持状态

### Session vs Task

| 维度 | Session（会话） | Task（任务） |
|------|----------------|-------------|
| 视角 | 主观视图 | 客观工作单元 |
| 范围 | 单Agent | 跨Agent |
| 用途 | 会话列表、对话视图 | 任务追踪、文件隔离 |
| 关系 | 一个Session属于某个Agent | 一个Task可包含多个Session |

### Session数据结构

```python
{
    "session_id": "unique_id",
    "agent_name": "AgentA",
    "counter": 10,
    "last_email_id": "email_123",
    "context": {
        "key": "value"
    },
    "reply_mapping": {
        "email_123": "email_456"
    }
}
```

---

## SessionManager

### SessionManager职责

SessionManager负责：

1. **状态缓存**
   - 内存中缓存Session数据
   - 快速访问

2. **持久化**
   - 定期保存到磁盘
   - 关键操作立即保存

3. **懒加载**
   - 按需加载Session
   - 减少内存占用

4. **映射管理**
   - 维护email到session的映射
   - 支持回复链追踪

### SessionManager API

```python
class SessionManager:
    def __init__(self, storage_path: str = "./sessions"):
        """初始化SessionManager"""

    def get_session(self, agent_name: str) -> Dict:
        """获取Agent的Session"""

    def save_session(self, agent_name: str, session: Dict) -> None:
        """保存Session到磁盘"""

    def load_session(self, agent_name: str) -> Dict:
        """从磁盘加载Session"""

    def update_session(self, agent_name: str, updates: Dict) -> None:
        """更新Session数据"""

    def delete_session(self, agent_name: str) -> None:
        """删除Session"""

    def update_reply_mapping(self, email_id: str, reply_email_id: str) -> None:
        """更新回复映射"""

    def get_reply_mapping(self, email_id: str) -> Optional[str]:
        """获取回复邮件ID"""
```

### 使用SessionManager

```python
from agentmatrix.core import SessionManager

# 创建SessionManager
manager = SessionManager(storage_path="./sessions")

# 获取Session
session = manager.get_session("AgentA")

# 读取状态
counter = session.get("counter", 0)

# 更新状态
counter += 1
session["counter"] = counter

# 保存Session
manager.save_session("AgentA", session)

# 更新回复映射
manager.update_reply_mapping("email_123", "email_456")
```

---


## 状态持久化

### 持久化策略

#### 1. 自动保存

```python
class BaseAgent:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 自动保存间隔
        self.auto_save_interval = 60  # 秒
        self._start_auto_save()

    def _start_auto_save(self):
        """启动自动保存"""
        asyncio.create_task(self._auto_save_loop())

    async def _auto_save_loop(self):
        """自动保存循环"""
        while self.running:
            await asyncio.sleep(self.auto_save_interval)
            self.save_session()
```

#### 2. 关键操作保存

```python
def handle_email(self, email: Email):
    # 处理邮件
    result = self.process_email(email)

    # 关键操作后立即保存
    self.session.update({
        "last_email_id": email.id,
        "last_result": result
    })
    self.session.save()
```

#### 3. 优雅关闭保存

```python
def stop(self):
    """停止Agent"""
    # 保存Session
    self.save_session()

    # 停止运行
    self.running = False
```

### 存储格式

#### 文件结构

```
./sessions/
├── AgentA.json
├── AgentB.json
├── AgentC.json
└── ...
```

#### JSON格式

```json
{
    "session_id": "agent_a_session",
    "agent_name": "AgentA",
    "created_at": "2026-03-19T10:00:00",
    "updated_at": "2026-03-19T11:00:00",
    "data": {
        "counter": 10,
        "last_email_id": "email_123",
        "context": {
            "key": "value"
        },
        "reply_mapping": {
            "email_123": "email_456"
        }
    }
}
```

### 加载策略

#### 1. 懒加载

```python
class SessionManager:
    def __init__(self):
        self._cache = {}  # 内存缓存
        self._loaded = set()  # 已加载的Session

    def get_session(self, agent_name: str) -> Dict:
        """获取Session（懒加载）"""
        if agent_name not in self._loaded:
            self._load_session(agent_name)
            self._loaded.add(agent_name)
        return self._cache.get(agent_name, {})
```

#### 2. 启动加载

```python
class BaseAgent:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 启动时加载Session
        self.session = self.session_manager.get_session(self.agent_name)
```

---

## 最佳实践

### 1. Session设计

```python
# 好的Session设计
session = {
    "counter": 10,              # 简单计数器
    "last_email_id": "id",      # 最后处理的邮件
    "context": {                # 上下文数据
        "project": "my_project",
        "status": "active"
    },
    "history": [                # 历史记录
        {"action": "process", "time": "..."}
    ]
}

# 不好的Session设计
session = {
    "large_data": [...],        # 避免存储大量数据
    "binary_data": b"...",      # 避免二进制数据
    "temporary": {...}          # 避免临时数据
}
```

### 2. 状态更新

```python
# 好的做法：使用update()
self.session.update({
    "counter": counter + 1,
    "status": "working"
})

# 不好的做法：直接修改底层dict
self.session.data["counter"] += 1  # 失去持久化能力
```

### 3. 保存时机

```python
# 关键操作后立即保存
def important_action(self):
    result = self.do_something()
    self.session.update({"last_result": result})
    self.session.save()  # 立即保存

# 非关键操作延迟保存
def normal_action(self):
    result = self.do_something()
    self.session.update({"last_result": result})
    # 等待自动保存
```

### 4. 错误处理

```python
try:
    # 加载Session
    session = self.session_manager.load_session(agent_name)
except Exception as e:
    logger.error(f"Failed to load session: {e}")
    # 使用默认Session
    session = self.session_manager.get_default_session()
```

### 5. 性能优化

```python
# 批量更新
def batch_update(self):
    updates = {}
    for i in range(100):
        updates[f"key_{i}"] = i
    self.session.update(updates)
    self.session.save()  # 一次保存

# 而不是
for i in range(100):
    self.session.update({f"key_{i}": i})
    self.session.save()  # 100次保存
```

---

## 调试技巧

### 查看Session状态

```python
# 获取Session
session = manager.get_session("AgentA")

# 打印Session
import json
print(json.dumps(session, indent=2))

# 检查特定字段
print(f"Counter: {session.get('counter', 0)}")
```

### Session验证

```python
def validate_session(session: Dict) -> bool:
    """验证Session数据"""
    required_fields = ["session_id", "agent_name", "created_at"]
    return all(field in session for field in required_fields)
```

### Session备份

```python
import shutil
from datetime import datetime

def backup_session(manager: SessionManager, agent_name: str):
    """备份Session"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"./sessions/backups/{agent_name}_{timestamp}.json"
    shutil.copy(
        f"./sessions/{agent_name}.json",
        backup_path
    )
```

---

## 相关文档

- **[架构概览](./architecture.md)** - 系统架构
- **[组件参考](./component-reference.md)** - SessionManager API
- **[Agent系统](./agent-system.md)** - Agent状态管理
- **[核心概念](../concepts/CONCEPTS.md)** - Session概念定义

---

**维护者**: AgentMatrix Team
**下次审查**: 每季度
