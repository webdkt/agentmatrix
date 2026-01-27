# Dialog-With-Retry API 改进

## 改进说明

根据实际使用反馈，对 `dialog_with_retry` 的返回值设计进行了优化。

## 改进前

```python
# 正常完成
return {
    "status": "success",
    "content": ...,
    "rounds_used": 2
}

# 超过max_rounds
return {
    "status": "max_rounds_reached",  # ← 不同的status
    "last_output": ...,
    "last_feedback": ...
}
```

**问题**：
- 调用端需要处理两种不同的status
- 即使只想用最后的结果，也需要else分支

## 改进后

```python
# 正常完成
return {
    "status": "success",  # ← 统一的status
    "content": ...,
    "rounds_used": 2,
    "max_rounds_exceeded": False  # ← 标记是否超过max_rounds
}

# 超过max_rounds
return {
    "status": "success",  # ← 统一的status
    "content": ...,  # ← 仍然有content
    "rounds_used": 3,
    "max_rounds_exceeded": True,  # ← 标记是否超过max_rounds
    "last_feedback": ...  # ← 额外的反馈信息
}
```

**优势**：
- ✅ 调用端统一处理：`result["status"]` 总是 `"success"`
- ✅ 总是有 `content` 可用：即使超过max_rounds，也能用最后的结果
- ✅ 可选的严格检查：如果需要，可以检查 `max_rounds_exceeded` 标记

## 使用示例

### 简化后的调用代码

```python
async def _planning_stage(self, ctx: ResearchContext):
    result = await self.brain.dialog_with_retry(
        producer_task=...,
        producer_persona=...,
        verifier_task_template=...,
        verifier_persona=...,
        approver_parser=...,
        max_rounds=3
    )

    # 可选：检查是否超过max_rounds
    if result.get("max_rounds_exceeded"):
        self.logger.warning(f"未能在{result['rounds_used']}轮内获得批准")

    # 无论如何，都使用content（统一处理）
    final_plan = result["content"]

    # 继续处理...
```

### 对比：改进前 vs 改进后

**改进前**（需要else分支）：
```python
result = await brain.dialog_with_retry(...)

if result["status"] == "success":
    # 正常处理
    content = result["content"]
else:
    # 失败处理（降级）
    content = result.get("last_output", "")
    if not content:
        raise Exception("...")
```

**改进后**（统一处理）：
```python
result = await brain.dialog_with_retry(...)

# 可选警告
if result.get("max_rounds_exceeded"):
    logger.warning("...")

# 统一处理
content = result["content"]
```

## API 文档更新

### 返回值

```python
{
    "status": "success",  # 总是success
    "content": str,       # A的最终输出
    "rounds_used": int,  # 使用的轮数

    "max_rounds_exceeded": bool,  # 是否超过max_rounds
    "last_feedback": str          # 最后的反馈（仅当exceeded时存在）
}
```

### 字段说明

- `status`：固定为 `"success"`，简化调用端处理
- `content`：A的最后一次输出，总是可用
- `rounds_used`：实际使用的轮数（1-max_rounds）
- `max_rounds_exceeded`：布尔值，True表示达到max_rounds仍未获得批准
- `last_feedback`：B的最后一次反馈（仅当 `max_rounds_exceeded=True` 时存在）

### 使用建议

**场景1：不在乎是否超过max_rounds**
```python
result = await brain.dialog_with_retry(...)
content = result["content"]  # 直接使用
```

**场景2：需要严格检查**
```python
result = await brain.dialog_with_retry(...)

if result.get("max_rounds_exceeded"):
    # 记录日志或采取其他措施
    logger.warning(f"Dialog exceeded max rounds: {result['last_feedback']}")

content = result["content"]  # 仍然可以使用
```

**场景3：超过max_rounds时抛异常**
```python
result = await brain.dialog_with_retry(...)

if result.get("max_rounds_exceeded"):
    raise Exception(f"Failed: {result['last_feedback']}")

content = result["content"]
```

## 总结

这个改进遵循了"宽松接收，严格处理"的原则：
- **宽松接收**：API总是返回可用结果
- **严格处理**：调用端可以根据需要检查 `max_rounds_exceeded` 标记

这样简化了大多数调用场景，同时保留了严格检查的灵活性。
