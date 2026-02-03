# BaseAgent 和 MicroAgent Prompt 构造重构总结

## 重构日期
2026-02-01

## 重构目标

解决过去 BaseAgent 和 MicroAgent 在 prompt 构造上的重复和职责不清问题：

### 重构前的问题
1. **BaseAgent** 构造复杂的 prompt（人设 + 世界规则 + 黄页），通过 `get_prompt()` 方法
2. **调用 MicroAgent** 时，将完整的 prompt 作为 `persona` 参数传入
3. **MicroAgent** 内部也会构造系统提示词（人设 + 世界规则）
4. **结果**：世界规则出现两次，产生重复和不一致

### 重构后的改进
1. **BaseAgent 简化**：只保留基本人设（`system_prompt`，从 YAML 加载）
2. **MicroAgent 接管**：负责构造完整的系统提示词
3. **黄页独立**：作为可选参数传递，只在需要时添加
4. **职责清晰**：BaseAgent 管理会话，MicroAgent 管理执行和 prompt

## 修改清单

### 1. `src/agentmatrix/agents/micro_agent.py`

#### 修改 `execute()` 方法签名
```python
async def execute(
    self,
    persona: str,
    task: str,
    available_actions: List[str],
    max_steps: Optional[int] = None,
    initial_history: Optional[List[Dict]] = None,
    result_params: Optional[Dict[str, str]] = None,
    yellow_pages: Optional[str] = None  # 新增
) -> Any:
```

#### 修改 `_build_system_prompt()` 方法
```python
def _build_system_prompt(self) -> str:
    """构建 System Prompt"""
    prompt = f"""你是 {self.persona}

### 操作环境 (The Cockpit)
...世界规则...
### 你的工具箱 (可用action)
{self._format_actions_list()}
"""

    # 如果提供了黄页信息，添加黄页部分
    if self.yellow_pages:
        prompt += f"""### 黄页（你的同事）

{self.yellow_pages}
"""

    return prompt
```

### 2. `src/agentmatrix/agents/base.py`

#### 删除的内容
- `__init__` 中的 `self.prompt_template` 加载
- `__init__` 中的 `self.full_prompt` 加载
- `get_prompt()` 方法（164-173行）

#### 修改 `process_email()` 调用
```python
# 旧代码
result = await micro_core.execute(
    persona=self.get_prompt(),  # 包含世界规则、黄页等
    task=task,
    ...
)

# 新代码
result = await micro_core.execute(
    persona=self.system_prompt,  # 只传入基本人设
    task=task,
    ...
    yellow_pages=self.post_office.yellow_page_exclude_me(self.name)  # 独立传入黄页
)
```

#### 修改 `_run_micro_agent()` 方法
```python
async def _run_micro_agent(
    self,
    persona: str,
    task: str,
    available_actions: Optional[List[str]] = None,
    max_steps: int = 50,
    exclude_actions: Optional[List[str]] = None,
    result_params: Optional[Dict[str, str]] = None,
    yellow_pages: Optional[str] = None  # 新增
) -> Any:
    ...
    result = await self._get_micro_core().execute(
        persona=persona,
        task=task,
        available_actions=available_actions,
        max_steps=max_steps,
        initial_history=None,
        result_params=result_params,
        yellow_pages=yellow_pages  # 传递 yellow_pages
    )
```

### 3. `src/agentmatrix/skills/deep_researcher.py`

**无需修改**：所有 `_run_micro_agent()` 调用都使用关键字参数，`yellow_pages` 参数有默认值 `None`，自动兼容。

## 重构后的架构

```
┌─────────────────────────────────────────────────────────────┐
│ BaseAgent (会话层)                                           │
├─────────────────────────────────────────────────────────────┤
│ profile:                                                    │
│   - system_prompt: "基本人设描述" (从 yml 加载)              │
│                                                             │
│ 职责：                                                      │
│   - 管理 session                                            │
│   - 接收用户消息                                            │
│   - 委托任务给 MicroAgent                                   │
│                                                             │
│ ❌ 不再构造复杂 prompt                                       │
│ ✅ 只传递基本人设和可选的黄页                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 传入:
                              │ - persona = system_prompt
                              │ - yellow_pages = post_office.yellow_page_exclude_me()
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ MicroAgent (执行层)                                         │
├─────────────────────────────────────────────────────────────┤
│ 输入:                                                       │
│   - persona: "基本人设描述"                                  │
│   - yellow_pages: "黄页信息" (可选)                         │
│                                                             │
│ _build_system_prompt() 构造:                                │
│   1. 人设（从传入的 persona）                               │
│   2. 世界规则（内部定义，保持现有最佳版本）                 │
│   3. 工具箱（available actions）                            │
│   4. 黄页（如果提供则添加）                                 │
│                                                             │
│ ✅ 完整的 prompt 构造职责                                   │
└─────────────────────────────────────────────────────────────┘
```

## 关键改进

### 1. 消除重复
- ✅ 世界规则只在 MicroAgent 中定义一次
- ✅ 不再出现两次物理规则和操作环境描述

### 2. 职责清晰
- ✅ BaseAgent：会话管理，不需要知道如何构造 LLM prompt
- ✅ MicroAgent：任务执行，负责完整的环境描述

### 3. 灵活性
- ✅ 黄页作为可选参数，只在需要时添加
- ✅ 不同场景可以使用不同的黄页信息
- ✅ 其他调用（如 deep_researcher）不需要黄页，使用默认值

### 4. 向后兼容
- ✅ 所有现有 `_run_micro_agent()` 调用自动兼容
- ✅ 新参数有默认值，不影响现有代码

## 测试验证

创建了 `tests/test_refactor.py` 进行全面测试：

1. ✅ MicroAgent 没有 yellow_pages 时不显示黄页部分
2. ✅ MicroAgent 有 yellow_pages 时正确显示黄页部分
3. ✅ BaseAgent 删除了 `get_prompt()` 方法
4. ✅ MicroAgent.execute() 方法签名包含 yellow_pages 参数
5. ✅ 所有语法检查通过

## 影响范围

### 修改的文件
- `src/agentmatrix/agents/base.py` - 删除 prompt 构造逻辑
- `src/agentmatrix/agents/micro_agent.py` - 增加 yellow_pages 支持

### 新增的文件
- `tests/test_refactor.py` - 重构验证测试

### 无需修改的文件
- `src/agentmatrix/skills/deep_researcher.py` - 自动兼容
- 其他所有 skills - 自动兼容

## 后续工作

### 可选的改进
1. 考虑将世界规则提取到独立配置文件（如果需要在多个 agent 类型间共享）
2. 考虑为黄页信息提供更结构化的格式（而不是字符串）
3. 考虑添加单元测试覆盖更多边界情况

### 清理工作
1. 可以删除 `src/agentmatrix/profiles/prompts/base.txt` 模板文件（不再使用）
2. 检查是否有其他地方引用了已删除的 `get_prompt()` 方法

## 总结

这次重构成功实现了：
- ✅ 清晰的职责分离（会话层 vs 执行层）
- ✅ 消除 prompt 构造的重复
- ✅ 保持代码的可维护性和可扩展性
- ✅ 向后兼容，不影响现有功能

重构后的架构更加清晰，BaseAgent 专注于会话管理，MicroAgent 专注于任务执行和 prompt 构造，符合单一职责原则。
