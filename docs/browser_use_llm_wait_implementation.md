# BrowserUseSkill browser-use-llm 服务等待机制 - 实现完成

## ✅ 实现完成

已成功为 BrowserUseSkill 添加 browser-use-llm 服务检查和等待机制。

---

## 修改内容

### 修改的文件（1个）

**`src/agentmatrix/skills/browser_use_skill.py`**

#### 1. 添加导入（line 21）
```python
from ..core.exceptions import LLMServiceUnavailableError
```

#### 2. 添加服务检查方法（line 342-386）
```python
async def _check_browser_llm_available(self) -> bool:
    """
    检查 browser-use-llm 服务是否可用

    - 发送最小的测试请求 "hi"
    - 超时时间 10 秒
    - 支持 browser-use-llm 和 deepseek-chat 两种配置
    - 返回 bool
    """
```

#### 3. 添加服务等待方法（line 388-408）
```python
async def _wait_for_browser_llm_recovery(self):
    """
    等待 browser-use-llm 服务恢复（轮询方式）

    - 每 5 秒检查一次
    - 每 30 秒打印日志
    - 服务恢复后自动退出
    """
```

#### 4. 修改 `use_browser()` 添加异常处理（line 763-815）
**关键改动：**
- 添加重试循环（最多 3 次）
- 捕获 `LLMServiceUnavailableError`
- 检查服务状态并等待恢复
- 重新执行任务

**处理流程：**
```python
while retry_count < 3:
    try:
        agent = await self._get_or_create_agent(full_task, headless)
        history = await agent.run()  # ← 关键调用
        break  # 成功，退出循环
    except LLMServiceUnavailableError as e:
        # 检查服务状态
        if await self._check_browser_llm_available():
            continue  # 已恢复，重试
        # 等待恢复
        await self._wait_for_browser_llm_recovery()
        continue  # 恢复后重试
    except Exception as e:
        # 其他异常，直接返回错误
        return f"任务执行失败: {error_msg}"
```

#### 5. 修改 `_create_new_agent()` 添加异常处理（line 555-596）
**改动：**
- 在调用 `_get_browser_use_llm()` 时添加重试机制
- 处理 `LLMServiceUnavailableError`
- 等待服务恢复后继续创建 Agent

---

## 工作原理

### 服务检查机制

1. **健康检查**
   - 发送最简单的测试请求：`{"role": "user", "content": "hi"}`
   - 设置 10 秒超时
   - 快速失败，避免长时间等待

2. **配置回退**
   - 优先使用 `browser-use-llm` 配置
   - 如果不存在，回退到 `deepseek-chat`
   - 自动适配，无需手动配置

### 异常处理流程

```
1. 调用 browser-use
   ↓
2. 捕获 LLMServiceUnavailableError
   ↓
3. 等待 3 秒（让服务稳定）
   ↓
4. 检查服务状态
   ├─ 已恢复 → 重试当前任务
   └─ 仍不可用 → 进入等待模式
       ↓
5. _wait_for_browser_llm_recovery()
   - 每 5 秒检查一次
   - 每 30 秒打印日志
   ↓
6. 服务恢复，重新执行任务
```

---

## 特点

### 1. 独立性
- ✅ 不影响全局状态（default_llm, default_slm）
- ✅ browser-use-llm 可以单独 down
- ✅ 只有 BrowserUseSkill 等待

### 2. 自动恢复
- ✅ 自动检测服务恢复
- ✅ 自动重试任务
- ✅ 最多重试 3 次

### 3. 用户友好
- ✅ 清晰的日志输出
- ✅ 实时显示等待状态
- ✅ 错误信息明确

---

## 控制台输出示例

### 正常运行
```
BrowserUseSkill 开始任务
  任务: 访问百度并搜索 Python
✅ 复用现有 Agent，更新任务：访问百度并搜索 Python...
BrowserUseSkill 任务完成
```

### 服务故障时
```
BrowserUseSkill 开始任务
  任务: 访问百度并搜索 Python
⚠️  browser-use-llm 服务错误 (尝试 1/3): Failed to connect...
🔄 browser-use-llm 不可用，进入等待模式...
⏳ Waiting for browser-use-llm recovery...
⏳ Still waiting for browser-use-llm... (30s elapsed)
✅ browser-use-llm recovered after 45s
✅ browser-use-llm 已恢复，重新执行任务
BrowserUseSkill 任务完成
```

### 服务持续不可用
```
⚠️  browser-use-llm 服务错误 (尝试 1/3): Failed to connect...
🔄 browser-use-llm 不可用，进入等待模式...
⏳ Waiting for browser-use-llm recovery...
⏳ Still waiting for browser-use-llm... (30s elapsed)
⏳ Still waiting for browser-use-llm... (60s elapsed)
⚠️  browser-use-llm 服务错误 (尝试 2/3): Failed to connect...
🔄 browser-use-llm 不可用，进入等待模式...
⏳ Waiting for browser-use-llm recovery...
⚠️  browser-use-llm 服务错误 (尝试 3/3): Failed to connect...
❌ browser-use-llm 服务不可用，已重试 3 次仍失败
任务执行失败: browser-use-llm 服务不可用，已重试 3 次仍失败
```

---

## 测试建议

### 测试服务恢复
1. 确保 llm_config.json 中配置了 `browser-use-llm`
2. 启动 server.py
3. 发送一个 browser_use 任务
4. 在任务执行期间，修改 llm_config.json 中的 browser-use-llm URL 为无效地址
5. 观察 BrowserUseSkill 进入等待模式
6. 恢复正确的 URL
7. 观察自动恢复并继续执行任务

### 测试配置回退
1. 删除 llm_config.json 中的 `browser-use-llm` 配置
2. 确保有 `deepseek-chat` 配置
3. 发送 browser_use 任务
4. 验证自动回退到 deepseek-chat
5. 验证服务检查也使用 deepseek-chat

---

## 日志位置

所有日志会记录到：
- `MatrixWorld/.matrix/logs/` - Agent 日志文件
- 控制台 - 重要事件（使用 echo 方法）

---

## 与全局 LLM Monitor 的区别

| 特性 | 全局 Monitor | BrowserUseSkill 检查 |
|------|-------------|---------------------|
| 监控的服务 | default_llm, default_slm | browser-use-llm (deepseek-chat) |
| 影响范围 | 所有 Agent | 只有 BrowserUseSkill |
| 故障影响 | 整个 Matrix 暂停 | 只有浏览器任务暂停 |
| 检查频率 | 定期（60秒） | 按需（任务执行时） |
| 是否必须 | 必须 | 可选（可降级） |

---

## 配置要求

### llm_config.json
```json
{
  "default_llm": {...},
  "default_slm": {...},

  "browser-use-llm": {
    "url": "https://open.bigmodel.cn/api/paas/v4/",
    "API_KEY": "ZHIPU_API_KEY",
    "model_name": "glm-4.6"
  },

  "deepseek-chat": {  // 可选，作为回退
    "url": "https://api.deepseek.com/v1",
    "API_KEY": "DEEPSEEK_API_KEY",
    "model_name": "deepseek-chat"
  }
}
```

---

## 实现日期
2025-02-15
