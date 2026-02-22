Probably Outdated
# BrowserUseSkill - 浏览器自动化技能

基于 [browser-use](https://github.com/browser-use/browser-use) 的浏览器自动化技能，让 LLM 驱动浏览器执行复杂任务。

## 安装依赖

```bash
pip install browser-use langchain-openai
```

## 配置

### LLM 配置（llm_config.json）

BrowserUseSkill 会自动从 `llm_config.json` 加载 LLM 配置：

- **优先配置**: `browser-use-llm`（推荐）
- **回退配置**: `deepseek-chat`（如果没有 `browser-use-llm`）

**支持的厂商**:
- **DeepSeek**: 使用 `ChatDeepSeek` 类（vendor-specific 实现）
  - `deepseek-chat`: 推荐，稳定
  - `deepseek-reasoner`: thinking 模型（暂未实现 wrapper，建议使用 deepseek-chat）

- **GLM (智谱 AI)**: 使用 `ChatOpenAI` 类（兼容模式）
  - `glm-4.6`: 推荐
  - `glm-4.6v`: thinking 模型（自动添加 `thinking={"type": "disabled"}` 参数）
  - `glm-4.7`, `glm-4.7-FlashX`: thinking 模型（同上）

**配置示例**:
```json
{
    "browser-use-llm": {
        "url": "https://api.deepseek.com/chat/completions",
        "API_KEY": "DEEPSEEK_API_KEY",
        "model_name": "deepseek-chat"
    },
    "deepseek_chat": {
        "url": "https://api.deepseek.com/chat/completions",
        "API_KEY": "DEEPSEEK_API_KEY",
        "model_name": "deepseek-chat"
    }
}
```

### 与 AgentMatrix 集成

- **自动加载 LLM**: Skill 直接从 `llm_config.json` 加载配置
- **无需手动注入**: 不需要通过 Agent YAML 配置 `brain` 或 `vision_brain`
- **遵循 Mixin 模式**: 通过 `@register_action` 注册 actions，无需 `__init__` 方法

### LLMClient 适配

AgentMatrix 的 `LLMClient` 包含以下属性：
- `url`: API 端点
- `api_key`: API 密钥
- `model_name`: 模型名称

Skill 通过 `_create_llm_client_for_browser_use()` 加载配置，然后使用 `_create_browser_use_llm_from_client()` 创建 browser-use 兼容的 LLM 实例。

**自动检测厂商**:
- DeepSeek: 检测 `deepseek` 关键词 → 使用 `ChatDeepSeek` 类
- GLM: 检测 `glm` 或 `bigmodel` 关键词 → 使用 `ChatOpenAI` 类
- 其他: 默认使用 `ChatOpenAI` 类


## 使用方式

### Actions

#### `browser_navigate(url, task, headless, max_actions)`

使用 browser-use Agent 执行浏览器自动化任务。

**特点**：
- **智能 Task 优化**：自动使用 LLM 将你的任务描述转换为符合 browser-use 最佳实践的格式
- **单一接口**：所有浏览器操作通过这一个 action 完成
- **自动导航**：Agent 会自动导航到指定 URL 并执行任务

**参数**：
- `url` (str): 起始网页 URL
- `task` (str): 自然语言任务描述（会自动优化）
- `headless` (bool): 是否隐藏浏览器窗口（默认 False 显示浏览器，设为 True 则隐藏）
- `max_actions` (int): 最大动作步数（默认 10）

**返回**：
任务执行结果（字符串格式），包含两部分：
- 【最终结果】：Agent 返回的任务结果（如果有）
- 【当前页面】：浏览器当前停留的 URL

**返回值示例**：

示例 1 - 有最终结果：
```
【最终结果】
成功提取到5条名言：
1. "The world as we have created it..." - Albert Einstein
2. "There are only two ways to live..." - Albert Einstein

【当前页面】
https://quotes.toscrape.com/
```

示例 2 - 无最终结果：
```
任务已完成，未返回结构化结果

【当前页面】
https://www.szlib.org.cn/search/result
```

### 使用示例

#### 示例 1: 提取页面内容

```python
result = await self.browser_navigate(
    url="https://quotes.toscrape.com/",
    task="提取前5条名言及其作者",
    headless=False,
    max_actions=10
)
```

**注意**：默认情况下浏览器会显示在屏幕上（`headless=False`），窗口大小为 1280x720。

**内部的自动优化过程**：
1. 用户输入："提取前5条名言及其作者"
2. LLM 自动优化为：
   ```
   1. Navigate to https://quotes.toscrape.com/
   2. Use extract action to extract the first 5 quotes with their authors
   3. Return the results in a structured format
   ```
3. browser-use Agent 执行优化后的任务

#### 示例 2: 网站搜索

```python
result = await self.browser_navigate(
    url="https://www.szlib.org.cn/",
    task="搜索书名'卡拉马佐夫兄弟'，返回书名、作者、出版社和可借状态",
    headless=False,
    max_actions=15
)
```

#### 示例 3: 表单填写

```python
result = await self.browser_navigate(
    url="https://example.com/login",
    task="1. 找到用户名和密码输入框\n2. 输入用户名 'admin' 和密码 'password123'\n3. 点击登录按钮\n4. 如果登录失败，重试一次",
    headless=True,
    max_actions=15
)
```

### Task 描述最佳实践

虽然此 action 会自动优化你的任务描述，但遵循以下原则可以获得更好的结果：

#### 1. 具体明确（Be Specific）
✅ **推荐**：
```
"1. Navigate to https://example.com
2. Use extract action with query 'product titles and prices'
3. Return first 10 results"
```

❌ **不推荐**：
```
"去网站上找些商品信息"
```

#### 2. 直接引用 Action 名称
明确告诉 Agent 使用哪个 action：
- `extract`: 提取内容
- `click`: 点击元素
- `input`: 输入文本
- `scroll`: 滚动页面
- `search`: 搜索引擎搜索

#### 3. 提供错误处理
```
"1. Navigate to https://example.com
2. If page times out, refresh and retry
3. Extract the main content"
```

#### 4. 使用强调词
```
"1. Navigate to login page
2. NEVER click on ads
3. ALWAYS use the search form to find content"
```


## 下载管理

BrowserUseSkill 自动处理文件下载，包括 PDF 文件。

### 默认下载路径

- **位置**：`{workspace}/downloads/`
- **自动创建**：如果目录不存在，会自动创建
- **用途**：所有通过浏览器下载的文件（PDF、图片、文档等）都保存在这里

**与 web_searcher.py 一致**：
- 使用相同的路径逻辑：`os.path.join(current_workspace, "downloads")`
- 便于统一管理和清理下载文件

### 下载能力

Browser-use 支持以下下载场景：

1. **点击下载链接**：自动处理下载对话框
2. **PDF 自动下载**：
   - 点击 PDF 链接后自动下载
   - 支持使用 `read_file` action 读取 PDF 内容
3. **批量下载**：可以一次性下载多个文件
4. **下载监控**：自动跟踪下载进度和状态

### 使用示例

```python
# 下载 PDF 并提取内容
result = await self.browser_navigate(
    url="https://arxiv.org/abs/2301.07041",
    task="下载论文 PDF 并提取摘要和主要结论",
    headless=False
)

# 下载的文件会保存在: {workspace}/downloads/
```

### 浏览器窗口设置

- **默认大小**：1280x720 像素
- **设计考虑**：适合常见笔记本屏幕
  - 约占屏幕宽度的 2/3
  - 约占屏幕高度的 90%
- **优点**：
  - 不会完全遮挡屏幕
  - 留出空间查看其他窗口（如 IDE、日志）
  - 适合大多数分辨率（1920x1080, 1366x768 等）


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
    ├── _get_llm_config_path()              # 获取 llm_config.json 路径
    ├── _create_llm_client_for_browser_use() # 从配置创建 LLMClient
    ├── _create_browser_use_llm_from_client() # 从 LLMClient 创建 browser-use LLM
    │   ├── 厂商检测（VENDOR_PATTERNS）     # 自动识别 DeepSeek, GLM 等
    │   ├── 类选择                          # DeepSeek→ChatDeepSeek, 其他→ChatOpenAI
    │   └── _create_glm_chat_wrapper()      # GLM thinking 模型专用 wrapper
    ├── _get_browser_use_llm()              # 获取或创建 LLM
    ├── _get_browser()                      # 获取或创建 Browser（keep_alive=True）
    ├── _close_browser()                    # 关闭浏览器
    └── browser_navigate()                  # 唯一对外 Action
        ├── 1. Task 优化                     # 使用 think_with_retry + LLM
        │   ├── 构建 optimization prompt
        │   ├── 调用 brain.think_with_retry()
        │   └── 提取 [OPTIMIZED_TASK]
        ├── 2. 创建 Agent                   # browser-use Agent
        └── 3. 执行并返回结果               # agent.run() + history.final_result()
```

### 智能 Task 优化

BrowserUseSkill 的核心创新是**自动 task 优化**机制，确保传递给 browser-use 的任务描述符合最佳实践。

#### 优化流程

1. **用户输入**：自然语言任务描述（可以是模糊的）
   ```python
   task = "提取前5条名言"
   ```

2. **LLM 优化**：使用 `think_with_retry` 调用 Agent 的 brain
   - Prompt: 包含 browser-use Prompting Guide 原则
   - Parser: `simple_section_parser` 提取 `[OPTIMIZED_TASK]`
   - 最大重试: 2 次

3. **优化结果**：结构化的 task 描述
   ```
   1. Navigate to https://quotes.toscrape.com/
   2. Use extract action to extract the first 5 quotes with their authors
   3. Return the results in a structured format
   ```

4. **执行任务**：传递优化后的 task 给 browser-use Agent

#### 优化 Prompt 设计

优化 prompt 包含以下关键元素：

- **browser-use Prompting Guide 原则**：Be Specific, Name Actions Directly, Provide Error Recovery, Use Emphasis
- **可用的 Actions 列表**：navigate, search, extract, click, input, scroll, send_keys, done, screenshot 等
- **Task 优化示例**：展示如何转换模糊任务为具体步骤
- **URL 上下文**：将目标 URL 注入到优化过程

#### 容错机制

- 如果 LLM 优化失败，自动回退到原始任务
- 不会因为优化失败而导致整个任务无法执行

### 厂商特定的 LLM 类选择

BrowserUseSkill 根据检测到的厂商自动选择合适的 browser-use LLM 类：

#### DeepSeek 厂商
- **检测**: 模型名或 URL 包含 `deepseek`
- **LLM 类**: `ChatDeepSeek`
- **参数**:
  ```python
  ChatDeepSeek(
      model="deepseek-chat",
      api_key=...,
      base_url="...",
      temperature=0.1,
  )
  ```
- **参考**: [DeepSeek Example](https://github.com/browser-use/browser-use/blob/main/examples/models/deepseek-chat.py)

#### GLM 和其他厂商
- **检测**: 模型名或 URL 包含 `glm`, `bigmodel` 等
- **LLM 类**: `ChatOpenAI`（来自 `browser_use.llm.openai.chat`）
- **参数**:
  ```python
  ChatOpenAI(
      model="glm-4.6",
      api_key=...,
      base_url="...",
      temperature=0.1,
      max_completion_tokens=4096,
  )
  ```

#### Thinking 模型处理
- **GLM thinking 模型**（如 glm-4.6v, glm-4.7）:
  - 自动创建 wrapper
  - 添加 `thinking={"type": "disabled"}` 参数
  - 参考: [智谱 AI Thinking 文档](https://docs.bigmodel.cn/cn/guide/capabilities/thinking)

- **DeepSeek thinking 模型**（如 deepseek-reasoner）:
  - 暂未实现 wrapper
  - 建议使用 `deepseek-chat` 代替

### Thinking 模式控制

BrowserUseSkill 通过厂商-模型列表字典自动检测和处理 thinking 模型：

#### 检测机制

```python
# 类级别字典，维护各厂商的 thinking 模型列表
THINKING_MODELS = {
    "zhipu": [
        "glm-4.6v",
        "glm-4.6v-thinking",
        "glm-4-plus",
        "glm-4-plus-thinking",
    ],
    "deepseek": [
        "deepseek-reasoner",
        "deepseek-reasoner-preview",
    ],
}

# 厂商识别规则
VENDOR_PATTERNS = {
    "zhipu": ["glm", "bigmodel"],
    "deepseek": ["deepseek"],
}
```

**检测流程**：
1. 根据模型名称或 URL 中的关键词识别厂商
2. 检查模型名是否在该厂商的 `THINKING_MODELS` 列表中
3. 如果是 thinking 模型，自动创建 wrapper 并添加相应参数

#### GLM 模型（智谱 AI）

- **检测**: 模型名在 `zhipu` 列表中（如 glm-4.6v）
- **处理**: 自动创建自定义 wrapper，在 API 调用时添加 `thinking={"type": "disabled"}`
- **参考**: [智谱 AI Thinking 文档](https://docs.bigmodel.cn/cn/guide/capabilities/thinking)

#### DeepSeek 模型

- **检测**: 模型名在 `deepseek` 列表中
- **处理**: 当前版本建议使用非 thinking 模型（如 deepseek-chat）
- **参考**: [DeepSeek Thinking 文档](https://api-docs.deepseek.com/zh-cn/guides/thinking_mode)

#### 添加新的 thinking 模型

只需在 `THINKING_MODELS` 字典中添加模型名即可，无需修改检测逻辑：

```python
# 示例：添加新的 GLM thinking 模型
THINKING_MODELS = {
    "zhipu": [
        "glm-4.6v",
        "glm-4.6v-thinking",
        "glm-5v",  # 新增
    ],
    ...
}
```


