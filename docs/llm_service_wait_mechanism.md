# LLM 服务等待机制设计方案

## 一、问题背景

### 1.1 问题描述
AgentMatrix 完全依赖 LLM 服务运行。当 LLM 服务不可用时（网络故障、API 限流、服务宕机等），所有的 Agent 调用会失败，但目前系统缺乏应对机制。

### 1.2 核心需求
- 当 LLM 服务不可用时，所有 Agent 应该能够感知到这个全局状态
- MicroAgent 在执行循环中，应该能够检测 LLM 服务的可用性
- 当服务不可用时，MicroAgent 应该进入等待状态，直到服务恢复

---

## 二、当前架构理解

### 2.1 初始化流程
```
runtime.py (AgentMatrix)
  └── loader.py (AgentLoader)
       - 读取 llm_config.json
       - 创建 LLMClient 实例（brain, cerebellum, vision_brain）
       - 为每个 Agent 注入 brain 和 cerebellum
```

**关键点：**
- `llm_config.json` 中定义了 `default_llm` 和 `default_slm`
- 每个 Agent 有独立的 brain 和 cerebellum 实例
- 所有 Agent 实例都保存在 `AgentMatrix.agents` 字典中

### 2.2 执行机制
```
BaseAgent
  ├── run() - 主循环
  └── MicroAgent (通过 parent 引用)
       ├── execute() - 执行任务
       └── _run_loop() - think-negotiate-act 循环
            ├── _think() → brain.think()
            ├── _detect_actions() → cerebellum.backend.think_with_retry()
            └── _execute_action() → 调用具体 action
```

**关键点：**
- MicroAgent 通过 `self.root_agent` 可以访问到 BaseAgent
- BaseAgent 可以通过某种方式访问到 AgentMatrix（需要添加引用）
- LLM 调用主要在 `brain.think()` 和 `cerebellum.backend.think_with_retry()` 中

### 2.3 异常识别
当前 LLMClient 中的异常类型：
- `aiohttp.ClientError` - 网络连接错误
- `Exception` with "API请求失败" - HTTP 状态码非 200
- `Exception` with "Gemini Error" / "Vision API Error" - 各类 API 错误

**问题：**
- 异常类型分散，难以统一识别
- 没有专门的服务不可用异常
- 异常信息字符串不统一

---

## 三、方案设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    AgentMatrix                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  LLMServiceMonitor (新增)                         │  │
│  │  - 定期健康检查                                    │  │
│  │  - 维护服务状态                                    │  │
│  │  - 提供 llm_available Event                       │  │
│  └───────────────────────────────────────────────────┘  │
│           ↑ 引用                                         │
│  ┌──────────┴──────────────────────────────────────┐   │
│  │  BaseAgent (添加 runtime 引用)                   │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
           ↓ parent 引用
┌─────────────────────────────────────────────────────────┐
│                    MicroAgent                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  _run_loop() (添加等待逻辑)                       │  │
│  │  - 捕获 LLMServiceUnavailableError                │  │
│  │  - 检查 self.root_agent.runtime.llm_available    │  │
│  │  - 等待直到服务恢复                               │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 核心组件设计

#### 3.2.1 LLMServiceMonitor
**职责：**
- 定期 ping LLM 服务（default_llm 和 default_slm）
- 维护服务可用性状态
- 提供 `llm_available` asyncio.Event 供 Agent 等待

**接口：**
```python
class LLMServiceMonitor:
    def __init__(self, llm_config: dict, check_interval: int = 60):
        self.llm_config = llm_config  # 从 loader.py 传入
        self.check_interval = check_interval  # 检查间隔（秒）
        self.llm_available = asyncio.Event()  # 初始为 set（可用）
        self.status_map = {}  # {model_name: bool} 记录每个服务的状态

    async def start(self):
        """启动健康检查任务"""

    async def stop(self):
        """停止健康检查任务"""

    async def _health_check_loop(self):
        """定期检查循环"""

    async def check_service(self, model_name: str) -> bool:
        """检查单个服务（发送简单的 think 请求）"""

    def is_available(self, model_name: str = None) -> bool:
        """查询服务是否可用"""
```

**健康检查逻辑：**
1. 发送最简单的测试请求：`messages=[{"role": "user", "content": "hi"}]`
2. 设置短超时（如 10 秒）
3. 如果成功返回，服务可用
4. 如果超时或异常，服务不可用
5. 根据 default_llm 和 default_slm 的状态，决定全局 `llm_available` 的状态

#### 3.2.2 自定义异常类
```python
# core/exceptions.py (新增文件)

class LLMServiceUnavailableError(Exception):
    """LLM 服务不可用异常（基类）"""
    pass

class LLMServiceTimeoutError(LLMServiceUnavailableError):
    """LLM 服务超时"""
    pass

class LLMServiceConnectionError(LLMServiceUnavailableError):
    """LLM 服务连接失败"""
    pass
```

#### 3.2.3 LLMClient 改造
**目标：** 统一异常抛出，便于上层识别

**改动点：**
1. 导入新的异常类
2. 在 `async_stream_think()` 和 `_async_stream_think_gemini()` 中捕获底层异常
3. 识别并转换为 `LLMServiceUnavailableError` 或其子类
4. 在 think_with_retry 等方法中不再捕获这些异常，向上传播

**示例：**
```python
# llm_client.py

async def async_stream_think(self, messages, **kwargs):
    try:
        # ... 原有代码 ...
        async with aiohttp.ClientSession(...) as session:
            async with session.post(self.url, json=data) as resp:
                if resp.status != 200:
                    # 检查是否是服务不可用相关的错误
                    if resp.status in [502, 503, 504]:
                        raise LLMServiceUnavailableError(
                            f"LLM service unavailable: {resp.status}"
                        )
                    raise Exception(f"API请求失败: {resp.status}")
                # ... 流式处理 ...

    except aiohttp.ClientConnectorError as e:
        raise LLMServiceConnectionError(f"Connection failed: {str(e)}")
    except asyncio.TimeoutError as e:
        raise LLMServiceTimeoutError(f"Request timeout: {str(e)}")
```

#### 3.2.4 AgentMatrix 改造
**改动：**
1. 在 `__init__` 中创建 `LLMServiceMonitor` 实例
2. 启动 monitor 任务
3. 添加 `stop()` 方法用于优雅关闭（先停 monitor，再停其他）
4. 为每个 BaseAgent 注入 `runtime` 引用

**示例：**
```python
# runtime.py

class AgentMatrix:
    def __init__(self, ...):
        # ... 原有代码 ...

        # 创建 LLM 服务监控器
        from .core.service_monitor import LLMServiceMonitor
        llm_config = loader.llm_config  # 从 loader 获取
        self.llm_monitor = LLMServiceMonitor(
            llm_config=llm_config,
            check_interval=60  # 每分钟检查一次
        )

        # 启动监控任务
        self.monitor_task = asyncio.create_task(self.llm_monitor.start())

        # 为每个 Agent 注入 runtime 引用
        for agent in self.agents.values():
            agent.runtime = self

    async def save_matrix(self):
        """修改：先停监控，再停其他"""
        self.llm_monitor.stop()
        if self.monitor_task:
            self.monitor_task.cancel()
            await self.monitor_task

        # ... 原有保存逻辑 ...
```

#### 3.2.5 BaseAgent 改造
**改动：**
- 添加 `runtime` 属性（在 AgentMatrix 初始化时注入）

**代码：**
```python
# agents/base.py

class BaseAgent:
    def __init__(self, ...):
        # ... 原有代码 ...
        self.runtime = None  # 将由 AgentMatrix 注入
```

#### 3.2.6 MicroAgent 改造
**改动：**
在 `_run_loop()` 中添加等待逻辑

**实现方案：**
```python
# agents/micro_agent.py

async def _run_loop(self, exit_actions=[]):
    """执行主循环 - 添加 LLM 服务等待逻辑"""
    start_time = time.time()
    # ... 原有初始化代码 ...

    while True:
        # ========== 新增：检查 LLM 服务状态 ==========
        if not self._is_llm_available():
            self.logger.warning(
                f"LLM service unavailable, '{self.run_label}' pausing..."
            )
            await self._wait_for_llm_recovery()
            self.logger.info(f"LLM service recovered, '{self.run_label}' resuming")

        # ... 原有循环逻辑 ...

def _is_llm_available(self) -> bool:
    """检查 LLM 服务是否可用"""
    # 通过 root_agent 访问 runtime
    if not hasattr(self.root_agent, 'runtime'):
        return True  # 向后兼容：如果没有 runtime，假设可用

    monitor = self.root_agent.runtime.llm_monitor
    return monitor.llm_available.is_set()

async def _wait_for_llm_recovery(self):
    """等待 LLM 服务恢复"""
    monitor = self.root_agent.runtime.llm_monitor
    check_interval = 5  # 每 5 秒检查一次

    while True:
        # 等待一段时间
        await asyncio.sleep(check_interval)

        # 检查是否恢复
        if monitor.llm_available.is_set():
            break

        self.logger.debug("Still waiting for LLM service recovery...")
```

**异常处理优化：**
除了定期检查，还可以在捕获到 LLM 异常时立即进入等待：

```python
async def _run_loop(self, exit_actions=[]):
    while True:
        try:
            # 检查服务状态
            if not self._is_llm_available():
                await self._wait_for_llm_recovery()

            # ... 原有循环逻辑 ...

        except LLMServiceUnavailableError as e:
            self.logger.warning(
                f"LLM service error detected: {str(e)}, entering wait mode..."
            )

            # 通知监控器立即检查（可选）
            monitor = self.root_agent.runtime.llm_monitor
            monitor.llm_available.clear()

            # 等待恢复
            await self._wait_for_llm_recovery()
```

---

## 四、实现步骤

### 步骤 1：创建异常定义
- 文件：`src/agentmatrix/core/exceptions.py`
- 内容：定义 `LLMServiceUnavailableError` 及子类

### 步骤 2：创建服务监控器
- 文件：`src/agentmatrix/core/service_monitor.py`
- 内容：实现 `LLMServiceMonitor` 类

### 步骤 3：改造 LLMClient
- 文件：`src/agentmatrix/backends/llm_client.py`
- 改动：
  - 导入新异常类
  - 在 `async_stream_think()` 和 `_async_stream_think_gemini()` 中捕获并转换异常
  - 修改 `think_with_retry()` 不捕获 `LLMServiceUnavailableError`

### 步骤 4：改造 AgentMatrix
- 文件：`src/agentmatrix/core/runtime.py`
- 改动：
  - 在 `__init__` 中创建 `LLMServiceMonitor`
  - 启动监控任务
  - 为 Agent 注入 `runtime` 引用
  - 在 `save_matrix()` 中停止监控

### 步骤 5：改造 BaseAgent
- 文件：`src/agentmatrix/agents/base.py`
- 改动：添加 `self.runtime = None` 初始化

### 步骤 6：改造 MicroAgent
- 文件：`src/agentmatrix/agents/micro_agent.py`
- 改动：
  - 添加 `_is_llm_available()` 方法
  - 添加 `_wait_for_llm_recovery()` 方法
  - 在 `_run_loop()` 中添加服务检查和等待逻辑
  - 添加异常捕获处理

---

## 五、关键细节

### 5.1 健康检查策略
**问题：** 如何准确判断服务是否可用？

**方案：**
1. **最小化请求：** 发送最简单的测试请求 `"hi"`，减少负担
2. **短超时：** 设置 10 秒超时，快速失败
3. **独立检查：** default_llm 和 default_slm 分别检查
4. **综合判断：**
   - 如果有任何一个服务可用，`llm_available` 保持 set
   - 如果所有服务都不可用，才 clear `llm_available`
   - 或者更严格：default_llm 必须可用（因为 brain 更关键）

**建议：** 采用严格策略，default_llm 不可用时即判定服务不可用

### 5.2 等待恢复机制
**MicroAgent 等待策略：**
1. **主动检查：** 在循环开始时检查 `llm_available`
2. **异常触发：** 捕获到 `LLMServiceUnavailableError` 后进入等待
3. **轮询检查：** 每 5 秒检查一次 `llm_available` 状态
4. **恢复继续：** 一旦恢复，从当前位置继续执行

**为什么不用 await event.wait()？**
- Event.wait() 会一直阻塞，无法打印日志
- 轮询方式可以提供更好的日志反馈
- 可以在等待期间执行其他逻辑（如超时检查）

### 5.3 多 Agent 并发等待
**场景：** 多个 MicroAgent 同时运行，LLM 服务故障

**行为：**
- 每个 Agent 都会独立检测到异常
- 每个 Agent 都会进入 `_wait_for_llm_recovery()`
- 所有 Agent 等待同一个 `llm_available` Event
- 服务恢复后，所有 Agent 同时恢复执行

**优势：**
- 无需通知机制，Event 自动广播
- 所有 Agent 同步恢复

### 5.4 向后兼容性
**保证：**
- 如果 `Agent.runtime` 不存在（旧代码），MicroAgent 假设服务可用
- 新增功能不破坏现有代码
- 逐步迁移

**实现：**
```python
def _is_llm_available(self) -> bool:
    if not hasattr(self.root_agent, 'runtime'):
        return True  # 向后兼容
    # ...
```

### 5.5 性能考虑
**健康检查开销：**
- 每分钟发送 2 个请求（default_llm + default_slm）
- 每个请求约 100 tokens，非常小
- 可以接受

**等待开销：**
- 轮询间隔 5 秒，不会频繁占用 CPU
- asyncio.sleep() 是非阻塞的

---

## 六、边界情况处理

### 6.1 启动时 LLM 不可用
**场景：** AgentMatrix 启动时，LLM 服务已经宕机

**处理：**
- `LLMServiceMonitor` 初始化时，`llm_available` 为 set（默认可用）
- 第一次健康检查失败后，会 clear Event
- Agent 在第一次调用时会检测到并等待

### 6.2 健康检查失败
**场景：** 健康检查自身出错（如网络波动）

**处理：**
- 捕获健康检查的异常，记录日志
- 不改变 `llm_available` 状态（保持当前状态）
- 下一次检查继续尝试

### 6.3 Agent 正在执行时服务故障
**场景：** Agent 正在执行一个长时间的 LLM 调用，服务突然故障

**处理：**
- LLMClient 会抛出 `LLMServiceUnavailableError`
- MicroAgent._run_loop() 会捕获异常
- 进入等待模式
- 服务恢复后，当前步骤会失败，但 Agent 会继续下一步

**优化：**
可以在等待前保存当前状态到 session，恢复后可以重试

### 6.4 部分服务故障
**场景：** default_llm 可用，但 default_slm 不可用

**处理：**
- Monitor 分别检查两个服务
- 可以提供更细粒度的状态：
  - `llm_monitor.is_available('default_llm')`
  - `llm_monitor.is_available('default_slm')`
- MicroAgent 可以根据使用的服务判断是否需要等待

---

## 七、测试建议

### 7.1 单元测试
1. **LLMServiceMonitor**
   - 模拟健康检查成功/失败
   - 测试 Event 的 set/clear 逻辑
   - 测试并发查询

2. **异常转换**
   - 测试各种底层异常是否正确转换
   - 测试异常信息是否保留

### 7.2 集成测试
1. **启动/停止流程**
   - 测试 AgentMatrix 完整启动
   - 测试优雅关闭

2. **服务故障模拟**
   - 手动停止 LLM 服务
   - 观察 Agent 是否正确等待
   - 恢复服务，观察 Agent 是否恢复

3. **多 Agent 场景**
   - 启动多个 Agent
   - 模拟服务故障
   - 观察所有 Agent 的行为

---

## 八、配置选项

### 8.1 可配置参数
```python
# 在 llm_config.json 中添加（可选）

{
  "default_llm": {...},
  "default_slm": {...},

  "service_monitor": {
    "enabled": true,              # 是否启用监控
    "check_interval": 60,         # 检查间隔（秒）
    "check_timeout": 10,          # 健康检查超时（秒）
    "wait_poll_interval": 5,      # Agent 等待轮询间隔（秒）
    "strict_mode": true           # 严格模式：default_llm 必须可用
  }
}
```

### 8.2 环境变量
```bash
# 禁用服务监控（用于调试）
AGENTMATRIX_DISABLE_MONITOR=true
```

---

## 九、后续优化

### 9.1 短期优化
1. **断路器模式：** 连续失败 N 次后，暂时停止检查一段时间


---

## 十、总结

### 优势
✅ **全局状态管理：** 单一 truth source（Event）
✅ **自动化：** Agent 无需手动处理，自动等待
✅ **可扩展：** 易于添加更多 LLM 服务监控
✅ **向后兼容：** 不破坏现有代码
✅ **低侵入性：** 改动点少，集中在关键路径

### 风险
⚠️ **健康检查开销：** 需要定期发送请求（但开销很小）
⚠️ **误判风险：** 网络抖动可能导致误判（可通过重试缓解）
⚠️ **等待时间：** 最坏情况下，Agent 可能等待一个检查周期（如 60 秒）

### 建议实施顺序
1. 先实现异常定义和 LLMClient 改造（基础）
2. 实现 LLMServiceMonitor（独立组件）
3. 改造 AgentMatrix 和 BaseAgent（集成）
4. 改造 MicroAgent（使用）
5. 添加配置和测试（完善）
