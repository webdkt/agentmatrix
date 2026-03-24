# Architecture

AgentMatrix 系统架构。

## 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                        AgentMatrix                          │
│                      (Runtime Orchestrator)                 │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│  BaseAgent  │   PostOffice│  MatrixPaths│   Config          │
│  (Async)    │   (Router)  │  (Paths)    │   (Settings)      │
└─────────────┴─────────────┴─────────────┴───────────────────┘
       │              │
       ▼              ▼
┌─────────────┐  ┌─────────────┐
│  MicroAgent │  │    Email    │
│  (Skills)   │  │   (Message) │
└─────────────┘  └─────────────┘
```

## Agent 类型

| 类型 | 职责 | 基类 |
|------|------|------|
| **BaseAgent** | 消息处理、会话管理、状态持久化 | `BaseAgent` |
| **MicroAgent** | 任务执行、Action 调用、Tool 使用 | `MicroAgent` |

### BaseAgent

核心能力：
- 异步消息循环 (`run()`)
- 双 Worker 模型：email worker + history worker
- 状态持久化到 JSON
- Session 管理
- Action 注册与执行

### MicroAgent

在 BaseAgent 基础上增加：
- Skill 系统（Mixin 模式）
- Think-With-Retry 执行模式
- Working Context（任务级变量空间）

## 消息系统

### Email

Agent 间通信的唯一方式。

```python
@dataclass
class Email:
    id: str
    sender: str
    recipient: str
    subject: str
    content: str
    attachments: List[str]
    timestamp: float
```

### PostOffice

消息路由中心。
- 维护所有 Agent 的收件箱映射
- 处理邮件分发
- 管理附件存储

## Skill 系统

基于 Mixin 模式的技能系统。

### Skill Mixin

```python
class MySkillMixin:
    _skill_description = "技能描述"
    _skill_dependencies = ["browser", "file"]  # 可选
    
    @register_action(
        short_desc="简短描述",
        description="详细描述",
        param_infos={"param": "参数说明"}
    )
    async def my_action(self, param: str) -> str:
        return result
```

### Skill 加载

1. 从 profile 读取 `skills` 列表
2. 解析依赖关系
3. 按顺序创建 Mixin 类
4. 动态创建 MicroAgent 子类

## 执行流程

### MicroAgent 执行循环

```
1. 接收 Email
2. 构建 System Prompt
3. LLM 生成 Action 调用
4. 解析 Action
5. 执行 Action
6. 返回结果给 LLM
7. 重复 3-6 直到完成
```

### Think-With-Retry 模式

LLM 输出 Python 函数调用格式，Parser 解析：
- 成功：直接执行
- 失败：返回错误给 LLM 重试

## Session 管理

每个对话有独立的 Session：
- Session ID: 用户会话标识
- Task ID: 单次任务标识  
- History: 消息历史（JSON 文件）
- Working Context: 任务级变量空间

## 目录结构

```
MatrixWorld/
├── .matrix/              # 系统数据（自动生成）
│   ├── configs/          # 配置文件
│   │   ├── agents/       # Agent profile YAML
│   │   ├── llm_config.json
│   │   ├── system_config.yml
│   │   ├── email_proxy_config.yml
│   │   └── backups/      # 自动备份
│   ├── database/         # SQLite 数据库
│   ├── logs/             # 日志文件
│   └── sessions/         # Agent 会话历史
└── workspace/            # 用户工作区
    ├── SKILLS/           # 自定义 Skills
    └── agent_files/      # Agent 工作文件
```

详见 [LLM-Managed Config](../../core/llm-managed-config.md) 了解配置管理设计。
