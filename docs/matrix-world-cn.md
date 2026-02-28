NEED REVIEW

# Matrix World 架构

## 概述

AgentMatrix 是一个多 Agent 编排框架，管理 AI agents 的生命周期、通信和协调。本文档描述总体架构、目录结构、初始化过程和运行时执行流程。

## 项目目录结构

```
agentmatrix/
├── src/agentmatrix/
│   ├── agents/                    # Agent 实现
│   │   ├── base.py               # BaseAgent 类
│   │   ├── micro_agent.py        # MicroAgent 类
│   │   └── post_office.py        # 消息路由
│   ├── backends/                  # LLM 客户端实现
│   │   └── llm_client.py         # LLM API 封装
│   ├── core/                      # 核心基础设施
│   │   ├── runtime.py            # AgentMatrix 主类
│   │   ├── loader.py             # Agent 加载器
│   │   ├── cerebellum.py         # 参数协商器
│   │   ├── action.py             # 动作装饰器
│   │   ├── session.py            # 会话管理
│   │   └── message.py            # 邮件消息传递
│   ├── skills/                    # 技能模块
│   │   ├── filesystem.py         # 文件操作
│   │   ├── web_searcher.py       # 网络搜索
│   │   ├── deep_researcher.py    # 深度研究
│   │   ├── crawler_helpers.py    # 网页爬取
│   │   ├── notebook.py           # 笔记本管理
│   │   └── project_management.py # 项目规划
│   ├── profiles/                  # Agent 配置
│   │   ├── prompts/              # 提示词模板
│   │   └── *.yml                 # Agent 配置 YAML 文件
│   └── db/                        # 数据库层
│       └── vector_db.py          # 向量数据库 (ChromaDB)
├── docs/                          # 文档
│   ├── v0.1/                     # 归档文档
│   ├── matrix-world-cn.md        # 本文件
│   ├── agent-and-micro-agent-design-cn.md
│   └── think-with-retry-pattern-cn.md
└── examples/                      # 示例 world 和教程
    └── MyWorld/                   # 示例 world 设置
        ├── agents/                # Agent 配置文件
        └── workspace/             # 工作区数据
```

## 核心组件

### AgentMatrix 运行时

**位置**: `src/agentmatrix/core/runtime.py`

`AgentMatrix` 类是管理整个 agent world 的主入口点。

```python
class AgentMatrix:
    def __init__(self, agent_profile_path, matrix_path, ...):
        self.matrix_path = matrix_path
        self.agent_profile_path = agent_profile_path

        # World 资源
        self.post_office = None      # 消息路由
        self.vector_db = None        # 邮件/笔记本搜索
        self.user_sessions = {}      # 用户会话跟踪

        # Agents
        self.agents = {}             # 名称 -> agent 实例

        # 初始化
        self._prepare_world_resource()
        self._prepare_agents()
        self.load_matrix()
```

**主要职责**:
- **World 资源准备**: 初始化 PostOffice 和 VectorDB
- **Agent 加载**: 从 YAML 配置文件加载所有 agents
- **状态持久化**: 保存和恢复 world 状态

### World 资源准备

**`_prepare_world_resource()`** (79-89行)

```python
def _prepare_world_resource(self):
    # 初始化用于消息路由的 PostOffice
    self.post_office = PostOffice()

    # 初始化用于语义搜索的 VectorDB
    self.vector_db = ChromaDB(
        persist_directory=os.path.join(self.matrix_path, "chroma_db")
    )

    # 注册到 agents
    for agent in self.agents.values():
        agent.post_office = self.post_office
        agent.vector_db = self.vector_db
```

**初始化的资源**:
1. **PostOffice**: 用于 agent 间通信的异步消息队列
2. **VectorDB (ChromaDB)**: 邮件和笔记本的语义搜索
3. **用户会话**: 跨 agents 跟踪用户对话

### Agent 加载

**位置**: `src/agentmatrix/core/loader.py`

`AgentLoader` 类从 YAML 配置文件发现并实例化 agents。

```python
class AgentLoader:
    def __init__(self, profile_path, llm_config_path=None):
        self.profile_path = profile_path
        # 加载 LLM 配置
        with open(llm_config_path or f"{profile_path}/llm_config.json") as f:
            self.llm_config = json.load(f)

    def load_from_file(self, file_path) -> BaseAgent:
        """从 YAML 文件加载并实例化一个 Agent"""
        # 1. 解析 YAML 配置文件
        with open(file_path, 'r', encoding='utf-8') as f:
            profile = yaml.safe_load(f)

        # 2. 解析基础类信息（必须字段）
        module_name = profile["module"]
        class_name = profile["class_name"]

        # 3. 解析可选配置
        attribute_inits = profile.pop("attribute_initializations", {})
        class_attrs = profile.pop("class_attributes", {})

        # 4. 清理配置中的特殊字段
        del profile["module"]
        del profile["class_name"]

        # 5. 导入 Agent 类
        module = importlib.import_module(module_name)
        agent_class = getattr(module, class_name)

        # 6. 设置类属性（如果有）
        if class_attrs:
            for attr_name, attr_value in class_attrs.items():
                setattr(agent_class, attr_name, attr_value)

        # 7. 实例化 Agent
        agent_instance = agent_class(profile.copy())

        # 8. 注入实例属性
        if attribute_inits:
            for attr_name, attr_value in attribute_inits.items():
                setattr(agent_instance, attr_name, attr_value)

        # 9. 设置 Brain（LLM）
        backend_model = agent_instance.backend_model
        agent_instance.brain = self._create_llm_client(backend_model)

        # 10. 设置 Cerebellum（SLM）
        cerebellum_config = profile.get("cerebellum", {})
        slm_model = cerebellum_config.get("backend_model", "default_slm")
        slm_client = self._create_llm_client(slm_model)
        agent_instance.cerebellum = Cerebellum(slm_client, agent_instance.name)

        # 11. 设置 Vision Brain（可选）
        vision_config = profile.get("vision_brain")
        if vision_config:
            vision_model = vision_config.get("backend_model", "default_vision")
            agent_instance.vision_brain = self._create_llm_client(vision_model)

        return agent_instance
```

**`load_all()`** (179-187行):

```python
def load_all(self) -> Dict[str, BaseAgent]:
    """从配置目录加载所有 agents"""
    agents = {}
    for filename in os.listdir(self.profile_path):
        if filename.endswith(".yml"):
            file_path = os.path.join(self.profile_path, filename)
            agent = self.load_from_file(file_path)
            agents[agent.name] = agent
    return agents
```

### Agent 配置文件格式

**示例**: `MyWorld/agents/researcher.yml`

```yaml
# ========== 必须字段 ==========
name: Researcher
description: 研究和信息收集专家
module: agentmatrix.agents.base
class_name: BaseAgent

# ========== 核心配置 ==========

# Skills 配置（🆕 新架构）
skills:
  - file              # 文件操作技能
  - web_search        # 网络搜索技能
  # 可用技能：file, web_search, browser, notebook, crawler

# Persona 配置（🆕 支持多 persona）
persona:
  base: |
    你是一个资深研究员，擅长进行深入的研究工作，并撰写研究报告
  planner: |
    你是研究规划专家，擅长制定研究计划
  analyst: |
    你是数据分析专家，擅长从研究结果中提取关键信息

# ========== 模型配置 ==========

# 后端模型（推理 LLM）
backend_model: default_llm

# 小脑模型配置（参数协商 SLM）
cerebellum:
  backend_model: default_slm  # 可选，默认使用系统 default_slm

# 视觉模型配置（可选，用于图片理解）
vision_brain:
  backend_model: default_vision  # 可选，默认使用系统 default_vision（如果存在）

# ========== 可选配置 ==========

# 其他 Prompts（用于特定场景）
prompts:
  task_breakdown: "请将任务分解为3-5个子任务"
  summary_format: "请用简洁的语言总结"

# 给调用者的指令
instruction_to_caller: |
  告诉我想研究什么问题

# 实例属性初始化（可选）
attribute_initializations:
  browser_adapter: null
  max_retries: 3

# 类属性设置（可选）
class_attributes:
  _custom_log_level: 10  # logging.DEBUG

# 日志配置（可选）
logging:
  components:
    brain:
      enabled: true
      level: DEBUG
    cerebellum:
      enabled: true
      level: INFO
```

**配置字段说明**：

#### 必须字段
| 字段 | 说明 | 示例 |
|------|------|------|
| `name` | Agent 唯一标识符 | `Researcher` |
| `description` | Agent 的用途描述 | `研究和信息收集专家` |
| `module` | Agent 类所在的 Python 模块路径 | `agentmatrix.agents.base` |
| `class_name` | Agent 类名称 | `BaseAgent` |

#### 核心配置（推荐）
| 字段 | 说明 | 默认值 |
|------|------|--------|
| `skills` | 要加载的技能列表（新架构） | `[]` |
| `persona` | Agent 人格配置（支持多个） | `{"base": ""}` |
| `backend_model` | 用于推理的 LLM 模型 | `default_llm` |

#### 模型配置（可选）
| 字段 | 说明 | 默认值 |
|------|------|--------|
| `cerebellum` | 小脑模型配置块 | 使用系统 default_slm |
| `cerebellum.backend_model` | 小脑使用的模型 | `default_slm` |
| `vision_brain` | 视觉模型配置块 | 使用系统 default_vision（如果存在） |
| `vision_brain.backend_model` | 视觉模型名称 | `default_vision` |

#### 高级配置（可选）
| 字段 | 说明 | 默认值 |
|------|------|--------|
| `prompts` | 其他 Prompt 模板（用于特定场景） | `{}` |
| `instruction_to_caller` | 给调用者的指令 | `""` |
| `attribute_initializations` | 实例属性初始化字典 | `{}` |
| `class_attributes` | 类属性设置字典 | `{}` |
| `logging` | 日志配置（组件级别） | `{}` |

**重要变更说明**：
- ❌ **已废弃**：`mixins`（旧架构，请改用 `skills`）
- ❌ **已废弃**：`system_prompt`（请改用 `persona.base`）
- ❌ **已废弃**：`cerebellum_model`（请改用 `cerebellum.backend_model`）
- ✅ **新字段**：`persona`（支持多 persona 配置）
- ✅ **新字段**：`skills`（简化技能加载，支持自动发现）
- ✅ **新字段**：`vision_brain`（支持视觉模型）
- ✅ **新字段**：`prompts`（支持多个场景的 prompt 模板）

### PostOffice

**位置**: `src/agentmatrix/agents/post_office.py`

`PostOffice` 类提供异步消息路由和服务发现。

```python
class PostOffice:
    def __init__(self):
        # 服务注册(agent 目录)
        self.yellow_page = {}      # 名称 -> agent 实例

        # 消息队列
        self.inboxes = {}           # 名称 -> asyncio.Queue

        # 搜索和会话
        self.vector_db = None       # 用于邮件搜索
        self.user_sessions = {}     # 用户会话跟踪

    def register_agent(self, agent: BaseAgent):
        """注册 agent 以进行通信"""
        self.yellow_page[agent.name] = agent
        self.inboxes[agent.name] = asyncio.Queue()

    async def send_email(self, email: Email):
        """将邮件路由到接收者的收件箱"""
        recipient_inbox = self.inboxes.get(email.recipient)
        if recipient_inbox:
            await recipient_inbox.put(email)

    async def get_email(self, agent_name: str, timeout: float = None):
        """从 agent 的收件箱检索下一封邮件"""
        inbox = self.inboxes.get(agent_name)
        return await asyncio.wait_for(inbox.get(), timeout)

    def find_agent(self, name: str) -> Optional[BaseAgent]:
        """通过黄页进行服务发现"""
        return self.yellow_page.get(name)
```

**关键特性**:
- **服务发现**: 黄页将 agent 名称映射到实例
- **异步消息路由**: 非阻塞邮件传递
- **向量搜索**: 通过语义相似性查找相关邮件
- **用户会话管理**: 跨 agents 跟踪用户对话

### 状态持久化

**`save_matrix()`** (runtime.py 144-156行):

```python
def save_matrix(self):
    """将 world 状态持久化到磁盘"""
    state = {
        "user_sessions": self.user_sessions,
        "agent_states": {}
    }

    # 保存每个 agent 的会话状态
    for name, agent in self.agents.items():
        state["agent_states"][name] = {
            "sessions": agent.sessions,
            "reply_mapping": agent.reply_mapping
        }

    # 写入文件
    state_file = os.path.join(self.matrix_path, "matrix_state.json")
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
```

**`load_matrix()`** (runtime.py 158-171行):

```python
def load_matrix(self):
    """从磁盘恢复 world 状态"""
    state_file = os.path.join(self.matrix_path, "matrix_state.json")
    if not os.path.exists(state_file):
        return

    with open(state_file, 'r') as f:
        state = json.load(f)

    # 恢复用户会话
    self.user_sessions = state.get("user_sessions", {})

    # 恢复 agent 会话
    for name, agent_state in state.get("agent_states", {}).items():
        if name in self.agents:
            agent = self.agents[name]
            agent.sessions = agent_state.get("sessions", {})
            agent.reply_mapping = agent_state.get("reply_mapping", {})
```

## 初始化流程

### 启动序列

```
1. 创建 AgentMatrix 实例
   │
2. 准备 World 资源
   ├─ 初始化 PostOffice
   ├─ 初始化 VectorDB (ChromaDB)
   └─ 创建用户会话跟踪器
   │
3. 加载 Agents
   ├─ 扫描 profiles/ 目录查找 *.yml 文件
   ├─ 对于每个配置文件:
   │  ├─ 解析 YAML
   │  ├─ 导入基类 (BaseAgent)
   │  ├─ 加载 skill mixins
   │  ├─ 创建动态类(多重继承)
   │  └─ 实例化 agent
   └─ 在 PostOffice 中注册 agents
   │
4. 加载 World 状态
   ├─ 读取 matrix_state.json
   ├─ 恢复用户会话
   └─ 恢复 agent 会话和回复映射
   │
5. 启动 Agent 循环
   └─ 每个 agent 开始监听邮件
```

### 代码示例

```python
# 初始化 AgentMatrix
matrix = AgentMatrix(
    agent_profile_path="src/agentmatrix/profiles",
    matrix_path="examples/MyWorld",
    default_backend=llm_client,
    default_cerebellum=cerebellum_client
)

# 所有 agents 已加载并就绪
print(f"已加载 {len(matrix.agents)} 个 agents:")
for name, agent in matrix.agents.items():
    print(f"  - {name}: {agent.description}")

# Agents 现在正在监听邮件
# 发送任务给 Planner agent
email = Email(
    id=str(uuid.uuid4()),
    sender="user@example.com",
    recipient="Planner",
    subject="规划网站",
    body="创建一个投资组合网站的计划",
    user_session_id="session_123"
)

await matrix.post_office.send_email(email)
```

## 运行时执行

### 任务处理生命周期

```
1. 用户发送邮件给 agent
   │
2. PostOffice 将邮件路由到 agent 的收件箱
   │
3. Agent 的 process_email() 方法:
   ├─ 检查 in_reply_to 以获取线程上下文
   ├─ 通过 SessionManager 恢复或创建 session
   ├─ 委托给 MicroAgent
   │  └─ 思考-协商-行动循环:
   │     ├─ 思考: LLM 生成推理
   │     ├─ 从输出中检测动作
   │     ├─ 协商参数(通过 Cerebellum)
   │     ├─ 执行动作
   │     └─ 重复直到 all_finished 或 max_steps
   ├─ MicroAgent 返回结果
   └─ 发送回复邮件
   │
4. PostOffice 将回复传递给用户
   │
5. AgentMatrix 保存状态
```

### 并发 Agent 执行

每个 agent 运行自己的异步循环，独立处理邮件:

```python
# 每个 agent 的消息循环
async def message_loop(agent: BaseAgent):
    while True:
        # 获取下一封邮件(阻塞)
        email = await agent.post_office.get_email(agent.name)

        # 处理邮件
        await agent.process_email(email)

# 并发启动所有 agents
async def run_matrix(matrix: AgentMatrix):
    tasks = []
    for agent in matrix.agents.values():
        task = asyncio.create_task(message_loop(agent))
        tasks.append(task)

    # 运行所有 agents
    await asyncio.gather(*tasks)
```

### Agent 间协作

Agents 可以通过邮件相互委托任务:

```python
# Researcher agent 的动作
@register_action(description="将规划委托给 Planner agent")
async def delegate_planning(self, research_results: str) -> str:
    # 组成委托邮件
    email = Email(
        id=str(uuid.uuid4()),
        sender=self.name,
        recipient="Planner",
        subject="根据研究创建计划",
        body=f"基于研究: {research_results}\n创建项目计划。",
        user_session_id=self.current_session_id
    )

    # 发送给 Planner
    await self.post_office.send_email(email)

    # 等待 Planner 的响应
    reply = await self.post_office.get_email(self.name, timeout=600)
    return reply.body
```

## 组件总结

| 组件 | 文件 | 职责 |
|------|------|------|
| AgentMatrix | core/runtime.py | World 管理和编排 |
| AgentLoader | core/loader.py | 从 YAML 配置文件初始化 agents |
| PostOffice | agents/post_office.py | 消息路由和服务发现 |
| VectorDB | db/vector_db.py | 邮件/笔记本的语义搜索 |
| Session | core/session.py | 对话状态管理 |
| Email | core/message.py | Agent 间通信数据结构 |

### 关键设计决策

1. **基于 YAML 的配置**: Agent 配置声明式且易于修改
2. **动态类组合**: Mixins 实现灵活的技能组合
3. **异步优先架构**: 非阻塞消息传递和执行
4. **状态持久化**: 对话在重启后保持
5. **服务发现**: 黄页实现 agents 之间的松耦合

## 开发指南

### 添加新 Agent

1. **创建配置 YAML**: 添加到 `profiles/` 目录
2. **定义系统提示词**: 指定 agent 的人格和行为
3. **选择技能**: 添加所需的 mixins
4. **配置后端**: 选择 LLM/SLM 模型
5. **重启 Matrix**: Agent 在下次启动时自动加载

### 添加新技能

1. **创建 Mixin 类**: 在 `src/agentmatrix/skills/` 中
2. **注册动作**: 使用 `@register_action` 装饰器
3. **实现方法**: 添加动作逻辑
4. **更新配置**: 添加到 agent 的 `mixins` 列表
5. **测试**: 使用 MicroAgent 进行单任务执行

### 监控和调试

- **检查 Agent 状态**: `matrix.agents.keys()`
- **查看用户会话**: `matrix.user_sessions`
- **检查 Agent 会话**: `agent.sessions`
- **搜索邮件历史**: `matrix.vector_db.search()`
- **保存状态**: `matrix.save_matrix()`

## 示例 World 设置

```
examples/MyWorld/
├── agents/                  # Agent 配置文件
│   ├── User.yml
│   └── researcher.yml
├── workspace/               # 工作区数据
│   ├── .matrix/            # 内部状态
│   ├── sessions/           # 会话历史
│   └── chroma_db/          # 向量数据库
└── matrix_world.yml        # World 配置
```

初始化:

```python
matrix = AgentMatrix(
    agent_profile_path="examples/MyWorld/agents",
    matrix_path="examples/MyWorld",
    default_backend=your_llm_client,
    default_cerebellum=your_slm_client
)

# 运行 matrix
await matrix.run()
```
