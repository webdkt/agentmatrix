# Browser Skill Fresh Start 实现

**修改时间**：2025-02-21
**修改文件**：`src/agentmatrix/skills/browser_skill.py`

## 问题描述

### 原始问题
在使用 browser skill 时，发现：
- browser-use Agent 会累积所有任务历史
- 每次返回的总结都包括之前的所有任务
- Prompt 会越来越长，影响性能和效果

### 根本原因
browser-use 的 `Agent.add_new_task()` 方法设计为**累积式追加**：
```python
# browser-use 源码
def add_new_task(self, new_task: str) -> None:
    self.task += '\n' + new_task  # 追加到 task 字符串
    self.state.agent_history_items.append(task_update_item)  # 追加到历史列表
```

这导致：
- Agent 的 `task` 字符串不断增长
- `agent_history_items` 列表不断累积
- 每次新的任务都会看到所有历史任务的上下文

## 解决方案

### 核心思路
**每次 `use_browser` 调用都创建全新的 Agent 实例**，同时保留浏览器状态。

### 实现细节

#### 修改前（会复用 Agent）
```python
async def _get_or_create_agent(self, task: str, headless: bool = False):
    # 首次创建
    if self._browser_use_agent is None:
        return await self._create_new_agent(task, headless)

    # 后续调用：复用 Agent，累积历史
    self._browser_use_agent.add_new_task(task)
    return self._browser_use_agent
```

#### 修改后（每次都创建新 Agent）
```python
async def _get_or_create_agent(self, task: str, headless: bool = False):
    # headless 模式改变或连接断开，清理 Browser
    if self._browser_use_agent is not None:
        if headless != self._browser_headless_mode:
            await self._cleanup_browser_and_agent()
        if not await self._is_browser_connected():
            await self._cleanup_browser_and_agent()

    # 🔥 Fresh Start：清除旧 Agent
    if self._browser_use_agent is not None:
        self._browser_use_agent = None

    # 创建新 Agent（Browser 会自动复用）
    return await self._create_new_agent(task, headless)
```

### 关键设计

#### 1. Agent vs Browser 生命周期分离
- **Agent**：短生命周期，每次调用都创建新的
- **Browser**：长生命周期，通过 `_get_browser()` 复用

#### 2. 保留的浏览器状态
✅ **Chrome profile**（cookies、登录状态）
✅ **已打开的标签页**
✅ **浏览器历史记录**
✅ **下载的文件**

#### 3. 清除的 Agent 状态
🗑️ **任务历史**（`agent_history_items`）
🗑️ **执行步骤计数**（`n_steps`）
🗑️ **失败计数**（`consecutive_failures`）
🗑️ **执行结果**（`last_result`）
🗑️ **计划状态**（`plan`）

## 性能影响

### 创建新 Agent 的开销
| 操作 | 开销 | 说明 |
|------|------|------|
| 创建 Python 对象 | ~10-50ms | Agent 对象初始化 |
| 浏览器启动 | ✅ 0ms | 不会重启，复用现有实例 |
| CDP 连接 | ✅ 0ms | 保持连接，不需要重新建立 |
| Chrome profile 加载 | ✅ 0ms | Profile 已在内存中 |
| LLM 客户端 | ✅ 复用 | `_browser_use_llm` 缓存 |

### 对比：复用 vs 重新创建
| 指标 | 复用 Agent（旧） | Fresh Start（新） |
|------|------------------|-------------------|
| 创建开销 | 0ms | ~10-50ms |
| 历史累积 | ✅ 不断增长 | ❌ 始终为空 |
| Prompt 长度 | 越来越长 | 固定长度 |
| 内存占用 | 持续增长 | 稳定 |
| 浏览器状态 | ✅ 保留 | ✅ 保留 |

## 测试验证

### 验证点
1. ✅ 每次 `use_browser` 调用都是独立的
2. ✅ 浏览器不会重启（标签页保持打开）
3. ✅ 每次调用都是 fresh start（无历史累积）
4. ✅ headless 模式切换正常工作
5. ✅ 浏览器连接断开时自动恢复

### 测试方法
```python
# 多次调用 browser
await agent.use_browser("打开 google.com")
await agent.use_browser("搜索 python")
await agent.use_browser("打开 bing.com")

# 验证：
# 1. 每次调用都是独立的任务
# 2. 浏览器标签页会累积（不会关闭之前的）
# 3. Agent 不知道之前做了什么
```

## 技术细节

### browser-use Agent 的状态结构
```python
class AgentState(BaseModel):
    agent_id: str
    n_steps: int
    consecutive_failures: int
    last_result: list[ActionResult] | None
    plan: list[PlanItem] | None
    last_model_output: AgentOutput | None
    # 🔥 关键：消息管理器状态（包含所有历史）
    message_manager_state: MessageManagerState
    # 文件系统状态
    file_system_state: FileSystemState | None
    # 循环检测器
    loop_detector: ActionLoopDetector
```

### MessageManager 的历史累积
```python
class MessageManagerState(BaseModel):
    task: str  # 🔥 会不断累积
    agent_history_items: list[HistoryItem]  # 🔥 会不断增长
    # ...
```

### 为什么没有"清除历史"的 API？
browser-use 的设计理念是：
- **Agent 是对话式的**：类似 ChatGPT，需要记住上下文
- **任务是连续的**：`add_new_task()` 表示后续任务，不是新对话
- **没有"重置"需求**：官方假设用户想要连续对话

但对于 AgentMatrix 来说：
- **每次 `use_browser` 调用都是独立的任务**
- **不需要 browser-use Agent 记住之前的操作**
- **MicroAgent 会管理任务上下文**

因此，Fresh Start 更符合我们的设计。

## 向后兼容性

### ✅ 完全兼容
- 不影响 Browser 实例的生命周期
- 不影响外部接口（`use_browser()` 参数不变）
- 不影响其他 skill 的使用

### 行为变化
| 场景 | 之前 | 现在 |
|------|------|------|
| 多次 `use_browser` | 共享历史 | 独立任务 |
| Prompt 长度 | 逐渐增长 | 固定长度 |
| Agent 记忆 | 记住所有操作 | 每次都是新的 |

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 性能开销 | 很小（~10-50ms） | 可忽略不计 |
| 浏览器复用失效 | 无影响 | Browser 生命周期独立 |
| 需要共享上下文的场景 | 可能不适用 | 可通过 MicroAgent 管理 |

## 未来优化

### 可选改进
1. **添加 `fresh_start` 参数**：让调用者选择是否清除历史
2. **智能复用**：同一轮内的多次调用共享历史，不同轮独立
3. **历史压缩**：保留最近 N 个任务，清除更早的

### 当前方案优势
- ✅ 简单直接，易于理解
- ✅ 符合"每次调用独立"的语义
- ✅ 避免 prompt 爆炸
- ✅ 性能开销可忽略

## 总结

通过**每次创建新 Agent 实例**的方式，实现了 Fresh Start：
- ✅ 清除了所有任务历史
- ✅ 保留了浏览器状态
- ✅ 性能开销极小
- ✅ 代码简洁易维护

这是一个简单而有效的解决方案，符合 AgentMatrix 的设计理念。
