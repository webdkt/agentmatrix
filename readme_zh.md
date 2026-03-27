# AgentMatrix

[English](readme.md) | 中文

**让 LLM 专注于思考，而不是格式。**

我们一直在思考一个问题：为什么让一个强大的语言模型做点事情，非要先教会它写 JSON？

你让 GPT 帮你做研究，它得先理解你的意图，然后还得小心翼翼地输出 `{"action": "search", "parameters": {"query": "..."}}`。推理能力和格式能力，两种完全不同的能力被硬塞进了同一个输出通道。这就像让一个人一边解数学题一边同时写书法——两个任务互相干扰，哪个都做不好。

AgentMatrix 的核心理念就是把这两件事分开。让大模型专心思考，让小模型处理格式。就这么简单。

---

## 它是什么

AgentMatrix 是一个多 Agent 框架 + 原生桌面应用。

它不只是又一个 "AI Agent SDK"。它重新定义了 Agent 之间、Agent 与人之间的协作方式。

### 三个核心创新

**1. 大脑 + 小脑：让思考和执行分离**

```
大脑 (LLM)          →  用自然语言思考，决定"做什么"
小脑 (SLM)          →  把意图翻译成结构化参数
身体 (Python 代码)   →  实际执行
```

大脑不需要知道什么是 JSON。它只管思考。小脑负责把"我觉得应该搜索一下这个话题"翻译成 `web_search(query="...")`。如果意图不明确，小脑会反问大脑。两个模型各司其职。

**2. 邮件系统：Agent 之间的沟通方式**

Agent 之间不直接调用 API。它们发邮件。

```python
email = Email(
    sender="研究员",
    recipient="写手",
    subject="研究报告请求",
    body="请根据我整理的要点撰写摘要...",
)
await post_office.send_email(email)
```

为什么是邮件？因为自然语言比 API 更好调试。你能看懂 Agent 之间在说什么，能追踪对话线程，能理解 Agent 为什么要这么做。它不只返回一个状态码——它解释自己的推理过程。

**3. MicroAgent：自然语言函数**

传统框架里，你写 Python 函数调用另一个 Python 函数。在 AgentMatrix 里，你写"自然语言函数"调用另一个"自然语言函数"：

```python
async def 研究话题(话题: str) -> dict:
    """这是一个 LLM 函数，不是普通 Python 函数"""
    return await micro_agent.execute(
        persona="你是一个研究员",
        task=f"深入研究 {话题}",
        result_params={
            "expected_schema": {
                "summary": "一句话摘要",
                "findings": ["关键发现"],
            }
        }
    )

# 在另一个 Agent 里调用
@register_action(description="对比研究多个话题")
async def 对比研究(话题列表: list) -> dict:
    results = {}
    for 话题 in 话题列表:
        results[话题] = await 研究话题(话题)  # 递归嵌套，上下文完全隔离
    return results
```

每个 MicroAgent 有独立的执行上下文。你可以在里面嵌套调用更多 MicroAgent，每一层都不会污染其他层的上下文。复杂任务被自然地拆解成可组合的"语言函数"。

---

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                   桌面应用 (Tauri + Vue 3)                   │
│          MERIDIAN 设计语言 · Matrix 风格初始化向导            │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket + REST API
┌──────────────────────────┴──────────────────────────────────┐
│                    FastAPI Server                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                   AgentMatrix 运行时                         │
│                                                             │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │  PostOffice  │  │   ConfigService │  │  TaskScheduler  │  │
│  │  (消息路由)   │  │   (配置管理)     │  │  (任务调度)      │  │
│  └──────┬───────┘  └────────────────┘  └─────────────────┘  │
│         │                                                   │
│  ┌──────┴───────────────────────────────────────────────┐   │
│  │                     Agents                            │   │
│  │  ┌──────────────┐  ┌─────────────────────────────┐   │   │
│  │  │  BaseAgent   │  │  MicroAgent (可递归嵌套)      │   │   │
│  │  │  持久会话层   │  │  临时执行层                   │   │   │
│  │  │  管理对话状态 │  │  继承 BaseAgent 的技能        │   │   │
│  │  └──────────────┘  └─────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
│         │                                                   │
│  ┌──────┴──────────────────────────────────────────────┐    │
│  │               Docker 容器 (每个 Agent 独立隔离)       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心特性

### Think-With-Retry：自然语言格式提取

不要求 LLM 输出严格 JSON。用松散的格式标记（比如 `[章节名]`），如果输出不完整，系统用对话式反馈让 LLM 自我修正：

```python
result = await llm.think_with_retry(
    initial_messages="创建计划，包含：[方案]、[时间线]、[预算]",
    parser=section_parser,
    max_retries=3
)
# LLM 漏了 [时间线]？系统会说："你的回复很好，但缺少 [时间线] 部分，请补充。"
# 不是报错，是对话。
```

### 动态技能组合

技能是 Python Mixin，在运行时动态组合到 Agent 类上：

```yaml
# Agent 配置 (YAML)
name: Researcher
description: 深度研究专家
skills:
  - web_search
  - crawler
  - memory
  - deep_researcher
```

写一个新的 `skill.py`，放进 skills 目录，Agent 自动拥有新能力。不需要改任何已有代码。

### 容器级隔离

每个 Agent 运行在自己的 Docker 容器里。文件操作在容器内执行，Agent 之间互不干扰。容器按需唤醒和休眠。

### 内容优先的配置管理

配置以原始文本形式在 Agent 之间传递。因为 LLM 天然能读懂 YAML/JSON，配置错误可以用自然语言反馈给 Agent，让它自己修正。ConfigService 负责验证、备份和安全写入。

---

## 桌面应用

原生桌面应用，基于 Tauri (Rust) + Vue 3 构建。

### MERIDIAN 设计语言

我们把设计风格称为 **MERIDIAN**——"情报档案室"美学。

- 编辑优先，零装饰。层级用边框和留白区分，不用阴影和渐变。
- 衬线体承载思考，无衬线体驱动行动。
- 朱红色（#C23B22）只在关键位置出现：选中边框、焦点状态、思考进度条。
- 中英文同等对待，各有专用字体栈。

### Matrix 风格初始化向导

首次启动时，你会看到一个全屏的 Matrix 主题引导：打字机效果、字符雨动画、逐步完成配置——用户名、工作目录、大脑模型、小脑模型。不是冰冷的 CLI 提示，是仪式感。

### 实时状态同步

通过 WebSocket 实时推送 Agent 状态。每个 Agent 的 `update_status()` 都会触发一次推送，不需要轮询。你能实时看到 Agent 在思考、在工作、在等待你的输入。

---

## 快速开始

### 桌面应用（推荐）

```bash
cd agentmatrix-desktop
npm install
npm run tauri:dev
```

首次启动会进入初始化向导，按提示完成配置即可。

### 作为 Python 库

```bash
pip install matrix-for-agents
```

```python
from agentmatrix import AgentMatrix

matrix = AgentMatrix(
    agent_profile_path="path/to/profiles",
    matrix_path="path/to/matrix"
)

await matrix.run()
```

---

## 内置技能

| 技能 | 说明 |
|------|------|
| `base` | 基础能力：获取时间、询问用户、列出额外技能 |
| `file` | 文件操作：读写、搜索、目录管理、bash 命令（容器内执行） |
| `browser` | 浏览器自动化 |
| `web_search` | 网络搜索 |
| `email` | 邮件收发（支持附件） |
| `memory` | 知识/记忆管理 |
| `deep_researcher` | 深度研究（多 Agent 协作） |
| `system_admin` | 系统管理 |
| `agent_admin` | Agent 生命周期管理 |
| `scheduler` | 任务调度 |

你也可以写自己的技能。一个 `skill.py` 文件就够了。

---

## 项目结构

```
agentmatrix/
├── src/agentmatrix/          # 核心框架
│   ├── agents/               # BaseAgent + MicroAgent
│   ├── core/                 # 运行时、小脑、动作系统
│   ├── skills/               # 内置技能
│   ├── services/             # ConfigService 等
│   └── backends/             # LLM 后端适配
├── agentmatrix-desktop/      # 原生桌面应用
│   ├── src/                  # Vue 3 前端
│   └── src-tauri/            # Tauri (Rust) 后端
├── server.py                 # FastAPI 服务
├── examples/                 # 示例
└── docs/                     # 文档
```

---

## 这不是什么

- 这不是一个 wrapper。我们不封装 LLM API，我们重新定义了 Agent 的思考方式。
- 这不是一个 no-code 工具。你写 Python、写 YAML、写自然语言。
- 这不是一个 toy project。Docker 隔离、会话管理、持久化、实时同步——都是认真实现的。

---

## 文档

- [Agent 与 MicroAgent 设计](docs/architecture/agent-and-micro-agent-design-cn.md)
- [Matrix World 架构](docs/matrix-world-cn.md)
- [Think-With-Retry 模式](docs/architecture/think-with-retry-pattern-cn.md)
- [配置服务与管理技能](docs/core/config-service-and-admin-skill.md)

---

## 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE)

---

## 路线图

- [ ] 增强多 Agent 协作模式
- [ ] 更多内置技能
- [ ] 更多 LLM 后端支持
- [ ] 增强的监控与调试工具
- [ ] 插件市场

---

**版本**: v0.3.0 | **状态**: Alpha  
**仓库**: https://github.com/webdkt/agentmatrix
