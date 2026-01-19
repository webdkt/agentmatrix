# Micro Agent 重构计划

## 版本管理

**备份分支**: `backup-before-micro-agent-refactor`
**当前分支**: `main`
**提交点**: `4bece8f` (Feat: Add Micro Agent support for subtask execution)

## 回退方法

如果重构出现问题，可以回退：

```bash
# 方法1: 切换到备份分支
git checkout backup-before-micro-agent-refactor

# 方法2: 在 main 分支上重置到备份点
git checkout main
git reset --hard 4bece8f

# 方法3: 创建新分支从备份点开始
git checkout -b new-feature backup-before-micro-agent-refactor
```

## 重构目标

### 核心理念

**Micro Agent 是基础执行单元，BaseAgent 是状态管理器**

- MicroAgent：无状态、单次任务执行
- BaseAgent：有状态、多 session 管理、使用 Micro Agent 作为执行引擎

### 设计方案

#### 1. MicroAgent 类增强

**新增能力**：
- `initial_history` 参数：支持"恢复记忆"
- `get_history()` 方法：获取完整的对话历史
- 返回值改为：返回最后的结果（而不是 history）

**接口**：
```python
async def execute(
    self,
    persona: str,
    task: str,
    available_actions: List[str],
    task_context: Optional[Dict] = None,
    max_steps: int = 50,
    exit_condition: str = "finish_task",
    initial_history: Optional[List[Dict]] = None  # 新增
) -> str:  # 返回值：结果（而不是 history）
    """执行任务，返回结果"""
    ...

def get_history(self) -> List[Dict]:  # 新增
    """获取完整的对话历史"""
    return self.messages
```

#### 2. BaseAgent 重构

**process_email() 改为使用 Micro Agent**：

```python
async def process_email(self, email: Email):
    """处理邮件 = 恢复记忆 + 执行 + 保存记忆"""
    session = self._resolve_session(email)

    # 执行（传入之前的 history）
    result = await self._micro_core.execute(
        persona=self.get_prompt(),
        task=str(email),
        available_actions=list(self.actions_map.keys()),
        max_steps=100,
        exit_condition="rest_n_wait",
        initial_history=session.history  # 恢复记忆
    )

    # 保存更新后的 history
    session.history = self._micro_core.get_history()
```

**_run_micro_agent() 保持简洁**：

```python
async def _run_micro_agent(self, persona, task, ...) -> str:
    """子任务执行（无状态）"""
    result = await self._micro_core.execute(
        persona=persona,
        task=task,
        available_actions=...,
        exit_condition="finish_task",
        initial_history=None  # 新对话
    )
    return result
```

## 实现步骤

### Step 1: 增强 MicroAgent 类

**文件**: `src/agentmatrix/agents/micro_agent.py`

**修改**:
1. `execute()` 方法添加 `initial_history` 参数
2. 修改初始化逻辑：区分新对话 vs 恢复记忆
3. 返回值改为返回结果
4. 添加 `get_history()` 方法

### Step 2: 重构 BaseAgent

**文件**: `src/agentmatrix/agents/base.py`

**修改**:
1. 创建 `_micro_core` 实例（在 `__init__` 中）
2. 重写 `process_email()`：使用 `_micro_core.execute()`
3. 保持 `_run_micro_agent()` 接口不变

### Step 3: 更新文档

**文件**: `docs/micro_agent_usage.md`, `docs/micro_agent_design.md`

**修改**:
1. 更新架构说明
2. 强调"恢复记忆"概念
3. 更新代码示例

### Step 4: 测试

**测试点**:
1. BaseAgent 处理单封邮件
2. BaseAgent 处理回复邮件（验证 session 恢复）
3. `_run_micro_agent()` 调用（验证无状态执行）

## 预期收益

### 代码复用
- think-act 循环只在 MicroAgent 中实现一次
- BaseAgent 复用这个逻辑

### 概念统一
- BaseAgent = 邮件驱动的 Micro Agent 集合
- 每个 email 处理 = 一个 Micro Agent 生命周期（带记忆恢复）

### 代码简化
- BaseAgent.process_email() 从 ~100 行 减少到 ~20 行
- 逻辑更清晰：恢复记忆 → 执行 → 保存记忆

## 风险评估

### 风险点
1. Session 管理逻辑可能需要微调
2. 历史恢复的边界情况（空 session、损坏的 session）
3. 退出条件的处理（rest_n_wait vs finish_task）

### 缓解措施
1. 详细的日志记录
2. 完整的测试覆盖
3. 保留备份分支，可快速回退

## 时间估计

- Step 1: 30 分钟
- Step 2: 20 分钟
- Step 3: 15 分钟
- Step 4: 30 分钟
- **总计**: ~1.5 小时

## 完成标准

- [ ] MicroAgent 支持 initial_history
- [ ] MicroAgent 返回结果（而不是 history）
- [ ] MicroAgent 提供 get_history() 方法
- [ ] BaseAgent.process_email() 使用 Micro Agent
- [ ] 所有测试通过
- [ ] 文档更新完整
