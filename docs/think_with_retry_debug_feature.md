# think_with_retry debug 参数功能说明

## 概述

为 `LLMClient.think_with_retry()` 方法添加了 `debug` 参数，用于在需要时输出详细的调试信息，包括对 LLM 的输入和返回。

## 修改内容

### 文件
- `src/agentmatrix/backends/llm_client.py`

### 方法签名
```python
async def think_with_retry(
    self,
    initial_messages: Union[str, List[str]],
    parser: callable,
    max_retries: int = 3,
    debug: bool = False,  # 新增参数
    **parser_kwargs
) -> any
```

## 功能说明

### debug=False（默认）
简洁的日志输出，只显示关键步骤：
- 初始 messages（简洁格式）
- 每次尝试的序号
- 成功或失败的最终结果

**适用场景：**
- 生产环境
- 不需要详细调试信息的场景
- 减少日志输出量

### debug=True
详细的调试输出，包括：

1. **初始信息**
   - `=== think_with_retry DEBUG START ===`
   - 所有初始 messages 的内容（每个 message 前 200 字符）

2. **每次尝试**
   - `=== Attempt X/Y ===`
   - 输入给 LLM 的所有 messages（每个 message 前 300 字符）
   - LLM 的原始返回（前 500 字符 + 总长度）
   - Parser 的解析结果：
     - status (success/error)
     - feedback (如果出错)
     - content (如果成功，显示结构或前 200 字符)

3. **错误处理**
   - 如果 parser 返回 error，显示 feedback 和重试信息
   - Assistant response（前 200 字符）
   - User feedback（前 200 字符）

4. **最终结果**
   - `=== think_with_retry SUCCESS ===` 或
   - `=== think_with_retry FAILED after X attempts ===`

**适用场景：**
- 开发和调试
- LLM 返回不符合预期
- Parser 解析失败需要排查
- 需要查看完整的交互过程

## 使用示例

### 基本使用（不启用 debug）
```python
client = LLMClient(url="...", api_key="...", model_name="...")

result = await client.think_with_retry(
    initial_messages="请分析以下文本",
    parser=my_parser,
    max_retries=3
)
# 只输出简洁的日志
```

### 启用 debug 模式
```python
result = await client.think_with_retry(
    initial_messages="请分析以下文本",
    parser=my_parser,
    max_retries=3,
    debug=True  # 启用详细调试输出
)
# 输出详细的 LLM 输入/输出和解析结果
```

### 在 retry 循环中自动 debug
```python
async def analyze_with_debug(text):
    def parser(response):
        # 自定义解析逻辑
        if "ERROR" in response:
            return {"status": "error", "feedback": "请重新分析"}
        return {"status": "success", "content": response}

    result = await client.think_with_retry(
        initial_messages=f"分析文本：{text}",
        parser=parser,
        max_retries=3,
        debug=True  # 查看 retry 过程
    )
    return result
```

## Debug 输出格式示例

### 成功场景
```
=== think_with_retry DEBUG START ===
Initial messages (1 messages):
  [0] user: 你是一个文本分析助手...

=== Attempt 1/3 ===
Input to LLM (1 messages):
  [0] user: 你是一个文本分析助手，请分析以下文本...

LLM Response (raw_reply):
  根据分析，这段文本主要讲述...
  (Total length: 156 chars)

Parser result:
  Status: success
  Content: {'analysis': '...', 'sentiment': 'positive'}

=== think_with_retry SUCCESS ===
```

### 失败重试场景
```
=== think_with_retry DEBUG START ===
Initial messages (1 messages):
  [0] user: 请提取 JSON 格式的数据...

=== Attempt 1/3 ===
Input to LLM (1 messages):
  [0] user: 请提取 JSON 格式的数据...

LLM Response (raw_reply):
  这是一段文本，但没有 JSON...

Parser result:
  Status: error
  Feedback: 请返回有效的 JSON 格式

Appending feedback for retry:
  Assistant response: 这是一段文本，但没有 JSON...
  User feedback: 请返回有效的 JSON 格式

=== Attempt 2/3 ===
Input to LLM (3 messages):
  [0] user: 请提取 JSON 格式的数据...
  [1] assistant: 这是一段文本，但没有 JSON...
  [2] user: 请返回有效的 JSON 格式

LLM Response (raw_reply):
  {"name": "Test", "value": 123}

Parser result:
  Status: success
  Content: {'name': 'Test', 'value': 123}

=== think_with_retry SUCCESS ===
```

## 日志级别

- 所有 debug 输出使用 `self.logger.debug()` 级别
- 错误信息仍使用 `self.logger.warning()` 和 `self.logger.exception()`
- 确保 logger 配置为 DEBUG 级别才能看到详细输出

### 配置示例
```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 或者针对特定 logger
client.logger.setLevel(logging.DEBUG)
```

## 注意事项

1. **性能影响**：debug=True 会产生更多日志输出，可能略微影响性能
2. **敏感信息**：debug 输出包含完整的 messages 内容，注意不要泄露敏感数据
3. **日志大小**：大量调用时，debug=True 会产生大量日志，注意日志文件大小
4. **生产环境**：建议在生产环境使用 debug=False（默认值）

## 测试

测试文件：`tests/test_think_with_retry_debug.py`

运行测试：
```bash
python tests/test_think_with_retry_debug.py
```

测试覆盖：
- ✅ 方法签名验证（debug 参数存在且默认值为 False）
- ✅ debug=False 的简洁输出模式
- ✅ debug=True 的详细输出模式
- ✅ 输出格式示例

## 版本历史

- **2026-02-01**: 初始版本，添加 debug 参数
