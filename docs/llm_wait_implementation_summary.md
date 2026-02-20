# LLM 服务等待机制 - 实现总结

## 实现完成 ✅

已成功实现 LLM 服务等待机制，所有文件都已创建或修改并通过语法检查。

---

## 改动文件清单

### 1. 新增文件（2个）

#### `src/agentmatrix/core/exceptions.py`
**内容：** 自定义异常类
- `LLMServiceUnavailableError` - LLM 服务不可用异常（基类）
- `LLMServiceTimeoutError` - 超时异常
- `LLMServiceConnectionError` - 连接异常
- `LLMServiceAPIError` - API 错误异常（带 status_code）

#### `src/agentmatrix/core/service_monitor.py`
**内容：** LLM 服务监控器
- `LLMServiceMonitor` 类
  - 定期健康检查（默认 60 秒）
  - 智能去重：如果 default_llm 和 default_slm 相同，只检查一次
  - 严格判断：两个服务都必须可用
  - 提供 `llm_available` Event 作为全局状态

---

### 2. 修改文件（5个）

#### `src/agentmatrix/backends/llm_client.py`
**改动：**
1. 导入自定义异常类
2. 修改所有 API 调用方法的异常处理：
   - `async_stream_think()` - OpenAI 格式
   - `_async_stream_think_gemini()` - Gemini 格式
   - `_think_with_image_openai()` - OpenAI Vision
   - `_think_with_image_openai_multi_turn()` - OpenAI Vision 多轮
   - `_think_with_image_gemini()` - Gemini Vision
   - `_think_with_image_gemini_multi_turn()` - Gemini Vision 多轮

3. 异常转换逻辑：
   - `aiohttp.ClientConnectorError` → `LLMServiceConnectionError`
   - `asyncio.TimeoutError` → `LLMServiceTimeoutError`
   - `aiohttp.ClientError` → `LLMServiceConnectionError`
   - HTTP 502/503/504 → `LLMServiceAPIError`

#### `src/agentmatrix/core/runtime.py`
**改动：**
1. 在 `_prepare_agents()` 中保存 loader 引用
2. 添加 `_start_llm_monitor()` 方法：
   - 创建 `LLMServiceMonitor` 实例
   - 启动监控任务
   - 为每个 Agent 注入 `runtime` 引用
3. 在 `__init__()` 中调用 `_start_llm_monitor()`
4. 在 `save_matrix()` 中先停止监控器

#### `src/agentmatrix/agents/base.py`
**改动：**
- 在 `__init__()` 中添加 `self.runtime = None`

#### `src/agentmatrix/agents/micro_agent.py`
**改动：**
1. 导入 `LLMServiceUnavailableError`
2. 修改 `_run_loop()` 方法：
   - 在主循环外层添加 `try-except LLMServiceUnavailableError`
   - 捕获异常后等待 3 秒，检查服务状态
   - 如果不可用，调用 `_wait_for_llm_recovery()` 等待恢复
   - 恢复后重试当前步骤
3. 添加 `_is_llm_available()` 方法：
   - 检查 `root_agent.runtime.llm_monitor.llm_available` 状态
   - 向后兼容：没有 runtime 时假设可用
4. 添加 `_wait_for_llm_recovery()` 方法：
   - 轮询方式（每 5 秒检查一次）
   - 每 30 秒打印一次日志
   - 服务恢复后自动退出

---

## 工作原理

### 正常运行流程
```
1. AgentMatrix 启动
   ↓
2. 创建 LLMServiceMonitor，开始定期检查（每 60 秒）
   ↓
3. 为每个 BaseAgent 注入 runtime 引用
   ↓
4. MicroAgent 正常执行，_run_loop 循环运行
```

### 服务故障处理流程
```
1. LLM 调用失败
   ↓
2. LLMClient 抛出 LLMServiceUnavailableError
   ↓
3. MicroAgent._run_loop 捕获异常
   ↓
4. 等待 3 秒（让 monitor 完成检查）
   ↓
5. 检查 monitor.llm_available 状态
   ├─ 如果已恢复 → 重试当前步骤
   └─ 如果仍不可用 → 进入等待模式
       ↓
6. _wait_for_llm_recovery()
   - 每 5 秒检查一次 llm_available
   - 每 30 秒打印日志
   ↓
7. 服务恢复，monitor 设置 llm_available.set()
   ↓
8. MicroAgent 检测到恢复，重试当前步骤
```

---

## 关键特性

### 1. 异常触发检查（按需处理）
- ✅ 不在 loop 开头主动检查（避免 99% 正常情况的开销）
- ✅ 只在发生异常时才处理
- ✅ 符合"懒惰检查"原则

### 2. 智能去重检查
- ✅ 检查 default_llm 和 default_slm 配置
- ✅ 如果 URL 和 model_name 相同，只检查一次
- ✅ 节省资源和时间

### 3. 严格判断
- ✅ brain (default_llm) 和 cerebellum (default_slm) 都必须可用
- ✅ 只要有一个不可用，全局服务就不可用
- ✅ 确保所有 Agent 功能正常

### 4. 全局状态同步
- ✅ 单一 truth source（llm_available Event）
- ✅ 所有 Agent 共享同一个状态
- ✅ 服务恢复后自动唤醒所有等待的 Agent

### 5. 向后兼容
- ✅ 如果没有 runtime 引用，假设服务可用
- ✅ 不破坏现有代码
- ✅ 可逐步迁移

---

## 配置选项

当前使用默认配置（硬编码）：
- 检查间隔：60 秒
- 健康检查超时：10 秒
- Agent 等待轮询间隔：5 秒

**未来可扩展：** 在 `llm_config.json` 中添加配置项（详见设计文档）

---

## 日志输出示例

### 正常启动
```
>>> 启动 LLM 服务监控...
✓ default_llm and default_slm point to the same service, will check once
>>> LLM service monitor started (interval: 60s)
```

### 服务故障
```
⚠️  LLM service error in step 5: Failed to connect to LLM service
Waiting for monitor to update service status...
⚠️  Service still unavailable, entering wait mode...
⏳ Waiting for LLM service recovery...
⏳ Still waiting for LLM service... (30s elapsed)
```

### 服务恢复
```
✅ LLM service recovered after 45s
✅ Service recovered after wait, retrying current step
Step 5/50
```

### Monitor 日志
```
⚠️  LLM service unavailable! Status: {'default_llm': False}
✅ All LLM services recovered! Status: {'default_llm': True}
```

---

## 测试建议

### 1. 单元测试（手动）
```python
# 测试异常转换
from agentmatrix.core.exceptions import LLMServiceConnectionError
# 故意使用错误的 URL，看是否抛出正确的异常

# 测试监控器
monitor = LLMServiceMonitor(llm_config, check_interval=10)
# 观察健康检查日志
```

### 2. 集成测试
**场景 1：启动时服务正常**
1. 正常启动 AgentMatrix
2. 观察 Monitor 是否正常工作
3. 执行 Agent 任务

**场景 2：运行时服务故障**
1. 启动 AgentMatrix
2. 运行一个长时间任务
3. 在任务执行期间，手动停止 LLM 服务（或修改 URL）
4. 观察 Agent 是否进入等待模式
5. 恢复服务，观察 Agent 是否自动恢复

**场景 3：启动时服务故障**
1. 先停止 LLM 服务
2. 启动 AgentMatrix
3. 观察 Agent 在第一次调用时的行为
4. 恢复服务，观察是否恢复

### 3. 多 Agent 测试
1. 启动多个 Agent
2. 模拟服务故障
3. 观察所有 Agent 是否都进入等待
4. 恢复服务，观察是否都同时恢复

---

## 潜在问题和解决方案

### 问题 1：网络抖动导致误判
**解决：** Monitor 已经实现"保持当前状态"策略，单次检查失败不会立即改变状态

### 问题 2：健康检查本身失败
**解决：** 捕获健康检查的异常，记录日志但不改变状态

### 问题 3：Agent 在等待期间超时
**影响：** 如果设置了 max_time，等待时间会占用总时间
**建议：** 可以在未来优化，暂停计时器或在恢复后补偿时间

### 问题 4：服务恢复后，当前步骤可能已经失败
**现状：** 会重试当前步骤
**优化：** 可以在未来添加状态保存，从失败的 action 恢复

---

## 后续优化方向

### 短期
1. 添加配置文件支持（llm_config.json）
2. 添加断路器模式（连续失败 N 次后暂停检查）
3. 添加监控指标（成功率、平均恢复时间等）

### 长期
1. 添加降级策略（primary → backup）
2. 添加本地模型作为降级方案
3. 添加 Web 监控面板
4. 添加告警通知（邮件、Webhook）

---

## 文档链接

- 设计方案：`docs/llm_service_wait_mechanism.md`
- 需求文档：`docs/new_requirement.md`

---

## 实现日期
2025-02-15

## 实现者
Claude Code (Sonnet 4.5)
