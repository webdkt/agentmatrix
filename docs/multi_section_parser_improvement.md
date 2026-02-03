# multi_section_parser 改进：增加 return_list 和 allow_empty 参数

## 改进目标

在 `deep_researcher.py` 中，很多地方使用 `multi_section_parser` 后都需要手动将 section 内容拆分成行：

```python
# 旧代码：需要手动处理
sections = await self.brain.think_with_retry(
    generate_prompt,
    multi_section_parser,
    section_headers=["[新计划]"],
    match_mode="ALL"
)

# 提取任务列表
new_tasks_text = sections["[新计划]"]
new_tasks = [
    line.strip()
    for line in new_tasks_text.split('\n')
    if line.strip()
]
```

这种重复代码很多，需要改进。

## 改进方案

为 `multi_section_parser` 增加两个新参数：

### 1. `return_list = False`（默认）
- **False**：返回字符串（默认行为，向后兼容）
- **True**：自动将内容拆分为行列表
  - 等价于：`[line.strip() for line in content.split('\n') if line.strip()]`

### 2. `allow_empty = False`（默认）
- **False**：不允许空内容（默认行为）
  - 如果 section 内容 strip 后为空，返回错误
- **True**：允许空的 section 内容

## 实现细节

### 内部辅助函数
```python
def _post_process(content: str):
    """根据参数处理内容"""
    # 如果不允许空且内容为空
    if not allow_empty and not content.strip():
        return None  # 标记为无效

    # 如果需要返回列表
    if return_list:
        return [line.strip() for line in content.split('\n') if line.strip()]

    # 否则返回字符串
    return content.strip()
```

### 应用位置
1. **多 section 模式**：在提取每个 section 内容时调用
2. **单 section 模式**：在提取最终内容时调用

## 使用示例

### 示例 1：自动拆分行
```python
# 旧代码
sections = await self.brain.think_with_retry(
    prompt,
    multi_section_parser,
    section_headers=["[任务列表]"],
    match_mode="ALL"
)
tasks_text = sections["[任务列表]"]
tasks = [line.strip() for line in tasks_text.split('\n') if line.strip()]

# 新代码
sections = await self.brain.think_with_retry(
    prompt,
    multi_section_parser,
    section_headers=["[任务列表]"],
    match_mode="ALL",
    return_list=True  # ✨ 自动拆分行
)
tasks = sections["[任务列表]"]  # 直接就是列表
```

### 示例 2：允许空内容
```python
# 有些场景下，section 可能为空，这是合法的
result = multi_section_parser(
    text,
    section_headers=["[备注]"],
    match_mode="ALL",
    allow_empty=True  # ✅ 允许空内容
)
```

### 示例 3：组合使用
```python
# 返回行列表，允许空列表（内容为空时）
result = multi_section_parser(
    text,
    section_headers=["[选项]"],
    match_mode="ALL",
    return_list=True,
    allow_empty=True
)
options = result["content"]["[选项]"]  # [] 如果内容为空
```

## 测试覆盖

### ✅ 测试场景
1. **默认行为**：向后兼容，返回字符串
2. **return_list=True**：自动拆分行，过滤空行
3. **return_list=True + 空行**：正确过滤空行
4. **allow_empty=False**：拒绝空内容（默认）
5. **allow_empty=True**：允许空内容
6. **组合参数**：return_list=True + allow_empty=False
7. **组合参数**：return_list=True + allow_empty=True

### 测试结果
```
✅ 测试 1: 默认行为（向后兼容）
✅ 测试 2: return_list=True（自动拆分行）
✅ 测试 3: return_list=True 过滤空行
✅ 测试 4: allow_empty=False（默认，不允许空）
✅ 测试 5: allow_empty=True（允许空）
✅ 测试 6: 组合 return_list=True + allow_empty=False
✅ 测试 7: return_list=True + allow_empty=True（空内容）
```

## 改进效果

### 代码简洁性
**改进前：**
```python
sections = await self.brain.think_with_retry(
    prompt,
    multi_section_parser,
    section_headers=["[新计划]"],
    match_mode="ALL"
)
new_tasks_text = sections["[新计划]"]
new_tasks = [
    line.strip()
    for line in new_tasks_text.split('\n')
    if line.strip()
]
```

**改进后：**
```python
sections = await self.brain.think_with_retry(
    prompt,
    multi_section_parser,
    section_headers=["[新计划]"],
    match_mode="ALL",
    return_list=True  # ✨ 一行搞定
)
new_tasks = sections["[新计划]"]
```

### 优势总结
- ✅ **减少重复代码**：拆分行逻辑集中在 parser 中
- ✅ **向后兼容**：默认参数保持原有行为
- ✅ **灵活组合**：两个参数可以独立或组合使用
- ✅ **代码更简洁**：从 4 行减少到 1 行
- ✅ **易于维护**：逻辑集中在一处

## 影响范围

### 修改的文件
- `src/agentmatrix/skills/parser_utils.py`

### 测试文件
- `tests/test_multi_section_parser.py`

### 向后兼容性
- ✅ 完全向后兼容
- ✅ 默认参数保持原有行为
- ✅ 现有代码无需修改

## 下一步建议

可以考虑在 `deep_researcher.py` 中逐步重构，使用新参数简化代码：

```python
# 查找所有类似这样的代码模式
# pattern: sections[...].split('\n')

# 替换为使用 return_list=True
```

## 版本历史
- **2026-02-02**: 初始版本，增加 return_list 和 allow_empty 参数
