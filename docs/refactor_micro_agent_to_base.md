# BaseAgent/MicroAgent 重构计划

## 目标
将 MicroAgent 的功能整合回 BaseAgent，消除不必要的类继承和复杂的注入逻辑。

## 核心原则
1. **不删除旧代码**：在新文件中实现重构版本
2. **功能不丢失**：所有现有功能必须保留
3. **逐步验证**：每阶段完成后与旧版本比对
4. **无向后兼容包袱**：不考虑兼容性，做彻底的重构
5. **可回滚**：通过 Git 确保可以随时退回当前版本

---

## 文件结构

```
src/agentmatrix/agents/
├── base.py              # 旧版本（保留，不修改）
├── micro_agent.py       # 旧版本（保留，不修改）
├── base_agent.py        # 新版本：主逻辑和类定义
└── base_util.py         # 新版本：工具方法和辅助函数
```

### 文件职责划分

**base_agent.py** (~500-600 行)
- `ExecutionResult` 类：execute() 的返回结果
- `ExecutionContext` 类：执行上下文封装
- `BaseAgent` 类：主逻辑
  - 初始化（__init__）
  - Action 扫描和注册
  - Session/Workspace 管理
  - 核心方法：execute(), process_email()
  - 主循环：_run_loop()
  - Action 执行：_execute_action(), _think()
  - 各种 action 定义（send_email, all_finished 等）

**base_util.py** (~300-400 行)
- 格式化方法
  - `format_actions_list()`
  - `format_task_message()`
  - `format_messages_for_debug()`
- Action 检测和解析
  - `extract_mentioned_actions()`
  - `parse_and_validate_actions()`
- Prompt 构建
  - `build_system_prompt()`
- 消息管理
  - `add_message()`
- 日志辅助
  - `get_log_context()`
- LLM 服务监控
  - `is_llm_available()`
  - `wait_for_llm_recovery()`

---

## 当前架构分析

### BaseAgent (src/agentmatrix/agents/base.py)
**职责：**
- 长期存活的 Agent，有 session、inbox、workspace
- Actions 定义和注册（`@register_action` 装饰器）
- 在 `process_email()` 中创建 MicroAgent 来执行任务

**核心属性：**
- `actions_map`: action 名称 -> 未绑定方法（`method.__func__`）
- `actions_meta`: action 元数据（给小脑看）
- `brain`, `cerebellum`, `vision_brain`
- `working_context`: 工作目录上下文
- `session_manager`, `current_session`
- `_session_context`: SessionContext 对象

**核心方法：**
- `_scan_methods()`: 扫描被装饰的方法，存入 `actions_map`
- `process_email()`: 主入口，创建 MicroAgent 执行
- `get_persona()`: 获取渲染后的 persona
- `get_skill_prompt()`: 获取 skill prompt
- 各种 action：`send_email`, `rest_n_wait`, `all_finished` 等

### MicroAgent (src/agentmatrix/agents/micro_agent.py)
**职责：**
- 临时任务专用的轻量级 Agent
- think-negotiate-act 循环
- 每次执行是独立上下文

**核心属性（都在 `__init__` 中）：**
- 从 parent 继承：`brain`, `cerebellum`, `action_registry`, `logger`
- `working_context`: 可独立指定或继承自 parent
- `_session_context`: 可独立或共享（通过 `independent_session_context`）
- `messages`: 对话历史
- `run_label`, `persona`, `task`, `available_actions`
- `result`, `step_count`, `last_action_name`

**核心方法：**
- `execute()`: 执行任务的主入口
- `_run_loop()`: think-negotiate-act 主循环
- `_think()`: 调用 brain
- `_detect_actions()`: 两阶段检测（提到的 + 真正要执行的）
- `_execute_action()`: 动态绑定方法到 self 并执行
- `_build_system_prompt()`: 构建系统提示词
- `_format_actions_list()`: 格式化可用 actions
- `_is_llm_available()`, `_wait_for_llm_recovery()`: LLM 服务监控

---

## 需要保留的所有功能

### 1. BaseAgent 现有功能
- [ ] Profile 加载和解析
- [ ] Persona 渲染（多个 persona，支持模板变量）
- [ ] Skill prompt 加载和渲染（带缓存）
- [ ] Action 扫描和注册（`@register_action` 装饰器）
- [ ] Session 管理（session_manager, current_session, user_session_id）
- [ ] Workspace 管理（workspace_root, private_workspace, current_workspace）
- [ ] WorkingContext 管理（base_dir, current_dir）
- [ ] SessionContext 管理（持久化上下文，自动保存）
- [ ] Transient Context（非持久化内存数据）
- [ ] 事件系统（emit, async_event_callback）
- [ ] Inbox 和邮件处理（run, process_email）
- [ ] 文件路径解析（_resolve_real_path）
- [ ] 通用 actions（all_finished, rest_n_wait, send_email, get_current_datetime）

### 2. MicroAgent 现有功能
- [ ] 独立的执行上下文（messages, run_label, result, step_count）
- [ ] execute() 方法（接受 persona, task, available_actions 等参数）
- [ ] 独立或共享的 SessionContext（independent_session_context）
- [ ] WorkingContext 继承或独立
- [ ] think-negotiate-act 循环（_run_loop）
- [ ] 两阶段 action 检测（_detect_actions）
- [ ] Action 动态绑定和执行（_execute_action）← **改为直接调用**
- [ ] System prompt 构建（简化模式和完整模式）
- [ ] 批量 action 执行（保持顺序，支持重复）
- [ ] 特殊 actions 处理（all_finished, exit_actions）
- [ ] 步数和时间限制（max_steps, max_time）
- [ ] LLM 服务异常处理（wait for recovery）
- [ ] 对话历史管理（messages, get_history）
- [ ] Session 持久化（自动保存 history）
- [ ] 参数解析（通过 cerebellum）
- [ ] 结果参数动态配置（result_params）
- [ ] 黄页支持（yellow_pages）
- [ ] 日志上下文（_log, _get_log_context）

### 3. 不再需要的功能
- [x] MicroAgent 类本身（将被整合）
- [x] 动态绑定逻辑（`types.MethodType(raw_method, self)`）
- [x] `_scan_own_actions()` 方法（不再需要合并 action_registry）
- [x] 组件注入逻辑（从 parent 继承 brain, cerebellum 等）

---

## 实施步骤

### Phase 1: 准备和设计（1-2小时）
**目标：** 创建新文件，定义数据结构

**任务：**
1. 创建 `src/agentmatrix/agents/base_agent.py`
2. 创建 `src/agentmatrix/agents/base_util.py`
3. 定义 `ExecutionResult` 类（替代 MicroAgent 对象作为结果载体）
4. 创建 `ExecutionContext` 类（封装执行上下文）
5. 创建 `BaseAgent` 类骨架

**代码结构：**
```python
# base_agent.py

from dataclasses import dataclass
from typing import Dict, List, Optional, Any

@dataclass
class ExecutionResult:
    """execute() 的返回结果"""
    run_label: str
    messages: List[Dict]  # 对话历史
    result: Any  # 最终结果
    last_action_name: Optional[str]
    step_count: int
    duration: float

class ExecutionContext:
    """执行上下文（替代 MicroAgent 对象）"""
    def __init__(self, agent, run_label, ...):
        self.agent = agent  # 引用 BaseAgent
        self.messages = []
        self.run_label = run_label
        self.persona = None
        self.task = None
        self.available_actions = []
        self.result = None
        self.step_count = 0
        self.last_action_name = None
        # ... 其他执行状态

class BaseAgent(AutoLoggerMixin):
    """重构后的 BaseAgent（整合了 MicroAgent 功能）"""
    def __init__(self, profile):
        # 从 BaseAgent.__init__ 复制
        pass

    async def execute(self, ...) -> ExecutionResult:
        """执行任务（替代 MicroAgent.execute）"""
        pass
```

**验证：**
- [ ] 文件创建成功
- [ ] `ExecutionResult` 包含所有必要字段
- [ ] `ExecutionContext` 可以封装所有执行状态

---

### Phase 2: 实现工具方法（2-3小时）
**目标：** 实现 base_util.py 中的工具方法

**任务：**
1. 实现 `format_actions_list()`（从 MicroAgent._format_actions_list）
2. 实现 `format_task_message()`（从 MicroAgent._format_task_message）
3. 实现 `format_messages_for_debug()`（从 MicroAgent._format_messages_for_debug）
4. 实现 `build_system_prompt()`（从 MicroAgent._build_system_prompt）
5. 实现 `get_log_context()`（从 MicroAgent._get_log_context）

**代码结构：**
```python
# base_util.py

def format_actions_list(available_actions, action_registry) -> str:
    """格式化可用 actions 列表"""
    # From MicroAgent._format_actions_list:429
    pass

def format_task_message(task: str) -> str:
    """格式化任务消息"""
    # From MicroAgent._format_task_message:440
    pass

def format_messages_for_debug(messages: List[Dict]) -> str:
    """格式化 messages 为调试输出"""
    # From MicroAgent._format_messages_for_debug:446
    pass

def build_system_prompt(execution_context: ExecutionContext) -> str:
    """构建 System Prompt"""
    # From MicroAgent._build_system_prompt:376
    pass

def get_log_context(execution_context: ExecutionContext) -> dict:
    """提供日志上下文变量"""
    # From MicroAgent._get_log_context:992
    pass
```

**验证：**
- [ ] 所有格式化方法正确工作
- [ ] System prompt 支持简化模式和完整模式
- [ ] 与旧版本输出一致

**比对点：**
- `format_actions_list()` vs `MicroAgent._format_actions_list()`
- `build_system_prompt()` vs `MicroAgent._build_system_prompt()`

---

### Phase 3: 实现 Action 检测和解析（3-4小时）
**目标：** 实现两阶段 action 检测逻辑

**任务：**
1. 实现 `extract_mentioned_actions()`（从 MicroAgent._extract_mentioned_actions）
2. 实现 `parse_and_validate_actions()`（从 MicroAgent._parse_and_validate_actions）
3. 实现 `detect_actions()`（从 MicroAgent._detect_actions，整合两阶段）

**代码结构：**
```python
# base_util.py

def extract_mentioned_actions(thought: str, available_actions: List[str]) -> List[str]:
    """
    提取用户**提到**的所有 action（完整单词匹配）

    From MicroAgent._extract_mentioned_actions:683
    """
    pass

async def parse_and_validate_actions(
    raw_reply: str,
    mentioned_actions: List[str],
    available_actions: List[str]
) -> Dict[str, Any]:
    """
    Parser: 提取并验证要执行的 actions

    From MicroAgent._parse_and_validate_actions:728
    """
    pass

async def detect_actions(
    thought: str,
    messages: List[Dict],
    brain,
    cerebellum,
    available_actions: List[str]
) -> List[str]:
    """
    两阶段检测：判断用户真正要执行的 actions

    From MicroAgent._detect_actions:797
    """
    pass
```

**验证：**
- [ ] 正则提取正确工作
- [ ] 两阶段检测正确工作（提到 → 真正执行）
- [ ] 防止幻觉（必须在 mentioned_actions 中）
- [ ] 支持重复的 action（保持顺序）

**比对点：**
- `extract_mentioned_actions()` vs `MicroAgent._extract_mentioned_actions()`
- `parse_and_validate_actions()` vs `MicroAgent._parse_and_validate_actions()`
- `detect_actions()` vs `MicroAgent._detect_actions()`

---

### Phase 4: 实现消息管理和 LLM 监控（2-3小时）
**目标：** 实现消息管理和 LLM 服务监控

**任务：**
1. 实现 `add_message()`（支持 session 持久化）
2. 实现 `is_llm_available()`（从 MicroAgent._is_llm_available）
3. 实现 `wait_for_llm_recovery()`（从 MicroAgent._wait_for_llm_recovery）

**代码结构：**
```python
# base_util.py

def add_message(
    execution_context: ExecutionContext,
    role: str,
    content: str
):
    """
    添加消息到对话历史（支持 session 持久化）

    From MicroAgent._add_message:969
    """
    pass

def is_llm_available(execution_context: ExecutionContext) -> bool:
    """
    检查 LLM 服务是否可用

    From MicroAgent._is_llm_available:612
    """
    pass

async def wait_for_llm_recovery(execution_context: ExecutionContext):
    """
    等待 LLM 服务恢复（轮询方式）

    From MicroAgent._wait_for_llm_recovery:630
    """
    pass
```

**验证：**
- [ ] Message 正确添加到 context.messages
- [ ] Session 自动保存（如果有 session_manager）
- [ ] LLM 服务可用性检查正确
- [ ] 等待恢复逻辑正确

**比对点：**
- `add_message()` vs `MicroAgent._add_message()`
- `is_llm_available()` vs `MicroAgent._is_llm_available()`
- `wait_for_llm_recovery()` vs `MicroAgent._wait_for_llm_recovery()`

---

### Phase 5: 实现 ExecutionContext（2-3小时）
**目标：** 实现执行上下文封装

**任务：**
1. 实现 `ExecutionContext.__init__()`（封装执行状态）
2. 实现上下文初始化方法（from_execute_params）
3. 实现对话历史初始化（initialize_conversation）
4. 实现便捷方法（get_history, update_session_context等）

**代码结构：**
```python
# base_agent.py

class ExecutionContext:
    """执行上下文（替代 MicroAgent 对象）"""

    def __init__(self, agent: 'BaseAgent'):
        self.agent = agent
        self.messages: List[Dict] = []
        self.run_label: Optional[str] = None
        self.persona: Optional[str] = None
        self.task: Optional[str] = None
        self.available_actions: List[str] = []
        self.result = None
        self.step_count = 0
        self.last_action_name: Optional[str] = None
        self.max_steps: Optional[int] = None
        self.max_time: Optional[float] = None
        self.yellow_pages: Optional[str] = None
        self.simple_mode: bool = False
        self.session: Optional[Dict] = None
        self.session_manager = None

    @classmethod
    def from_execute_params(
        cls,
        agent: 'BaseAgent',
        run_label: str,
        persona: str,
        task: str,
        available_actions: List[str],
        ...
    ) -> 'ExecutionContext':
        """从 execute() 参数创建上下文"""
        pass

    def initialize_conversation(self, initial_history: Optional[List[Dict]] = None):
        """初始化对话历史"""
        # From MicroAgent._initialize_conversation:366
        pass

    def get_history(self) -> List[Dict]:
        """获取完整的对话历史"""
        # From MicroAgent.get_history:983
        pass
```

**验证：**
- [ ] ExecutionContext 可以正确初始化
- [ ] from_execute_params 正确处理所有参数
- [ ] 对话历史正确初始化（支持 session 和 initial_history）
- [ ] 支持独立或共享的 SessionContext
- [ ] 支持独立或继承的 WorkingContext

**比对点：**
- `ExecutionContext.__init__` vs `MicroAgent.__init__`
- `ExecutionContext.initialize_conversation` vs `MicroAgent._initialize_conversation`

---

### Phase 6: 实现 execute() 主流程（3-4小时）
**目标：** 实现主要的执行流程

**任务：**
1. 实现 `execute()` 方法签名和参数处理
2. 创建 ExecutionContext
3. 初始化对话历史
4. 调用主循环
5. 构造和返回 ExecutionResult

**代码结构：**
```python
# base_agent.py

class BaseAgent(AutoLoggerMixin):

    async def execute(
        self,
        run_label: str,
        persona: str,
        task: str,
        available_actions: List[str],
        max_steps: Optional[int] = None,
        max_time: Optional[float] = None,
        initial_history: Optional[List[Dict]] = None,
        result_params: Optional[Dict[str, str]] = None,
        yellow_pages: Optional[str] = None,
        session: Optional[Dict] = None,
        session_manager = None,
        simple_mode: bool = False,
        exit_actions = [],
        working_context = None,
        independent_session_context: bool = False,
    ) -> ExecutionResult:
        """
        执行任务（替代 MicroAgent.execute）

        From MicroAgent.execute:221
        """
        # 1. 创建 ExecutionContext
        # 2. 初始化对话历史
        # 3. 运行主循环
        # 4. 返回 ExecutionResult
        pass
```

**验证：**
- [ ] execute() 接受所有必要参数
- [ ] ExecutionContext 正确创建
- [ ] 对话历史正确初始化
- [ ] 主循环正确调用
- [ ] 返回正确的 ExecutionResult

**比对点：**
- `BaseAgent.execute()` vs `MicroAgent.execute()`
- 确保所有参数都被正确处理

---

### Phase 7: 实现主循环 _run_loop（4-5小时）
**目标：** 实现 think-negotiate-act 循环

**任务：**
1. 实现 `_run_loop()` 方法（复制主循环逻辑）
2. 实现步数和时间限制检查
3. 实现 think → detect → execute → feedback 流程
4. 实现批量 action 执行（保持顺序）
5. 实现特殊 actions 处理（all_finished, exit_actions）
6. 实现 LLM 异常处理

**代码结构：**
```python
# base_agent.py

class BaseAgent(AutoLoggerMixin):

    async def _run_loop(self, ctx: ExecutionContext, exit_actions = []):
        """
        执行主循环

        From MicroAgent._run_loop:472
        """
        # 复制主循环逻辑
        # 调用 base_util 中的工具方法
        pass

    async def _think(self, ctx: ExecutionContext) -> str:
        """调用 Brain 进行思考"""
        # From MicroAgent._think:678
        pass

    async def _prepare_feedback_message(
        self, ctx: ExecutionContext, combined_result: str, step_count: int, start_time: float
    ) -> str:
        """
        准备反馈消息（Hook 方法）

        From MicroAgent._prepare_feedback_message:657
        """
        pass
```

**验证：**
- [ ] 主循环正确执行
- [ ] 步数限制正确工作
- [ ] 时间限制正确工作
- [ ] 批量 actions 正确执行
- [ ] 特殊 actions 正确处理
- [ ] LLM 异常正确处理

**比对点：**
- `BaseAgent._run_loop()` vs `MicroAgent._run_loop()`
- 确保所有逻辑都被保留

---

### Phase 8: 实现 action 执行（4-5小时）
**目标：** 实现 action 执行逻辑（**关键差异：不再动态绑定**）

**任务：**
1. 实现 `_execute_action()`（直接调用 self 的方法）
2. 通过 cerebellum 解析参数
3. 执行方法
4. 记录 last_action_name

**代码结构：**
```python
# base_agent.py

class BaseAgent(AutoLoggerMixin):

    async def _execute_action(
        self,
        ctx: ExecutionContext,
        action_name: str,
        thought: str,
        action_index: int,
        action_list: List[str]
    ) -> Any:
        """
        执行 action（关键：直接调用 self 的方法，不再动态绑定）

        From MicroAgent._execute_action:873

        关键差异：
        - 旧版：bound_method = types.MethodType(raw_method, micro_agent_self)
        - 新版：直接调用 self.actions_map[action_name](self, **params)
        """
        # 1. 获取方法（从 self.actions_map）
        # 2. 解析参数（通过 cerebellum）
        # 3. 执行方法（传入 self 作为第一个参数）
        # 4. 记录 last_action_name
        pass
```

**关键变更：**
```python
# 旧版（MicroAgent._execute_action:906）
bound_method = types.MethodType(raw_method, self)  # 绑定到 micro_agent
result = await bound_method(**params)

# 新版（BaseAgent._execute_action）
method = self.actions_map[action_name]  # 未绑定的函数
result = await method(self, **params)  # 传入 self 作为第一个参数
```

**验证：**
- [ ] Action 正确执行
- [ ] 参数解析正确（通过 cerebellum）
- [ ] 不再需要 types.MethodType
- [ ] self 在 action 中正确指向 BaseAgent

**比对点：**
- `BaseAgent._execute_action()` vs `MicroAgent._execute_action()`
- **关键差异**：直接调用 vs 动态绑定

---

### Phase 9: 迁移 BaseAgent 功能（3-4小时）
**目标：** 将 BaseAgent 的所有功能迁移到新 BaseAgent

**任务：**
1. 复制 `__init__()` 初始化逻辑
2. 复制 `_scan_methods()` 逻辑
3. 复制 session 管理逻辑
4. 复制 workspace 管理逻辑
5. 复制 WorkingContext/SessionContext 管理逻辑
6. 复制所有 actions（all_finished, send_email 等）
7. 复制事件系统（emit）
8. 复制 `process_email()` 逻辑（改为调用 self.execute）

**代码结构：**
```python
# base_agent.py

class BaseAgent(AutoLoggerMixin):
    _log_from_attr = "name"

    def __init__(self, profile):
        # From BaseAgent.__init__:26
        pass

    def _scan_methods(self):
        """扫描并生成元数据"""
        # From BaseAgent._scan_methods:210
        pass

    @property
    def workspace_root(self):
        # From BaseAgent.workspace_root:196
        pass

    @property
    def private_workspace(self) -> Path:
        # From BaseAgent.private_workspace:228
        pass

    @property
    def current_workspace(self) -> Path:
        # From BaseAgent.current_workspace:248
        pass

    async def process_email(self, email: Email):
        """
        处理邮件 = 恢复记忆 + 执行 + 保存记忆

        From BaseAgent.process_email:360

        关键变更：改为调用 self.execute
        """
        # 1. Session 管理
        # 2. 调用 self.execute（而不是创建 MicroAgent）
        # 3. 保存 session
        pass

    @register_action(...)
    async def all_finished(self, result: str = None) -> Any:
        # From BaseAgent.all_finished:804
        pass

    @register_action(...)
    async def send_email(self, to, body, subject=None):
        # From BaseAgent.send_email:496
        pass

    # ... 其他 actions
```

**验证：**
- [ ] BaseAgent 可以正确初始化
- [ ] Actions 正确扫描和注册
- [ ] Session 管理正常
- [ ] Workspace 管理正常
- [ ] process_email 正常工作（调用 self.execute）
- [ ] 所有 actions 正常工作

**比对点：**
- `BaseAgent.__init__()` vs 旧版 `BaseAgent.__init__()`
- `BaseAgent.process_email()` vs 旧版 `BaseAgent.process_email()`
- **关键差异**：不再创建 MicroAgent，直接调用 self.execute

---

### Phase 10: 集成测试和修复（5-8小时）
**目标：** 全面测试和修复

**任务：**
1. 创建简单的测试脚本
2. 测试基本 execute 流程
3. 测试嵌套 execute 流程（action 中调用 self.execute）
4. 测试 session 持久化
5. 测试 LLM 服务异常处理
6. 测试所有 actions
7. 修复发现的问题

**测试脚本示例：**
```python
# test_refactor.py

async def test_basic_execute():
    """测试基本 execute 流程"""
    agent = BaseAgent(profile)
    result = await agent.execute(
        run_label="test",
        persona="...",
        task="...",
        available_actions=["all_finished"]
    )
    assert result.result is not None
    assert len(result.messages) > 0

async def test_nested_execute():
    """测试嵌套 execute"""
    agent = BaseAgent(profile)

    @register_action(...)
    async def subtask(self):
        # action 中嵌套调用 execute
        result = await self.execute(...)
        return result

    # 测试嵌套调用
    pass
```

**验证：**
- [ ] 基本 execute 正常工作
- [ ] 嵌套 execute 正常工作（**关键**）
- [ ] Session 正确保存和恢复
- [ ] LLM 异常正常处理
- [ ] 所有 actions 正常工作

---

### Phase 11: 最终验证和比对（2-3小时）
**目标：** 最终验证并确认无功能丢失

**任务：**
1. 逐项比对功能清单
2. 静态代码审查（逐行比对）
3. 创建功能对比文档
4. 确认无功能丢失

**功能对比模板：**
```markdown
| 功能 | 旧版位置 | 新版位置 | 状态 |
|------|----------|----------|------|
| 执行上下文 | MicroAgent | ExecutionContext | ✅ |
| execute 方法 | MicroAgent.execute:221 | BaseAgent.execute | ✅ |
| 两阶段检测 | MicroAgent._detect_actions:797 | base_util.detect_actions | ✅ |
| 动态绑定 | MicroAgent._execute_action:906 | ~~已移除~~ | ✅ |
| Action 执行 | types.MethodType | 直接调用 | ✅ |
| ... | ... | ... | ... |
```

**验证：**
- [ ] 所有功能都被实现
- [ ] 无功能丢失
- [ ] 嵌套执行正常工作
- [ ] 代码更简洁易维护

---

## 风险管理

### 高风险区域
1. **action 执行逻辑**（Phase 8）
   - 从动态绑定改为直接调用
   - 需要确保 self 正确传递
   - **缓解**：仔细测试所有 actions

2. **嵌套执行**（Phase 10）
   - 确保 ExecutionContext 不会互相干扰
   - 确保嵌套的 messages 不会混淆
   - **缓解**：创建专门的嵌套测试

3. **session 持久化**（Phase 4, 9）
   - 确保 messages 正确保存
   - 确保多个 ExecutionContext 共享 session 时不出错
   - **缓解**：测试不同的 session 配置

4. **LLM 异常处理**（Phase 7）
   - 确保服务恢复后可以继续执行
   - 确保不会丢失 context
   - **缓解**：模拟 LLM 服务故障

### 回滚策略
1. **Git 分支**：每个 Phase 完成后 commit
   ```
   git checkout -b refactor/base-agent-integration
   git commit -m "Phase X: 完成XXX"
   ```

2. **功能标记**：使用注释标记每个功能的来源
   ```python
   # From MicroAgent.execute:221
   async def execute(self, ...):
       pass
   ```

3. **比对清单**：每个 Phase 完成后更新功能清单

### 验证方法
1. **静态比对**：逐行比对代码，确保逻辑一致
2. **动态测试**：运行相同的测试用例，比对结果
3. **代码审查**：每个 Phase 完成后进行 code review

---

## 成功标准

### 必须满足
- [ ] 所有功能都被实现（见功能清单）
- [ ] 嵌套 execute 正常工作（action 中调用 self.execute）
- [ ] session 持久化正常
- [ ] 所有测试通过
- [ ] 无功能丢失

### 优化目标
- [ ] 代码更简洁（预计减少 30% 以上的代码）
  - 旧版：base.py (822行) + micro_agent.py (998行) = 1820行
  - 新版：base_agent.py (~600行) + base_util.py (~400行) = 1000行
  - 减少：~45%

- [ ] 更容易理解（消除动态绑定）
  - 不再需要 `types.MethodType`
  - 不再需要复杂的注入逻辑

- [ ] 更容易维护（统一的上下文管理）
  - ExecutionContext 封装所有执行状态
  - 工具方法独立在 base_util.py

---

## 时间估算
- Phase 1: 1-2 小时
- Phase 2: 2-3 小时
- Phase 3: 3-4 小时
- Phase 4: 2-3 小时
- Phase 5: 2-3 小时
- Phase 6: 3-4 小时
- Phase 7: 4-5 小时
- Phase 8: 4-5 小时
- Phase 9: 3-4 小时
- Phase 10: 5-8 小时
- Phase 11: 2-3 小时

**总计：31-44 小时**

---

## 下一步行动

请确认此重构计划，确认后我将从 **Phase 1: 准备和设计** 开始。

确认后我将：
1. 创建 `src/agentmatrix/agents/base_agent.py`
2. 创建 `src/agentmatrix/agents/base_util.py`
3. 定义 `ExecutionResult` 类
4. 定义 `ExecutionContext` 类
5. 创建 `BaseAgent` 类骨架
