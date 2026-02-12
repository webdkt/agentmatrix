NEED REVIEW - 基本废弃了


# 配置默认搜索引擎

## 概述

Web Searcher 现在支持通过 Agent Profile YAML 配置默认搜索引擎。每个 Agent 可以配置自己喜欢的搜索引擎，而无需在每次调用 `web_search` action 时手动指定。

## 支持的搜索引擎

- `google`: Google 搜索
- `bing`: Bing 搜索

## 配置方法

### 在 Agent Profile YAML 中配置

编辑 agent 的 profile yml 文件（例如 `profiles/researcher.yml`），在 `attribute_initializations` 下添加 `default_search_engine`：

```yaml
# 属性初始化（Mixin 需要的实例属性）
attribute_initializations:
  browser_adapter: null
  default_search_engine: "google"  # 配置默认搜索引擎
```

### 示例配置

#### Researcher Agent（使用 Google）

```yaml
# profiles/researcher.yml
name: Tom
description: 研究员
module: agentmatrix.agents.base
class_name: BaseAgent

mixins:
  - agentmatrix.skills.deep_researcher.DeepResearcherMixin

attribute_initializations:
  browser_adapter: null
  default_search_engine: "google"  # ← 使用 Google 作为默认引擎

system_prompt: |
  你是一个资深研究员，擅长进行深入的研究工作
```

#### Planner Agent（使用 Bing 或不配置）

```yaml
# profiles/planner.yml
name: Planner
description: 计划者
module: agentmatrix.agents.base
class_name: BaseAgent

mixins:
  - agentmatrix.skills.web_searcher.WebSearcherMixin

attribute_initializations:
  # 不配置 default_search_engine，将使用默认值 "bing"

system_prompt: |
  你是一个项目经理
```

## 使用方式

### 1. 使用配置的默认引擎

调用 `web_search` 时不指定 `search_engine` 参数，将使用配置的默认引擎：

```python
# 如果 default_search_engine 配置为 "google"
# 将使用 Google 搜索
result = await agent.web_search(
    purpose="研究 AI 安全",
    search_phrase="AI 安全最新进展"
)
```

### 2. 覆盖默认引擎

可以在调用时显式指定 `search_engine` 参数，覆盖配置的默认值：

```python
# 即使 default_search_engine 配置为 "google"
# 这里显式指定使用 "bing"
result = await agent.web_search(
    purpose="研究 AI 安全",
    search_engine="bing",  # ← 覆盖默认配置
    search_phrase="AI 安全最新进展"
)
```

## 优先级规则

搜索引擎的优先级（从高到低）：

1. **调用参数**: `web_search(search_engine="google")` ← 最高优先级
2. **Agent 配置**: `default_search_engine: "google"`
3. **系统默认**: `"bing"` ← 最低优先级（兜底）

## 向后兼容性

如果 agent profile 中没有配置 `default_search_engine`，系统将使用硬编码的默认值 `"bing"`。这确保了向后兼容性。

```python
# web_searcher.py 中的兜底逻辑
if search_engine is None:
    search_engine = getattr(self, 'default_search_engine', DEFAULT_SEARCH_ENGINE)
    # DEFAULT_SEARCH_ENGINE = "bing"
```

## 工作原理

### 加载流程

1. **AgentLoader 加载配置**（`core/loader.py`）
   ```python
   # 解析 attribute_initializations
   attribute_inits = profile.pop("attribute_initializations", {})

   # 注入到实例
   for attr_name, attr_value in attribute_inits.items():
       setattr(agent_instance, attr_name, parsed_value)
   # 例如：agent.default_search_engine = "google"
   ```

2. **Web Searcher 读取配置**（`skills/web_searcher.py`）
   ```python
   # web_search 函数中
   if search_engine is None:
       # 从实例属性读取配置
       search_engine = getattr(self, 'default_search_engine', DEFAULT_SEARCH_ENGINE)
   ```

## 配置验证

如果配置了无效的搜索引擎名称，系统将在运行时检测并回退到默认引擎：

```python
# 验证搜索引擎
if search_engine.lower() not in SEARCH_ENGINES:
    self.logger.warning(f"Unknown search engine '{search_engine}', using default '{DEFAULT_SEARCH_ENGINE}'")
    search_engine = DEFAULT_SEARCH_ENGINE
```

## 注意事项

1. **区分大小写**: 配置值建议使用小写（`"google"` 或 `"bing"`），虽然代码会自动转小写
2. **拼写检查**: 确保搜索引擎名称拼写正确，否则会回退到默认值
3. **Agent 重新加载**: 修改配置后需要重启 Agent 才能生效

## 调试日志

启用 DEBUG 日志级别可以看到搜索引擎选择过程：

```log
INFO: Using configured default search engine: google
INFO: 🔍 准备搜索: AI 安全最新进展
INFO: 🔍 搜索引擎: google
```
