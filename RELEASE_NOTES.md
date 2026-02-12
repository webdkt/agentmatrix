# Release Notes

## [0.1.6] - 2025-02-03

### 🎉 Major Features

#### 1. **批量 Action 执行支持**
MicroAgent 现在支持在一次思考中检测和执行多个 actions，显著提升多步骤任务的执行效率。

**核心改进**：
- ✅ 正则表达式 Action 检测：支持完整的标识符匹配，兼容中文环境
- ✅ 批量执行：按 LLM 输出的自然顺序依次执行多个 actions
- ✅ 智能参数解析：Cerebellum 能够理解包含多个 actions 的上下文
- ✅ 统一结果反馈：多个 actions 的执行结果合并为一条消息反馈给 Brain

**示例**：
```python
# LLM 输出
"我需要搜索AI安全研究，然后总结内容，最后发邮件给用户"

# 自动检测并执行
[web_search 执行成功]: 找到10篇相关论文...
[summarize_content 执行成功]: AI安全研究3个方向...
```

**技术细节**：
- 使用正则表达式 `r'([a-zA-Z_][a-zA-Z0-9_]*)'` 进行精确匹配
- 支持完整单词匹配，避免部分误识别
- 自动去重但保持原始顺序
- 特殊 actions（all_finished, rest_n_wait）在循环内部处理

#### 2. **可配置的默认搜索引擎**
Agent 现在可以通过 Profile YAML 配置默认搜索引擎，无需在每次调用时手动指定。

**配置方式**：
```yaml
# profiles/researcher.yml
attribute_initializations:
  default_search_engine: "google"  # 可选: "google" 或 "bing"
```

**优先级规则**：
1. 调用参数：`web_search(search_engine="google")` （最高优先级）
2. Agent 配置：`default_search_engine: "google"`
3. 系统默认：`"bing"` （兜底）

**向后兼容**：
- 未配置的 Agent 自动使用 `"bing"` 作为默认引擎
- 现有代码无需修改

### 🔧 Improvements

#### Action Detection 增强
- **正则表达式优化**：使用 `r'([a-zA-Z_][a-zA-Z0-9_]*)'` 替代简单的字符串查找
- **中文环境支持**：即使 action 名称前后没有空格（如 `用web_search搜索`），也能正确匹配
- **完整单词匹配**：避免部分匹配问题（例如 `"web"` 不会匹配到 `"web_search"`）
- **自动去重**：同一 action 名称多次出现时，只保留第一次出现的位置

#### Cerebellum 参数解析优化
- **多 Action 上下文理解**：System Prompt 明确指示"只关注指定的 action"
- **智能过滤**：Cerebellum 能够从包含多个 actions 的意图中提取相关参数
- **改进的错误提示**：参数缺失时明确指出是哪个 action 的哪个参数

### 📝 Documentation

#### 新增文档
- `docs/default_search_engine_config.md` - 默认搜索引擎配置指南
  - 配置方法
  - 使用示例
  - 优先级规则
  - 工作原理说明

### 🔄 Technical Changes

#### Modified Files
- `src/agentmatrix/agents/micro_agent.py`
  - `_detect_actions()` - 重写为批量检测方法
  - `_run_loop()` - 支持批量 action 执行逻辑
  - `_format_task_message()` - 优化任务消息格式（改为 `[NEW INPUT]`）

- `src/agentmatrix/core/cerebellum.py`
  - `parse_action_params()` - 更新 System Prompt，支持多 action 上下文

- `src/agentmatrix/skills/web_searcher.py`
  - `web_search()` - 添加 `default_search_engine` 配置支持
  - 参数默认值从 `"bing"` 改为 `None`，支持动态配置

- `src/agentmatrix/profiles/researcher.yml`
  - 添加 `default_search_engine: "google"` 配置示例

### 🐛 Bug Fixes

- 修复 action 检测时的部分匹配问题
- 修复中文环境下 action 名称识别失败的问题
- 修复批量执行时特殊 action 处理顺序错误的问题

### ⚠️ Breaking Changes

**无破坏性变更** - 所有改动完全向后兼容

### 📋 Migration Guide

#### 升级到 0.1.6

1. **无需代码修改**：所有现有代码完全兼容
2. **可选配置**：如需使用新功能，可按需配置

**推荐配置**（可选）：
```yaml
# 为你的 Agent 配置默认搜索引擎
attribute_initializations:
  default_search_engine: "google"
```

### 🔮 Known Issues

- 无

### 🙏 Credits

感谢所有贡献者的反馈和建议！

---

## [0.1.5] - Previous Release

（之前版本的 Release Note 可以在此补充）
