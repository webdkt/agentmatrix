# 前端轮询问题分析与解决方案

## 问题发现

前端仍在轮询 Agent 状态历史：
```
XHRGET http://localhost:8000/api/agents/Mark/status/history
[HTTP/1.1 200 OK 1ms]
```

每 2 秒一次，造成不必要的网络请求。

---

## 当前架构分析

### 旧机制：HTTP 轮询

**位置**: `web/js/app.js` (lines 552-575)

```javascript
startAgentStatusPolling(agentName) {
    this.agentStatusPolling = true;
    this.agentStatusTarget = agentName;

    // 立即获取一次状态
    this.fetchAgentStatus();

    // 每 2 秒轮询一次
    this.pollingInterval = setInterval(() => {
        this.fetchAgentStatus();
    }, 2000);
}
```

**API 端点**: `/api/agents/{agent_name}/status/history`

**返回数据**: Agent 状态历史（最近 3 条状态消息）
```json
[
  {
    "message": "正在搜索文件...",
    "timestamp": "2026-03-15T20:44:00"
  },
  {
    "message": "正在分析代码...",
    "timestamp": "2026-03-15T20:44:02"
  }
]
```

### 新机制：WebSocket 广播

**位置**: `src/agentmatrix/core/system_status_collector.py`

```python
def collect_status(self) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(),
        "agents": self._collect_agent_status()
    }
```

**广播数据**: 实时系统状态（每 2 秒）
```json
{
    "timestamp": "2026-03-15T20:44:00",
    "agents": {
        "Mark": {
            "status": "THINKING",
            "pending_question": null,
            "current_session_id": "...",
            "current_task_id": "...",
            "current_user_session_id": null
        }
    }
}
```

---

## 两个机制的对比

| 特性 | HTTP 轮询 | WebSocket 广播 |
|------|----------|---------------|
| **数据内容** | 状态历史（最近 3 条消息） | 实时状态（status 字段） |
| **更新频率** | 每 2 秒 | 每 2 秒 |
| **网络开销** | N 个客户端 × 2 秒 = N 个请求 | 1 个广播消息 |
| **实时性** | 有延迟（轮询间隔） | 实时推送 |
| **扩展性** | 差（客户端增加 = 负载增加） | 好（广播机制） |

---

## 解决方案

### 方案 A：移除轮询（推荐）✅

**优点**:
- 简化代码
- 减少网络请求
- 统一使用 WebSocket

**缺点**:
- 会失去状态历史 UI 组件
- 需要确认功能是否必需

**实施步骤**:
1. 移除 `startAgentStatusPolling()` 和相关代码
2. 移除状态历史 UI 组件（index.html lines 430-445）
3. 使用 WebSocket 的 `status` 字段显示状态

**代码修改**:
```javascript
// ❌ 删除
startAgentStatusPolling(agentName) { ... }
stopAgentStatusPolling() { ... }
fetchAgentStatus() { ... }

// ✅ 使用 WebSocket 数据
// 在 uiStore.js 中
systemStatus.agents[agentName].status  // "THINKING", "WORKING", etc.
```

---

### 方案 B：通过 WebSocket 广播状态历史

**优点**:
- 保留状态历史功能
- 移除轮询，使用 WebSocket

**缺点**:
- 需要修改后端广播内容
- 增加数据传输量

**实施步骤**:
1. 修改 `SystemStatusCollector` 收集状态历史
2. 在 WebSocket 广播中包含状态历史
3. 前端从 WebSocket 接收状态历史
4. 移除轮询代码

**代码修改**:

**后端** (`system_status_collector.py`):
```python
def _collect_agent_status(self) -> Dict[str, Dict]:
    agents = {}
    for name, agent in self.matrix_runtime.agents.items():
        agent_info = {
            "status": agent.status,
            "pending_question": None,
            "current_session_id": None,
            "current_task_id": None,
            "current_user_session_id": None,
            "status_history": []  # 🆕 添加状态历史
        }

        # 添加状态历史
        if hasattr(agent, 'get_status_history'):
            agent_info["status_history"] = agent.get_status_history()

        # ... 其他字段 ...

    return agents
```

**前端** (`uiStore.js`):
```javascript
handleSystemStatus(payload) {
    const status = payload.status;
    this.systemStatus = {
        timestamp: status.timestamp,
        agents: status.agents || {}
    };

    // 更新状态历史
    for (const [agentName, agentInfo] of Object.entries(status.agents)) {
        if (agentName === this.agentStatusTarget) {
            this.agentStatusHistory = agentInfo.status_history || [];
        }
    }

    this.checkForWaitingUser();
}
```

---

### 方案 C：减少轮询频率（临时方案）

**优点**:
- 最小化代码改动
- 保留状态历史功能

**缺点**:
- 仍然有轮询开销
- 不是最佳解决方案

**实施步骤**:
1. 将轮询间隔从 2 秒改为 5 秒
2. 只在必要时启动轮询

**代码修改**:
```javascript
// 从每 2 秒改为每 5 秒
this.pollingInterval = setInterval(() => {
    this.fetchAgentStatus();
}, 5000);  // 2000 → 5000
```

---

## 前端 UI 组件分析

**位置**: `web/index.html` (lines 420-445)

**功能**:
1. 显示 Agent 正在工作的动画（脉冲圆点）
2. 显示状态历史消息列表（最近 3 条）
3. 显示最新状态的时间戳

**示例**:
```
● Mark 正在工作...
  2026-03-15 20:44:00

  ● 正在搜索文件...
  ● 正在分析代码...
  ● 正在生成报告...
```

**评估**: 这是一个 nice-to-have 功能，但不是核心功能。

---

## 推荐方案

### 🎯 方案 A：移除轮询（推荐）

**理由**:
1. **简化架构**: 统一使用 WebSocket，移除轮询
2. **减少开销**: 消除不必要的网络请求
3. **实时性更好**: WebSocket 实时推送 vs 轮询延迟
4. **状态历史非必需**: 核心功能是显示 Agent 当前状态，而不是历史

**替代方案**:
- 使用 WebSocket 的 `status` 字段显示当前状态
- 如果需要历史记录，可以从会话历史中推断

---

## 修改文件清单

### 方案 A（推荐）

1. ✅ `web/js/app.js`
   - 移除 `fetchAgentStatus()` 方法
   - 移除 `startAgentStatusPolling()` 方法
   - 移除 `stopAgentStatusPolling()` 方法
   - 移除 `checkLastEmailChanged()` 方法
   - 移除相关调用代码

2. ✅ `web/index.html`
   - 移除状态历史 UI 组件（lines 420-445）
   - 或者简化为只显示当前状态

### 方案 B（保留功能）

1. ✅ `src/agentmatrix/core/system_status_collector.py`
   - 添加 `status_history` 字段到 `agent_info`

2. ✅ `web/js/stores/uiStore.js`
   - 在 `handleSystemStatus()` 中更新 `agentStatusHistory`

3. ✅ `web/js/app.js`
   - 移除轮询代码
   - 从 WebSocket 接收状态历史

---

## 下一步

请选择要实施的方案：

- [ ] **方案 A**: 移除轮询和状态历史（推荐）
- [ ] **方案 B**: 通过 WebSocket 广播状态历史
- [ ] **方案 C**: 减少轮询频率（临时）

或者提出其他建议！

---

## 总结

| 方案 | 复杂度 | 功能完整性 | 性能 | 推荐度 |
|------|-------|----------|------|-------|
| 方案 A | 低 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 方案 B | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 方案 C | 低 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |

**我推荐方案 A**，因为：
1. 状态历史不是核心功能
2. WebSocket 已经提供了实时状态
3. 简化代码，减少网络开销
