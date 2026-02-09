# vision_brain 配置机制更新

## ✅ 已完成的改进

将 `vision_brain` 的配置机制改为和 `brain`、`cerebellum` 完全一致。

## 修改内容

### 1. BaseAgent (base.py)

**修改前**：
```python
self.brain = None
self.cerebellum = None
self.vision_brain = None
self.vision_model = profile.get("vision_model", None)  # ❌ 不一致
```

**修改后**：
```python
self.brain = None
self.cerebellum = None
self.vision_brain = None  # ✅ 和 brain、cerebellum 一样
```

### 2. AgentLoader (loader.py)

**新增**：和 cerebellum 完全一致的初始化逻辑

```python
# 设置视觉大模型 (Vision Brain) - 机制和 cerebellum 一样
vision_config = profile.get("vision_brain")
vision_client = None

if vision_config:
    # 从 vision_brain 配置块中读取 backend_model
    vision_model = vision_config.get("backend_model")
    vision_client = self._create_llm_client(vision_model)
    print(f"[{agent_instance.name}] Using Vision Brain: {vision_model}")
else:
    # 如果没有配置 vision_brain，保持为 None
    print(f"[{agent_instance.name}] No Vision Brain configured.")

agent_instance.vision_brain = vision_client
```

### 3. BrowserAutomationSkill (browser_automation_skill.py)

**修改前**：
```python
vision = self._get_brain_with_vision()  # ❌ 旧方法
```

**修改后**：
```python
vision = getattr(self, 'vision_brain', None)  # ✅ 直接访问属性

if not vision:
    return "错误：缺少 vision_brain 配置。请在 agent 配置文件中添加 vision_brain.backend_model"
```

## YAML 配置示例

### 完整配置

```yaml
name: BrowserExpert
module: agentmatrix.agents.base
class_name: BaseAgent

mixins:
  - agentmatrix.skills.browser_automation_skill.BrowserAutomationSkillMixin

# 主模型（用于推理、规划）
backend_model: default_llm

# 小脑（用于参数解析）
cerebellum:
  backend_model: default_slm

# 🆕 视觉大模型（用于图片理解）
vision_brain:
  backend_model: gpt-4o  # 或其他支持视觉的模型
```

### llm_config.json 需要包含

```json
{
  "default_llm": {
    "url": "https://api.openai.com/v1/chat/completions",
    "API_KEY": "OPENAI_API_KEY",
    "model_name": "gpt-4"
  },
  "default_slm": {
    "url": "https://api.openai.com/v1/chat/completions",
    "API_KEY": "OPENAI_API_KEY",
    "model_name": "gpt-3.5-turbo"
  },
  "gpt-4o": {
    "url": "https://api.openai.com/v1/chat/completions",
    "API_KEY": "OPENAI_API_KEY",
    "model_name": "gpt-4o"
  }
}
```

## 使用方式

### 基本使用（不需要手动注入）

```python
from agentmatrix.core.loader import AgentLoader

loader = AgentLoader(profile_path="path/to/profiles")
agent = loader.load_from_file("browser_agent.yml")

# vision_brain 已经自动配置好了！
print(agent.vision_brain)  # <agentmatrix.backends.llm_client.LLMClient>
print(agent.brain)  # <agentmatrix.backends.llm_client.LLMClient>
print(agent.cerebellum)  # <agentmatrix.core.cerebellum.Cerebellum>
```

### 浏览器任务

```python
# 只需要配置 browser_adapter
from agentmatrix.core.browser.drission_page_adapter import DrissionPageAdapter

browser = DrissionPageAdapter(profile_path="./chrome_profile")
await browser.start(headless=False)

agent.browser_adapter = browser

# 直接执行
result = await agent.browser_research("登录Gmail")
```

## 配置对比

### 之前的方式（不一致）

```yaml
# ❌ 旧方式：不一致
backend_model: default_llm

# 需要手动注入
attribute_initializations:
  brain_with_vision: null  # 运行时手动设置
```

```python
# 需要手动注入
from agentmatrix.backends.llm_client import LLMClient

vision_llm = LLMClient(url, key, model)
agent.brain_with_vision = vision_llm  # 手动设置
```

### 现在的方式（一致）

```yaml
# ✅ 新方式：和 brain、cerebellum 一样
backend_model: default_llm

vision_brain:
  backend_model: gpt-4o  # 配置文件中指定
```

```python
# 自动初始化，无需手动注入
loader = AgentLoader()
agent = loader.load_from_file("browser_agent.yml")

# vision_brain 已经就绪！
```

## 优势

1. ✅ **一致性**：vision_brain、brain、cerebellum 配置机制完全一致
2. ✅ **简洁**：不需要运行时手动注入
3. ✅ **清晰**：配置文件中一目了然
4. ✅ **灵活**：可以轻松切换不同的 vision 模型
5. ✅ **可维护**：统一的管理方式，易于维护

## 迁移指南

如果你之前使用了旧的方式，只需要：

1. **更新 YAML 配置**：
   ```yaml
   # 添加
   vision_brain:
     backend_model: gpt-4o
   ```

2. **删除手动注入代码**：
   ```python
   # 删除这些
   agent.brain_with_vision = vision_llm
   ```

3. **更新 Skill 代码**：
   ```python
   # 改为
   vision = getattr(self, 'vision_brain', None)
   ```

## 总结

现在 `vision_brain` 的配置机制和 `brain`、`cerebellum` 完全一致，使得：

- BaseAgent 有三个标准的大模型组件：
  - `brain` - 主推理模型
  - `cerebellum` - 参数解析模型
  - `vision_brain` - 视觉理解模型

- 配置方式统一：
  - YAML 中指定 `backend_model`
  - AgentLoader 自动创建 LLMClient
  - 无需手动注入

---

**更新日期**: 2026-02-05
**影响范围**: BaseAgent, AgentLoader, BrowserAutomationSkill
**向后兼容**: 否（需要更新配置文件）
