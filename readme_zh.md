# AgentMatrix

一个让 LLM 专注于**推理**而不是格式合规的智能多 Agent 框架。让Agent系统开发变得更自然。
实现：
- 自然语言函数：不再是简单的大模型API调用，而是自然语言函数：输入自然语言意图，得到意图执行结果，无需特别关注格式。不再需要花费力气去定义JSON格式，只需要关注意图本身。
- 自然的Sub Agent上下文管理：Agent的可以递归嵌套的调用skill(实质是sub agent，本项目中用micro agent这个名字），使得Agent可以处理更复杂的任务。这些micro agent工作任务的上下文自然自动的隔离，无需担心上下文污染。可以支持长周期的任务而无需进行复杂的手动上下文管理

[**English**](readme.md) | [**中文文档**](readme_zh.md)

## 🎯 AgentMatrix 是什么？

AgentMatrix 是一个多 Agent 框架，特点是：

- **Agent** 像拥有特定技能的数字员工
- Agent 通过**自然语言**（类似邮件）协作，而不是僵硬的 API 调用
- LLM 可以自然推理，不会把"脑力"浪费在 JSON 语法上

## 📦 项目组织

AgentMatrix 仓库包含三个主要部分：

### 1. 核心框架 (`src/agentmatrix/`)
AgentMatrix 的核心 - 用于构建智能 Agent 的 Python 库。
- **安装**: `pip install matrix-for-agents`
- **用途**: 作为库在你自己的项目中使用
- **包含**: Agent 运行时、技能系统、LLM 集成、消息路由

### 2. Web 应用 (`web/` + `server.py`)
AgentMatrix 的官方可视化管理界面。
- **启动**: `python server.py`
- **提供**: 可视化 Agent 交互界面、邮件式消息系统、会话管理
- **技术**: FastAPI 后端 + 现代化前端（Alpine.js + Tailwind CSS）
- **文档**: 参见 [web/README.md](web/README.md)

### 3. 示例 (`examples/`)
帮助您快速上手的示例配置和教程。
- **MyWorld**: 包含多个 Agent 的完整示例世界
- **文档**: 参见 [examples/README.md](examples/README.md)

**快速开始路径**:
- 🖥️ **想要可视化界面？** → 启动 Web 应用: `python server.py`
- 🐍 **想要编程使用？** → 作为库安装: `pip install matrix-for-agents`
- 📚 **想要通过示例学习？** → 探索 `examples/MyWorld`

## 🧠 为什么这很重要？

### 问题所在

大多数 Agent 框架强迫强大的 LLM 在僵硬的格式（如 JSON）里思考。这会导致：

- ❌ LLM 的注意力被语法占用，而不是推理
- ❌ 频繁的解析错误和脆弱的工作流
- ❌ 降低了 LLM 处理复杂任务的能力

**我们的理论**：要求 LLM 在做复杂推理的同时还要完美格式化 JSON，就像让人在杂耍的同时解微积分。你在增加不必要的认知负担。

### 我们的解决方案

AgentMatrix 使用 **大脑 + 小脑 + 身体**架构：

```
┌─────────────────────────────────────────────────┐
│  🧠 大脑 (LLM)                                  │
│  - 用自然语言推理                              │
│  - 决定"要做什么"                              │
│  - 无格式约束 → 更好的推理                     │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  🧠 小脑 (SLM)                                  │
│  - 将意图翻译成结构化数据                      │
│  - 处理参数协商                                │
│  - 澄清不清楚的请求                            │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  💪 身体 (Python 代码)                          │
│  - 执行函数                                    │
│  - 提供反馈                                    │
│  - 管理资源                                    │
└─────────────────────────────────────────────────┘
```

**核心洞察**：让 LLM 用自然语言思考，然后用更小的模型把那个意图翻译成机器可执行的命令。

## ✨ 核心特性

### 1. 双层 Agent 架构 (v0.1.5+)

**BaseAgent = 会话层**
- 管理多次用户交互的对话状态
- 可以同时维护多个独立的会话
- 拥有技能、动作和能力

**MicroAgent = 执行层**
- 单个任务的临时执行器
- 继承 BaseAgent 的所有能力
- 有独立的执行上下文
- 任务完成时终止

**🔥 核心特性：递归嵌套与 "LLM 函数"**

MicroAgent 调用可以**递归嵌套** - 这是一个革命性的特性：

```
MicroAgent 第 1 层
  ├─ 调用: web_search() 动作
  │   └─ 这个动作内部运行:
  │       └─ MicroAgent 第 2 层 (处理搜索结果)
  │           ├─ 调用: analyze_content() 动作
  │           │   └─ 这个动作内部运行:
  │           │       └─ MicroAgent 第 3 层 (提取关键信息)
  │           │           └─ 返回结构化数据给第 2 层
  │           └─ 返回分析结果给第 1 层
  └─ 返回最终结果给用户
```

**为什么这很重要**：

- ✅ **完美状态隔离**：每一层的执行历史都保持隔离。第 3 层的复杂推理不会污染第 2 层的上下文。第 2 层的中间步骤不会干扰第 1 层的会话。

- ✅ **MicroAgent 作为 "LLM 函数"**：把 `micro_agent.execute()` 看作**自然语言函数**：
  - **输入**：自然语言任务描述
  - **处理**：LLM 推理 + 多步执行
  - **输出**：自然语言结果 或 结构化数据（通过 `expected_schema`）

  ```python
  # 定义一个 "LLM 函数"
  async def research_topic(topic: str) -> Dict:
      """LLM 函数 - 不是普通的 Python 函数"""
      result = await micro_agent.execute(
          persona="你是一个研究员",
          task=f"研究关于 {topic} 的内容",
          result_params={
              "expected_schema": {
                  "summary": "摘要",
                  "key_findings": ["关键发现"],
                  "sources": ["来源"]
              }
          }
      )
      return result  # 返回结构化数据

  # 在另一个 MicroAgent 中调用这个 "LLM 函数"
  @register_action(description="研究多个主题")
  async def research_multiple_topics(topics: List[str]) -> Dict:
      results = {}
      for topic in topics:
          # 递归调用 MicroAgent
          results[topic] = await research_topic(topic)
      return results
  ```

- ✅ **简单构建复杂任务**：将复杂工作流分解为可组合的 LLM 函数调用，每个都有独立的上下文。

- ✅ **自然递归**：实现递归任务分解，每一层都是独立的 MicroAgent。

**对比**：
- **Python 函数**：确定性逻辑，固定流程
- **LLM 函数 (MicroAgent)**：概率性推理，灵活思考，自然语言接口

### 2. Think-With-Retry 模式

**挑战**：从 LLM 输出中提取结构化数据，同时不伤害推理质量

**我们的解决方案**：
- 使用**松散的格式要求**（例如用 `[章节名]` 而不是严格的 JSON）
- **智能重试**，提供具体、可操作的反馈
- **对话式流程** - 重试感觉像自然的澄清

**示例**：
```python
result = await llm_client.think_with_retry(
    initial_messages="创建一个项目计划，包含以下部分：[计划]、[时间线]、[预算]",
    parser=multi_section_parser,
    section_headers=['[计划]', '[时间线]', '[预算]'],
    max_retries=3
)
```

如果 LLM 忘记了 `[时间线]` 部分：
1. 解析器检测到缺失的部分
2. 系统自动请求：*"你的回答很有帮助，但缺少 [时间线] 部分。请添加它。"*
3. LLM 自然地纠正输出
4. 没有僵硬的约束，只是对话式反馈

### 3. 自然语言协调

Agent 通过**邮件**（自然语言消息）通信，而不是 API 调用：

```python
email = Email(
    sender="Researcher",
    recipient="Writer",
    subject="研究报告请求",
    body="请根据研究内容编写摘要...",
    user_session_id="session_123"
)
await post_office.send_email(email)
```

**好处**：
- 📝 更可解释和可调试
- 🔄 通过 `in_reply_to` 实现线程对话
- 🤝 Agent 解释它们在做什么，不只是返回代码

### 4. 动态技能组合

技能是**mixins**，通过 YAML 配置在运行时加载：

```yaml
# profiles/researcher.yml
name: Researcher
description: 研和信息收集专家

mixins:
  - agentmatrix.skills.web_searcher.WebSearcherMixin
  - agentmatrix.skills.crawler_helpers.CrawlerHelpersMixin
  - agentmatrix.skills.notebook.NotebookMixin
```

**好处**：
- 🔧 可组合的能力
- 📦 添加技能无需修改代码
- 🎯 技能可以在 Agent 之间共享

## 🚀 快速开始

### 安装

```bash
pip install matrix-for-agents
```

### 基本用法

```python
from agentmatrix import AgentMatrix

# 初始化框架
matrix = AgentMatrix(
    agent_profile_path="path/to/profiles",
    matrix_path="path/to/matrix"
)

# 启动运行时
await matrix.run()
```

### 向 Agent 发送任务

```python
# 给 Agent 发邮件
email = Email(
    sender="user@example.com",
    recipient="Researcher",
    subject="研究任务",
    body="帮我研究 AI 安全最佳实践",
    user_session_id="my-session"
)

await matrix.post_office.send_email(email)
```

## 📚 架构概览

### 核心组件

```
AgentMatrix 运行时
├── PostOffice        # 消息路由和服务发现
├── VectorDB          # 邮件/笔记本的语义搜索
├── AgentLoader       # 从 YAML 动态加载 Agent
└── Agents
    ├── BaseAgent     # 会话层 - 管理对话
    └── MicroAgent    # 执行层 - 运行任务
```

### 执行流程

```
用户发送邮件
    ↓
BaseAgent 收到邮件
    ↓
恢复/创建会话
    ↓
委托给 MicroAgent
    ↓
MicroAgent 执行:
  1. 思考：下一步该做什么？
  2. 从 LLM 输出检测动作
  3. 协商参数（通过 Cerebellum）
  4. 执行动作
  5. 重复直到 all_finished 或达到步数上限
    ↓
MicroAgent 返回结果
    ↓
BaseAgent 更新会话
    ↓
BaseAgent 发送回复邮件
```

## 📖 文档

全面的双语文档（英文 & 中文）：

### 核心架构
- **[Agent 和 Micro Agent 设计](docs/architecture/agent-and-micro-agent-design-cn.md)**
  - 双层架构设计哲学
  - 会话 vs. 执行分离
  - 技能系统和通信机制

- **[Matrix World 架构](docs/matrix-world-cn.md)**
  - 项目结构和组件
  - 初始化和运行时流程
  - 配置文件格式

### 核心模式
- **[Think-With-Retry 模式](docs/architecture/think-with-retry-pattern-cn.md)**
  - 自然语言 → 结构化数据
  - 解析器设计和实现
  - 自定义解析器创建指南

## 🛠️ 内置技能

- **Filesystem** - 文件操作和目录管理
- **WebSearcher** - 多搜索引擎的网络搜索
- **CrawlerHelpers** - 网页爬取和内容提取
- **Notebook** - 笔记本创建和管理
- **ProjectManagement** - 项目规划和任务分解

## 🧪 示例：创建自定义 Agent

```yaml
# profiles/my-agent.yml
name: MyAgent
description: 用于我的用例的自定义 Agent
module: agentmatrix.agents.base
class_name: BaseAgent

# 加载所需的技能
mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.web_searcher.WebSearcherMixin

# 定义 Agent 的人格
system_prompt: |
  你是一个专注于研究和分析的
  有用助手。

# 配置后端
backend_model: gpt-4
cerebellum_model: gpt-3.5-turbo
```

## 🤝 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解指南。

## 📝 许可证

Apache License 2.0 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

构建于：
- [FastAPI](https://fastapi.tiangolo.com/) - API 框架
- [DrissionPage](https://drissionpage.cn/) - 浏览器自动化
- [ChromaDB](https://www.trychroma.com/) - 向量数据库

## 📅 路线图

- [ ] 增强的多 Agent 协作模式
- [ ] 更多内置技能
- [ ] 性能优化
- [ ] 额外的后端集成
- [ ] 增强的监控和调试工具

---

**当前版本**: v0.1.5  
**状态**: Alpha（API 可能会演进）  
**文档**: [docs/](docs/) | [English Documentation](docs/)

详细信息请访问：https://github.com/webdkt/agentmatrix
