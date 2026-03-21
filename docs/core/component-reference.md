# AgentMatrix Core - 组件参考手册

**版本**: v1.0
**最后更新**: 2026-03-19

---

## 📋 目录

- [核心组件](#核心组件)
- [Agent类型](#agent类型)
- [技能系统](#技能系统)
- [服务层](#服务层)
- [后端组件](#后端组件)
- [数据库组件](#数据库组件)
- [工具模块](#工具模块)

---

## 核心组件

### AgentMatrix (Runtime)

**位置**: `src/agentmatrix/core/runtime.py`

**描述**: 系统主容器，负责初始化和协调所有组件

**主要功能**:
- 管理所有Agent实例
- 初始化系统资源（PostOffice、配置、日志等）
- 提供Agent生命周期管理
- 协调消息传递

**关键方法**:
```python
class AgentMatrix:
    def __init__(self, config_path: str = None)
    def start(self) -> None
    def stop(self) -> None
    def register_agent(self, agent_class: Type[BaseAgent]) -> None
    def get_agent(self, agent_name: str) -> BaseAgent
```

**使用示例**:
```python
matrix = AgentMatrix(config_path="config.yaml")
matrix.start()
# ... 使用系统
matrix.stop()
```

---

### Email

**位置**: `src/agentmatrix/core/message.py`

**描述**: Agent间通信的基本单位

**数据结构**:
```python
@dataclass
class Email:
    sender: str                         # 发件人
    recipient: str                      # 收件人
    subject: str                        # 主题
    body: str                           # 正文
    in_reply_to: Optional[str]          # 回复的邮件ID
    id: str                             # 唯一ID
    timestamp: datetime                 # 时间戳
    task_id: Optional[str]              # 任务ID
    sender_session_id: Optional[str]    # 发件人会话ID
    recipient_session_id: Optional[str] # 收件人会话ID
    metadata: Dict[str, Any]            # 元数据（附件等）
```

**属性**:
- `attachments`: 附件列表（从metadata获取）

**方法**:
- `__str__()`: 格式化邮件内容

**使用示例**:
```python
email = Email(
    sender="User",
    recipient="AgentA",
    subject="Hello",
    body="How are you?"
)
```

---

### MatrixConfig

**位置**: `src/agentmatrix/core/config.py`

**描述**: 统一配置管理

**主要功能**:
- 加载和管理配置
- 配置验证
- 环境变量解析
- 默认值管理

**配置节**:
- `llm_config`: LLM配置
- `email_proxy_config`: 邮件代理配置
- `matrix_config`: Matrix配置

**使用示例**:
```python
config = MatrixConfig(config_path="config.yaml")
llm_config = config.get_llm_config()
```

---

### SessionManager

**位置**: `src/agentmatrix/core/session_manager.py`

**描述**: 会话状态管理器

**主要功能**:
- 内存缓存管理
- 磁盘懒加载/保存
- reply_mapping管理
- 自动持久化

**关键方法**:
```python
class SessionManager:
    def get_session(self, agent_name: str) -> Dict
    def save_session(self, agent_name: str, session: Dict) -> None
    def load_session(self, agent_name: str) -> Dict
    def update_reply_mapping(self, email_id: str, reply_email_id: str) -> None
```

**使用示例**:
```python
manager = SessionManager(storage_path="./sessions")
session = manager.get_session("AgentA")
session["counter"] = session.get("counter", 0) + 1
manager.save_session("AgentA", session)
```

---

---

### Cerebellum

**位置**: `src/agentmatrix/core/cerebellum.py`

**描述**: 参数解析器

**主要功能**:
- 负责参数解析和协商
- 与Brain协作
- 处理参数验证

**关键方法**:
```python
class Cerebellum:
    def parse_params(self, action: str, user_input: str) -> Dict
    def validate_params(self, action: str, params: Dict) -> bool
```

---

## Agent类型

### BaseAgent

**位置**: `src/agentmatrix/agents/base.py`

**描述**: 基础Agent类，所有持久化Agent的基类

**特点**:
- 持久化会话状态
- 完整的生命周期管理
- 支持技能组合
- 状态机管理

**状态类型**:
- `IDLE`: 空闲
- `THINKING`: 思考中
- `WORKING`: 工作中
- `WAITING_FOR_USER`: 等待用户输入

**关键方法**:
```python
class BaseAgent:
    def __init__(self, **kwargs)
    def start(self) -> None
    def stop(self) -> None
    def add_skill(self, skill: BaseSkill) -> None
    def register_action(self, name: str, func: Callable) -> None
    def execute_action(self, action_name: str, **params) -> Any
```

**属性**:
- `agent_name`: Agent名称
- `persona`: Agent人格描述
- `skills`: 技能列表
- `session_manager`: 会话管理器

**使用示例**:
```python
agent = BaseAgent(
    agent_name="MyAgent",
    persona="You are a helpful assistant."
)
agent.add_skill(BaseSkill())
agent.start()
```

---

### MicroAgent

**位置**: `src/agentmatrix/agents/micro_agent.py`

**描述**: 轻量级临时Agent

**特点**:
- 简单的think-negotiate-act循环
- 直接继承父组件（brain、cerebellum等）
- 支持技能动态组合
- 无Session概念

**关键方法**:
```python
class MicroAgent:
    def __init__(self, **kwargs)
    def add_skill(self, skill_class: Type[BaseSkill]) -> None
    def run(self, task: str) -> str
```

**使用示例**:
```python
agent = MicroAgent(
    agent_name="TempAgent",
    persona="You are a temporary agent."
)
agent.add_skill(BaseSkill)
result = agent.run("Do something")
```

---

### PostOffice

**位置**: `src/agentmatrix/agents/post_office.py`

**描述**: 消息传递中心

**主要功能**:
- 维护Agent目录
- 异步邮件队列处理
- 邮件持久化
- Agent注册/注销

**关键方法**:
```python
class PostOffice:
    def register_agent(self, agent: BaseAgent) -> None
    def unregister_agent(self, agent_name: str) -> None
    def send_email(self, email: Email) -> None
    def get_agent_directory(self) -> Dict[str, BaseAgent]
```

**使用示例**:
```python
post_office = PostOffice()
post_office.register_agent(agent)
post_office.send_email(email)
```

---

### UserProxy

**位置**: `src/agentmatrix/agents/user_proxy.py`

**描述**: 用户代理，连接人类用户

**主要功能**:
- 处理用户输入
- 显示Agent输出
- 管理用户交互

**关键方法**:
```python
class UserProxy(BaseAgent):
    def get_user_input(self) -> str
    def display_message(self, message: str) -> None
```

---

## 技能系统

### BaseSkill

**位置**: `src/agentmatrix/skills/base/base.py`

**描述**: 基础技能类

**主要功能**:
- 提供基础Actions（获取时间、用户交互等）
- Action注册机制
- 技能组合支持

**内置Actions**:
- `get_current_time`: 获取当前时间
- `ask_user`: 向用户提问
- `wait_for_user`: 等待用户输入

**使用示例**:
```python
skill = BaseSkill()
agent.add_skill(skill)
```

---

### MarkdownSkill

**位置**: `src/agentmatrix/skills/markdown/`

**描述**: Markdown处理技能

**主要功能**:
- Markdown渲染
- 文档生成
- 格式转换

---

### SchedulerSkill

**位置**: `src/agentmatrix/skills/scheduler/`

**描述**: 调度技能

**主要功能**:
- 定时任务
- 任务调度
- 时间管理

---

### FileSkill

**位置**: `src/agentmatrix/skills/file_skill.py`

**描述**: 文件操作技能

**主要功能**:
- 文件读写
- 目录操作
- 文件搜索

---

### BrowserSkill

**位置**: `src/agentmatrix/skills/browser_skill.py`

**描述**: 浏览器自动化技能

**主要功能**:
- 网页浏览
- 元素操作
- 数据抓取

---

## 服务层

### ConfigService

**位置**: `src/agentmatrix/services/config_service.py`

**描述**: 配置服务

**主要功能**:
- 配置文件管理
- 配置读取和更新
- 配置验证

---

### EmailProxyService

**位置**: `src/agentmatrix/services/email_proxy_service.py`

**描述**: 邮件代理服务

**主要功能**:
- 邮件收发
- 邮件路由
- 邮件存储

---

## 后端组件

### LLMClient

**位置**: `src/agentmatrix/backends/llm_client.py`

**描述**: LLM客户端

**主要功能**:
- 统一的LLM调用接口
- 支持多种模型
- 处理认证和请求

**关键方法**:
```python
class LLMClient:
    def chat(self, messages: List[Dict], **kwargs) -> str
    def stream_chat(self, messages: List[Dict], **kwargs) -> Iterator
```

---

### MockLLM

**位置**: `src/agentmatrix/backends/mock_llm.py`

**描述**: 模拟LLM，用于测试

**主要功能**:
- 模拟LLM响应
- 测试支持

---

## 数据库组件

### AgentMatrixDB

**位置**: `src/agentmatrix/db/agent_matrix_db.py`

**描述**: 主数据库

**主要功能**:
- 邮件存储
- Agent状态持久化
- 配置存储

**关键方法**:
```python
class AgentMatrixDB:
    def save_email(self, email: Email) -> None
    def get_emails(self, agent_name: str) -> List[Email]
    def get_session_emails(self, session_id: str) -> List[Email]
```

---

## 工具模块

### token_utils

**位置**: `src/agentmatrix/utils/token_utils.py`

**描述**: Token计数工具

**主要功能**:
- Token计数
- 成本估算

---

### parser_utils

**位置**: `src/agentmatrix/utils/parser_utils.py`

**描述**: 解析工具

**主要功能**:
- 文本解析
- 参数提取

---

## 概念映射表

### Email ↔ 组件映射

| Email字段 | 组件 | 说明 |
|-----------|------|------|
| `sender` | PostOffice | 发件人 |
| `recipient` | PostOffice | 收件人 |
| `task_id` | SessionManager | 任务关联 |
| `sender_session_id` | SessionManager | 发件人会话 |
| `recipient_session_id` | SessionManager | 收件人会话 |
| `attachments` | AttachmentManager | 附件管理 |

### Agent ↔ 组件映射

| Agent类型 | 基类 | 会话管理 | 用途 |
|-----------|------|---------|------|
| BaseAgent | BaseAgent | SessionManager | 持久化Agent |
| MicroAgent | MicroAgent | N/A | 临时Agent |
| UserProxy | BaseAgent | SessionManager | 用户交互 |

### Skill ↔ Action映射

| Skill | Actions | 说明 |
|-------|---------|------|
| BaseSkill | get_current_time, ask_user | 基础功能 |
| FileSkill | read_file, write_file, list_files | 文件操作 |
| BrowserSkill | open_page, click, extract_text | 浏览器操作 |

---

## 相关文档

- **[架构概览](./architecture.md)** - 系统架构和设计原则
- **[Agent系统](./agent-system.md)** - Agent系统详解
- **[消息系统](./message-system.md)** - 消息传递机制
- **[会话管理](./session-management.md)** - 状态管理详解
- **[技能系统](./skill-system.md)** - 技能开发指南
- **[核心概念](../concepts/CONCEPTS.md)** - 核心概念定义

---

**维护者**: AgentMatrix Team
**下次审查**: 每季度
