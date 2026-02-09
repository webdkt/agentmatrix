# BrowserUseSkill - 浏览器自动化技能

基于 [browser-use](https://github.com/browser-use/browser-use) 的浏览器自动化技能，让 LLM 驱动浏览器执行复杂任务。

## 安装依赖

```bash
pip install browser-use langchain-openai
```

## 配置

### 与 AgentMatrix 集成

- **使用 `brain`**：从 `self.brain`（LLMClient）提取 `url`, `api_key`, `model_name` 创建 LangChain LLM
- **使用 `vision_brain`**：如果配置了 `vision_brain`，可以启用视觉模式
- **无需手动加载 .env**：Skill 直接使用 AgentMatrix 已经加载好的 LLMClient
- **遵循 Mixin 模式**：通过 `@register_action` 注册 actions

### LLMClient 适配

AgentMatrix 的 `LLMClient` 包含以下属性：
- `url`：API 端点
- `api_key`：API 密钥
- `model_name`：模型名称

Skill 通过 `_get_llm_client_config()` 提取这些配置，然后使用 `_create_langchain_llm()` 创建 LangChain 兼容的 LLM。


**说明**:
- `default_llm`：必需，用于普通任务
- `default_vision`：可选，用于视觉模式（需要支持视觉的模型，）


### 2. API Key 配置（.env）

见上文

### 3. Agent YAML 配置

```yaml
name: LibraryAgent
description: 带有浏览器自动化能力的 Agent
module: agentmatrix.agents.base
class_name: BaseAgent

mixins:
  - agentmatrix.skills.browser_use_skill.BrowserUseSkillMixin

system_prompt: |
  你是一个图书馆查询助手，可以使用浏览器自动化工具访问网页。

backend_model: default_llm
cerebellum_model: default_slm
```

**视觉模式配置**:
在 `llm_config.json` 中配置 `default_vision`，Loader 会自动创建 `vision_brain`


## 使用方式

### Actions

#### `browser_navigate(url, task, use_vision, max_actions)`

访问指定 URL 并执行导航任务。

```python
# Agent 内部使用
result = await self.browser_navigate(
    url="https://www.example.com",
    task="点击登录按钮并填写表单",
    use_vision=True,  # 使用视觉模式（需要配置 vision_brain）
    max_actions=10
)
```

#### `browser_search(site_url, keyword, search_instruction, use_vision, max_actions)`

在指定网站搜索关键词。

```python
result = await self.browser_search(
    site_url="https://www.szlib.org.cn/",
    keyword="卡拉马佐夫兄弟",
    use_vision=False,  # 不使用视觉模式
    max_actions=15
)
```

#### `search_szlib_book(book_name, use_vision, max_actions)`

专门用于深圳图书馆图书搜索的 Demo 功能。

```python
result = await self.search_szlib_book(
    book_name="卡拉马佐夫兄弟",
    use_vision=None,  # 自动检测（如果配置了 vision_brain 则启用）
    max_actions=15
)
```

### 视觉模式说明

- `use_vision=True`：强制使用视觉模式（需要配置 `vision_brain`）
- `use_vision=False`：强制不使用视觉模式
- `use_vision=None`：自动检测（如果配置了 `vision_brain` 则启用，否则禁用）

如果请求视觉模式但未配置 `vision_brain`，会自动回退到普通模式并发出警告。

### 用户调用示例

用户发送邮件：
```
主题: 查询图书
内容: 请帮我在深圳图书馆搜索《卡拉马佐夫兄弟》这本书的信息
```

Agent 会自动调用 `search_szlib_book` action。

## 测试

### 方法 1: 简单测试（推荐先运行）
```bash
cd tests
python test_browser_use_simple.py
```

### 方法 2: 标准测试（测试 AgentMatrix 集成）
```bash
cd tests
python test_browser_use_skill.py
```

## 实现细节

### 架构

```
BrowserUseSkillMixin (Skill)
    ├── _get_llm_client_config()     # 从 LLMClient 提取配置
    ├── _create_langchain_llm()      # 创建 LangChain LLM
    ├── _get_browser_use_llm()       # 获取 LLM（支持视觉模式切换）
    ├── _has_vision_brain()          # 检查是否配置了 vision_brain
    ├── browser_navigate()           # 导航 Action
    ├── browser_search()             # 搜索 Action
    └── search_szlib_book()          # Demo Action
```


