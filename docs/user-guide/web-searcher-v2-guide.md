# WebSearcherV2 - 基于 Micro Agent 的网络搜索技能

## 概述

WebSearcherV2 是基于 Micro Agent 模式的网络搜索技能，与现有的 web_searcher 相比，具有以下特点：

- **单一接口**：只提供一个 `web_search(query)` action
- **自主规划**：Micro Agent 自己决定如何使用浏览器和文件工具，无需详细指令
- **长时间运行**：每轮 30 分钟，支持无限轮次，context 不会爆炸
- **状态管理**：通过纯文本 dashboard 保持长期记忆

## 核心设计

### 架构

```
WebSearcherV2Mixin (Skill)
    ├── 继承 BrowserUseSkillMixin     # 提供 browser_navigate
    ├── 继承 FileOperationSkillMixin   # 提供 file_operation
    └── web_search()                   # 唯一对外 action
        └── _do_search_task()          # 永久搜索循环
            └── 每轮调用 _run_micro_agent()  # BaseAgent 提供的方法
                ├── 工具 1: browser_navigate
                ├── 工具 2: file_operation
                ├── 工具 3: update_dashboard
                └── 工具 4: all_finished
```

### Micro Agent 的工具集

Micro Agent 可以使用以下 4 个工具：

1. **browser_navigate** (来自 BrowserUseSkill)
   - 访问网页
   - 搜索引擎搜索
   - 提取页面内容

2. **file_operation** (来自 FileOperationSkill)
   - 保存搜索结果到文件
   - 读取之前保存的文件

3. **update_dashboard** (WebSearcherV2 提供)
   - 更新搜索状态（纯文本）
   - 参数：`content: str` （任意格式的纯文本）

4. **all_finished** (BaseAgent 提供)
   - Micro Agent 主动完成任务
   - 可以返回结构化结果

### 永久循环机制

参考 deep_researcher 的 `_do_research_task` 模式：

```python
while True:
    # 每轮 30 分钟
    result = await self._run_micro_agent(
        persona="网络搜索专家",
        task=task_prompt,  # 包含全局目标 + dashboard
        available_actions=["browser_navigate", "file_operation", "update_dashboard", "all_finished"],
        max_time=30.0
    )

    # 检查退出条件
    if should_stop(result):
        break
```

**优势**：
- ✅ Context 不会爆炸（每轮都是新会话）
- ✅ 长期记忆通过 dashboard 保存
- ✅ 支持长时间运行（多轮）
- ✅ Micro Agent 可以主动完成（all_finished）

### Dashboard 管理

Dashboard 是**纯文本**，保存在 session context 的 `search_dashboard` 字段。

**初始格式**：
```
【搜索状态】
初始化完成，准备开始搜索。

【当前目标】
（待更新）

【发现】
（暂无）

【已访问网页】
（暂无）
```

**更新方式**：
- Micro Agent 通过 `update_dashboard(content="...")` 更新
- 完全自由格式，可以是任何文本结构
- 支持多轮更新（每轮都会加载上一轮的 dashboard）

## 使用方法

### 基本用法

```python
from agentmatrix.agents.base import BaseAgent
from agentmatrix.skills.web_searcher_v2 import WebSearcherV2Mixin

class MyAgent(BaseAgent, WebSearcherV2Mixin):
    pass

# 使用
agent = MyAgent(profile)
result = await agent.web_search(query="What is Python asyncio?")
print(result)  # 最终的 dashboard
```

### 测试

```bash
cd tests
python test_web_searcher_v2.py
```

测试包含两个案例：
1. **简单搜索**：快速验证基本功能
2. **多轮搜索**：验证永久循环和 dashboard 管理

**注意**：每轮最多 30 分钟，Micro Agent 可能会提前完成。

## 配置要求

### LLM 配置

WebSearcherV2 通过 BrowserUseSkill 自动加载 LLM 配置：

- **优先配置**: `browser-use-llm`（推荐）
- **回退配置**: `deepseek_chat`（如果没有 `browser-use-llm`）

在 `llm_config.json` 中配置：

```json
{
    "browser-use-llm": {
        "url": "https://api.deepseek.com/chat/completions",
        "API_KEY": "DEEPSEEK_API_KEY",
        "model_name": "deepseek-chat"
    }
}
```

### 依赖安装

```bash
pip install browser-use langchain-openai
```

## 工作流程示例

### 场景：搜索 "Python asyncio best practices"

**第 1 轮**：
1. Micro Agent 收到任务：搜索 "Python asyncio best practices"
2. 决定使用 `browser_navigate` 访问 Google
3. 搜索并找到几个相关网页
4. 提取内容，发现信息不够全面
5. 调用 `update_dashboard` 更新状态
6. 达到时间限制（30 分钟），返回 "未完成"

**第 2 轮**：
1. Micro Agent 收到任务（包含上一轮的 dashboard）
2. 看到 dashboard 显示已找到 3 个网页，但需要更深入的信息
3. 决定访问其中最有价值的网页
4. 提取详细内容
5. 调用 `file_operation` 保存重要信息
6. 调用 `update_dashboard` 更新发现
7. 提前完成（调用 `all_finished`）

**最终结果**：
```
【搜索状态】
已完成（2 轮）

【全局目标】
搜索 Python asyncio best practices

【当前目标】
✓ 已完成

【发现】
- asyncio 是 Python 3.4+ 的内置库
- 关键优势：非阻塞 IO、高并发、资源效率高
- 最佳实践：避免阻塞操作、使用 asyncio.gather()、正确处理异常
- 常见陷阱：在 async 函数中使用同步代码、忘记 await

【已访问网页】
1. https://docs.python.org/3/library/asyncio.html
2. https://realpython.com/async-io-python/
3. https://medium.com/python-features/introduction-to-asyncio-in-python-455e4e5e23ed
```

## 与 web_searcher 的对比

| 特性 | web_searcher (v1) | web_searcher_v2 |
|------|------------------|-----------------|
| 接口数量 | 多个 action | 单一 action (web_search) |
| 指令方式 | 详细步骤描述 | 自主规划 |
| 上下文管理 | Session context | Dashboard (纯文本) |
| 长时间运行 | 受限于 context 长度 | 多轮短会话，无限制 |
| 灵活性 | 需要预定义流程 | Micro Agent 自主决策 |

## 实现细节

### 退出条件

搜索循环会在以下情况退出：

1. **Micro Agent 主动完成**：调用 `all_finished`（返回 dict）
2. **正常完成**：返回字符串且不包含 "未完成"
3. **Dashboard 显示完成**：包含"搜索完成"、"任务完成"等关键词
4. **达到最大轮次**：20 轮（10 小时）

### 时间跟踪

- **每轮时间**：30 分钟（硬限制）
- **总时间跟踪**：`total_time` 变量累计
- **时间信息**：每轮都会告诉 Micro Agent 已用时间

### 错误处理

- 如果某轮执行失败，记录错误到 dashboard
- 继续下一轮（不会因为单轮失败而中断）
- 只有在连续多次失败或达到最大轮次时才退出

### 文件管理

#### 工作目录结构

WebSearcherV2 为每次 `web_search` 调用创建专属工作目录：

```
{workspace_root}/
└── {user_session_id}/
    └── history/
        └── {agent_name}/
            └── {session_id}/           # ← session_folder
                ├── history.json
                ├── context.json
                └── web_search/         # ← WebSearcherV2 工作目录
                    ├── 20250210_143022/
                    │   ├── notes.md
                    │   ├── findings.md
                    │   └── ...
                    ├── 20250210_150830/
                    │   └── ...
                    └── ...
```

**关键特性**：
- 每次搜索都有独立的时间戳目录（`YYYYMMDD_HHMMSS/`）
- 完全隔离，不会相互干扰
- Session 删除时自动清理

#### Dashboard 中的工作目录

Dashboard 初始化时会包含工作目录路径：

```
【搜索状态】
初始化完成，准备开始搜索。

【工作目录】
/Users/frwang/workspace/user_12345/history/WebSearcherV2/a1b2c3d4/web_search/20250210_143022/

【当前目标】
（待更新）
```

#### Micro Agent 如何使用工作目录

Micro Agent 可以通过 `file_operation` action 在专属工作目录中创建文件。

**方式 1：使用绝对路径**
```
"在 /Users/frwang/workspace/.../web_search/20250210_143022/ 目录下创建 notes.md 文件，
内容是我刚才发现的 5 个关键点..."
```

**方式 2：使用相对路径（推荐）**
```
"在 web_search/20250210_143022 目录下创建 notes.md 文件"
```

相对路径会基于 `session_folder` 解析，例如：
- `working_dir="web_search/20250210_143022"` → `{session_folder}/web_search/20250210_143022/`
- `working_dir="notes"` → `{session_folder}/notes/`

**方式 3：直接传递 working_dir 参数**
```python
await self.file_operation(
    operation_description="创建 notes.md 文件",
    working_dir="web_search/20250210_143022"  # 相对于 session_folder
)
```

**推荐方式**：
在任务提示中，WebSearcherV2 会告知 Micro Agent 使用专属目录，因此 Micro Agent 可以使用相对路径（更简洁），例如：
```
"切换到 web_search/20250210_143022 目录，然后创建 notes.md 文件"
```

#### 优势

1. **完全隔离**：每次搜索都有独立的文件存储空间
2. **易于调试**：可以直接查看工作目录下的文件
3. **自动清理**：Session 删除时，工作目录也会被清理
4. **灵活扩展**：支持任意文件操作（笔记、草稿、下载等）

## 扩展

### 添加新的工具

如果需要给 Micro Agent 添加更多工具，只需修改 `_do_search_task` 中的 `available_actions` 列表：

```python
available_actions=[
    "browser_navigate",
    "file_operation",
    "update_dashboard",
    "all_finished",
    "your_new_action"  # 新增
]
```

确保新 action 已经通过 `@register_action` 注册。

### 自定义时间限制

修改 `web_search()` 方法中的 `max_time` 参数：

```python
result = await self._run_micro_agent(
    ...,
    max_time=60.0  # 改为 60 分钟/轮
)
```

### 自定义最大轮次

修改 `_should_stop()` 方法中的 `MAX_ROUNDS`：

```python
MAX_ROUNDS = 50  # 改为 50 轮
```

## 常见问题

### Q: Micro Agent 一直在搜索，不停止怎么办？

A: 检查 dashboard 是否显示任务已完成。如果没有，可能需要：
1. 改进 prompt，明确告诉 Micro Agent 何时应该完成
2. 设置合理的 `MAX_ROUNDS`
3. 在 dashboard 中添加进度提示

### Q: 如何查看 Micro Agent 的搜索过程？

A: 查看日志文件或实时控制台输出。每轮的开始和结束都有明确的日志标记。

### Q: Dashboard 内容太长怎么办？

A: Micro Agent 可以自主决定如何组织 dashboard。可以在 prompt 中建议它保持简洁，或者实现一个 `summarize_dashboard` action。

## 参考文档

- [Agent-Micro Agent 设计](./agent-and-micro-agent-design-cn.md)
- [BrowserUseSkill 使用指南](../src/agentmatrix/skills/browser_use_skill_README.md)
- [Deep Researcher 实现](../src/agentmatrix/skills/deep_researcher.py)
