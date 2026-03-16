# How-To: Debug Agent

调试 Agent 的方法。

## 日志查看

Agent 日志位置：

```bash
# 实时查看日志
tail -f .matrix/logs/{agent_name}.log

# 查看所有日志
ls -la .matrix/logs/
```

## 常见问题

### Action 未注册

**现象**: LLM 调用 action 时报 "Action not found"

**检查**:
1. Skill 是否正确加载
2. @register_action 装饰器是否添加
3. 类名是否匹配文件名

### LLM 输出无法解析

**现象**: Cerebellum 反复重试

**检查**:
1. Action description 是否清晰
2. param_infos 是否完整
3. 查看日志中的 LLM 原始输出

### Session 状态异常

**现象**: Agent 不记得之前的对话

**检查**:
1. Session 文件是否存在：`.matrix/sessions/{agent}/{session}/`
2. Session ID 是否正确传递
3. history.json 是否有写入权限

## 调试技巧

### 1. 启用详细日志

修改 `main.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

### 2. 查看 System Prompt

在日志中搜索 "System Prompt" 查看发送给 LLM 的完整提示。

### 3. 手动测试 Action

创建测试脚本：

```python
import asyncio
from agentmatrix.agents.micro_agent import MicroAgent

async def test():
    agent = MicroAgent({...})
    result = await agent.my_action("test")
    print(result)

asyncio.run(test())
```

### 4. 检查 Working Context

在 Action 中打印上下文：

```python
async def my_action(self):
    self.logger.debug(f"Working context: {self.working_context._data}")
```

## 性能分析

### Action 耗时

查看日志中的时间戳：

```
[2026-03-15 10:00:01] Calling action: browser_navigate
[2026-03-15 10:00:05] Action completed in 4.2s
```

### LLM 延迟

在 LLM 配置中启用调试：

```json
{
  "default_llm": {
    "type": "openai",
    "model": "gpt-4",
    "debug": true
  }
}
```
