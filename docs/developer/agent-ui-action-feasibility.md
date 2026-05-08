# Agent UI Action 架构可行性分析

## 需求概述

1. **Agent 暴露功能接口**：不同 Agent class（BaseAgent、BrowserCollabAgent、未来其他）能对外暴露可调用的方法（如查看 system prompt）。
2. **前端工具条按钮**：AgentSessionPanel 底部输入框肩膀上的工具条，动态显示当前 Agent 暴露的按钮，点击调用后端对应方法。
3. **结果返回机制**：执行结果通过现有 session event 信号推送到前端，前端通过已有的 event classification + handler 机制渲染。

---

## 现有架构调研

### 后端 Agent 类

```
BasicAgent
  └── BaseAgent (desktop)
        └── BrowserCollabAgent
```

- **BaseAgent** 已有 `action_registry` / `actions_meta`，通过 `_scan_all_actions()` 扫描 `@register_action` 装饰的方法。但这些 action 是**给 LLM 自调用**的（SLM 解析后让 Agent 自己执行）。
- **BaseAgent** 已有 `_log_session_event()`：异步写入 DB + WebSocket 广播 `SESSION_EVENT`。
- **BaseAgent** 已有 `_broadcast_message_callback`：实时推送消息到所有 WebSocket 客户端。
- **FastAPI** (`server/app.py`) 已有大量 `/api/agents/{agent_name}/...` 端点。

### 前端架构

- **AgentSessionPanel** 有两个工具条区域：
  - `agent-session-panel__toolbar`（顶部 top bar）：Collab toggle、Refresh
  - `agent-session-panel__floating-toolbar`（输入框肩膀）：CollabFile、Task Files、Terminal
- **agentAPI** (`src/api/agent.js`)：封装所有 Agent REST 调用。
- **WebSocket Store**：处理 WebSocket 消息，有 `registerListener(eventType, callback)` 机制。
- **useChatTimeline**：通过 `classifyEvent()` 将 `SESSION_EVENT` 映射为 `renderType`（bubble-user、bubble-agent、thought、pill、system 等），`ChatMessage.vue` 按 `renderType` 渲染。

### 事件流

```
后端 Agent._log_session_event()
  → DB 写入
  → WebSocket broadcast_message_to_clients()
    → 前端 WebSocket Store.handle_message()
      → handleSessionEvent()
        → sessionStore.setLastSessionEvent()
          → useChatTimeline watch(lastSessionEvent)
            → parseEvent() + classifyEvent()
              → events.value.push()
                → ChatMessage 渲染
```

---

## 可行性结论：✅ 完全可行

现有架构与需求高度兼容，不需要引入新的通信机制或大的结构改动。

| 需求 | 复用/扩展点 | 工作量 |
|------|-----------|--------|
| Agent 暴露接口 | 扩展 `@register_action` 或新增 `@ui_action` 装饰器；复用 `_scan_all_actions()` 扫描机制 | 低 |
| 工具条动态按钮 | 扩展现有 `floating-toolbar` 或 `toolbar`；新增 2 个 API 端点 | 低 |
| 结果推送 | **完全复用** `SESSION_EVENT` + `useChatTimeline` 事件流 | 极低 |

---

## 推荐架构设计

### 1. 后端：新增 `@ui_action` 装饰器

新建 `src/agentmatrix/core/ui_actions.py`：

```python
from dataclasses import dataclass
from typing import Callable, Optional, Any

@dataclass
class UIActionMeta:
    name: str           # 唯一标识（如 "view_prompt"）
    label: str          # 按钮文字（如 "System Prompt"）
    icon: Optional[str] = None      # 图标名（前端 MIcon 用）
    tooltip: Optional[str] = None   # hover 提示
    requires_idle: bool = False     # 是否要求 Agent IDLE 才可点击
    display_mode: str = "text"      # 结果展示模式：text | markdown | json | toast | modal
    handler: Callable = None

def ui_action(name: str, label: str, icon: str = None, tooltip: str = None,
              requires_idle: bool = False, display_mode: str = "text"):
    """标记一个方法为 UI 可调用 action。

    示例：
        class MyAgent(BaseAgent):
            @ui_action(name="view_prompt", label="System Prompt",
                       icon="file-text", display_mode="modal")
            async def view_system_prompt(self):
                return self.last_system_prompt or "N/A"
    """
    def decorator(func):
        func._is_ui_action = True
        func._ui_action_meta = UIActionMeta(
            name=name, label=label, icon=icon, tooltip=tooltip,
            requires_idle=requires_idle, display_mode=display_mode,
            handler=func
        )
        return func
    return decorator
```

### 2. 后端：BaseAgent 扫描 UI Actions

在 `BaseAgent.__init__()` 中增加：

```python
self.ui_actions: Dict[str, UIActionMeta] = {}
self._scan_ui_actions()

def _scan_ui_actions(self):
    """扫描当前类及 MRO 上所有标记为 UI action 的方法。"""
    for cls in type(self).__mro__:
        for name, method in cls.__dict__.items():
            if not hasattr(method, '_is_ui_action'):
                continue
            meta = method._ui_action_meta
            # 绑定实例方法
            bound = method.__get__(self, type(self))
            self.ui_actions[meta.name] = UIActionMeta(
                name=meta.name,
                label=meta.label,
                icon=meta.icon,
                tooltip=meta.tooltip,
                requires_idle=meta.requires_idle,
                display_mode=meta.display_mode,
                handler=bound,
            )

def get_ui_actions(self) -> list:
    """返回前端渲染所需的 UI action 元数据列表。"""
    return [
        {
            "name": a.name,
            "label": a.label,
            "icon": a.icon,
            "tooltip": a.tooltip,
            "requires_idle": a.requires_idle,
            "display_mode": a.display_mode,
            "available": not a.requires_idle or self._status == AgentStatus.IDLE,
        }
        for a in self.ui_actions.values()
    ]

async def execute_ui_action(self, action_name: str, payload: dict = None) -> Any:
    """执行 UI action，并将结果记录为 session event。"""
    action = self.ui_actions.get(action_name)
    if not action:
        raise ValueError(f"UI action '{action_name}' not found")

    if action.requires_idle and self._status != AgentStatus.IDLE:
        raise RuntimeError(f"Action '{action_name}' requires IDLE status")

    # 执行（支持 sync / async handler）
    result = action.handler(**(payload or {}))
    if asyncio.iscoroutine(result):
        result = await result

    # 序列化结果（只保留可 JSON 序列化的类型）
    serializable_result = result if isinstance(result, (str, int, float, bool, list, dict, type(None))) else str(result)

    # 记录 session event（推送到前端）
    session_id = self.current_session.get("session_id") if self.current_session else None
    if session_id:
        await self._log_session_event(
            session_id,
            "ui_action",
            action_name,
            {
                "result": serializable_result,
                "display_mode": action.display_mode,
                "payload": payload,
            }
        )

    return {"result": serializable_result, "display_mode": action.display_mode}
```

### 3. 后端：新增 2 个 FastAPI 端点

在 `server/app.py` 中增加：

```python
@app.get("/api/agents/{agent_name}/ui_actions")
async def get_agent_ui_actions(agent_name: str):
    """获取 Agent 暴露的 UI action 列表（用于前端渲染工具条）。"""
    global matrix_runtime
    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    agent = matrix_runtime.agents.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"actions": agent.get_ui_actions()}


class InvokeUIActionRequest(BaseModel):
    payload: Optional[dict] = None

@app.post("/api/agents/{agent_name}/ui_actions/{action_name}")
async def invoke_agent_ui_action(agent_name: str, action_name: str, request: InvokeUIActionRequest):
    """调用 Agent 的 UI action。"""
    global matrix_runtime
    if not matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    agent = matrix_runtime.agents.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        result = await agent.execute_ui_action(action_name, request.payload or {})
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))  # 409 Conflict = 状态不满足
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 4. 前端：API 封装

在 `agentmatrix-desktop/src/api/agent.js` 中增加：

```javascript
export const agentAPI = {
  // ... existing methods ...

  /**
   * 获取 Agent 暴露的 UI actions
   */
  async getAgentUIActions(agentName) {
    return API.get(`/api/agents/${agentName}/ui_actions`)
  },

  /**
   * 调用 Agent 的 UI action
   */
  async invokeAgentUIAction(agentName, actionName, payload = {}) {
    return API.post(`/api/agents/${agentName}/ui_actions/${actionName}`, { payload })
  },
}
```

### 5. 前端：工具条动态渲染

在 `AgentSessionPanel.vue` 中：

```vue
<script setup>
// ... existing imports ...

const agentUIActions = ref([])

// 加载当前 Agent 的 UI actions
const loadAgentUIActions = async () => {
  if (!currentAgentName.value) {
    agentUIActions.value = []
    return
  }
  try {
    const result = await agentAPI.getAgentUIActions(currentAgentName.value)
    agentUIActions.value = result.actions || []
  } catch (e) {
    console.error('Failed to load UI actions:', e)
    agentUIActions.value = []
  }
}

// 切换 session 时重新加载
watch(currentAgentName, () => {
  loadAgentUIActions()
}, { immediate: true })

// 调用 UI action
const invokeUIAction = async (actionName) => {
  try {
    await agentAPI.invokeAgentUIAction(currentAgentName.value, actionName)
    // 成功 —— 结果会通过 SESSION_EVENT 推送到前端，无需额外处理
  } catch (e) {
    console.error('UI action failed:', e)
    // 可以显示一个 toast 错误提示
  }
}
</script>

<template>
  <!-- ... existing template ... -->

  <!-- Top Bar Toolbar（或 Floating Toolbar）中增加动态按钮 -->
  <div class="agent-session-panel__toolbar">
    <!-- 现有按钮：Collab, Refresh -->
    
    <!-- 动态 UI action 按钮 -->
    <button
      v-for="action in agentUIActions"
      :key="action.name"
      class="agent-session-panel__toolbar-btn"
      :class="{ 'agent-session-panel__toolbar-btn--disabled': !action.available }"
      :disabled="!action.available"
      :title="action.tooltip || action.label"
      @click="invokeUIAction(action.name)"
    >
      <MIcon :name="action.icon || 'zap'" />
      <span class="agent-session-panel__toolbar-btn-text">{{ action.label }}</span>
    </button>
  </div>
</template>
```

### 6. 前端：Event Classification + 渲染

在 `useChatTimeline.js` 的 `classifyEvent()` 中增加：

```javascript
function classifyEvent(type, name, detail) {
  if (type === 'email') { /* ... */ }
  if (type === 'think') return 'thought'
  if (type === 'action') { /* ... */ }
  
  // ✅ 新增：UI action 执行结果
  if (type === 'ui_action') {
    const mode = detail.display_mode
    if (mode === 'modal') return 'ui-action-modal'
    if (mode === 'toast') return 'ui-action-toast'
    return 'ui-action-text'  // 默认在 timeline 中显示为文本卡片
  }
  
  if (type === 'session') { /* ... */ }
  return 'system'
}
```

在 `ChatMessage.vue` 中增加对应 `renderType` 的渲染模板（以 `ui-action-text` 为例）：

```vue
<template v-else-if="message.type === 'ui-action-text'">
  <div class="chat-ui-action">
    <div class="chat-ui-action__header">
      <MIcon name="zap" />
      <span>{{ message.data.eventName }}</span>
    </div>
    <div class="chat-ui-action__body">
      <pre v-if="message.data.detail?.display_mode === 'json'">{{ JSON.stringify(message.data.detail?.result, null, 2) }}</pre>
      <div v-else-if="message.data.detail?.display_mode === 'markdown'" v-html="renderMarkdown(message.data.detail?.result)"></div>
      <div v-else>{{ message.data.detail?.result }}</div>
    </div>
  </div>
</template>
```

---

## 使用示例

### BaseAgent 定义通用 UI Action

```python
from agentmatrix.core.ui_actions import ui_action

class BaseAgent(BasicAgent):
    @ui_action(name="view_prompt", label="System Prompt",
               icon="file-text", display_mode="modal")
    async def view_system_prompt(self):
        """查看当前 system prompt（用于调试）。"""
        return self.last_system_prompt or "No system prompt available."
```

### BrowserCollabAgent 定义特有 UI Action

```python
class BrowserCollabAgent(BaseAgent):
    @ui_action(name="reload_site_knowledge", label="Reload SK",
               icon="refresh-cw", tooltip="重新加载站点知识",
               requires_idle=True, display_mode="toast")
    async def reload_site_knowledge(self):
        """重新加载当前站点的 knowledge。"""
        # ... 实现 ...
        return {"status": "ok", "site": self._current_site_url}
```

---

## 未决问题 / 需要用户决策

1. **按钮位置**：放在 top bar toolbar（与 Collab/Refresh 同排）还是 floating toolbar（输入框肩膀）？
   - Top bar：空间更大，适合显示 label + icon
   - Floating toolbar：更紧凑，icon-only 更合适

2. **结果展示方式**：`display_mode` 的枚举值需要确定。建议：
   - `text`：在 timeline 中显示为普通文本卡片
   - `markdown`：渲染为格式化 markdown
   - `json`：代码块展示
   - `modal`：弹出对话框（如查看完整的 system prompt）
   - `toast`：右上角临时提示（适合轻量操作确认）

3. **Action 参数**：当前设计假设 UI action 不需要额外参数（一键执行）。如果未来需要参数输入（如 "搜索关键词"），需要额外的表单/对话框机制。建议第一期只做无参 action。

4. **按钮加载时机**：每次切换 session 时重新拉取 `ui_actions` 列表，还是 Agent store 中缓存？推荐每次切换 session 时拉取（因为 Agent 状态变化可能影响 `available`）。

---

## 工作量预估

| 模块 | 内容 | 预估时间 |
|------|------|---------|
| 后端装饰器 + BaseAgent 扫描 | `ui_actions.py` + `_scan_ui_actions()` + `execute_ui_action()` | 2h |
| 后端 API 端点 | 2 个 FastAPI 路由 | 1h |
| 前端 API 封装 | `agentAPI.getAgentUIActions()` + `invokeAgentUIAction()` | 30min |
| 前端工具条渲染 | AgentSessionPanel 动态按钮 + 样式 | 1.5h |
| 前端 Event 处理 | `classifyEvent()` + `ChatMessage.vue` 新 renderType | 1.5h |
| 调试联调 | end-to-end 测试 | 1h |
| **总计** | | **~7-8h（1天）** |

---

## 风险与缓解

| 风险 | 可能性 | 缓解措施 |
|------|--------|---------|
| MRO 扫描重复/遗漏 UI action | 低 | 用 `name` 作为 key 去重，子类覆盖父类同名 action |
| Agent 在 action 执行期间状态变化 | 低 | `execute_ui_action` 是 async 的，执行前 snapshot 状态检查 |
| 结果过大导致 WebSocket 消息过大 | 低 | 对 result 做截断（如 > 50KB 返回截断提示 + 下载链接） |
| 前端按钮闪烁（切换 session 时） | 中 | 加 loading 状态或骨架屏 | 
