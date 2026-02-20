# Browser-Use Skill 重构说明

## 📋 概述

针对 GLM、Mimo 等国产模型对 browser-use 的兼容性问题，采用了专家建议的方案进行重构。新实现利用 browser-use 内置的 JSON schema 兼容性参数，大幅简化了代码。

## 🔴 旧实现的问题

### 1. 复杂的 Monkey Patching
```python
# 旧代码需要为每个厂商创建单独的 wrapper
def _create_glm_chat_wrapper(self, base_llm):
    class GLMChatOpenAIWrapper:
        async def ainvoke(self, messages, output_format=None, **kwargs):
            # 复杂的 monkey patching 逻辑
            original_create = self._base_llm.get_client().chat.completions.create
            # ... 省略大量代码
```

### 2. 只解决部分问题
- ✅ 处理了 thinking 参数问题
- ❌ **没有处理 JSON schema 兼容性问题**（这是主要问题根源）
- ❌ 代码复杂，难以维护

### 3. 维护成本高
- 每新增一个国产模型就需要写新的 wrapper
- 厂商识别逻辑分散
- 无法处理 JSON schema 的兼容性问题

## ✅ 新实现方案

### 核心思路：使用 browser-use 内置参数

browser-use 的 `ChatOpenAI` 类已经内置了以下关键参数：

```python
from browser_use.llm.openai.chat import ChatOpenAI

llm = ChatOpenAI(
    model='mimo-v2-flash',
    api_key='your-api-key',
    base_url='https://api.xiaomimimo.com/v1',
    # ✅ 这些参数已经在 ChatOpenAI 中实现了！
    dont_force_structured_output=True,   # 禁用强制结构化输出
    remove_min_items_from_schema=True,   # 移除 minItems
    remove_defaults_from_schema=True,    # 移除默认值
)
```

### 参数说明

| 参数 | 作用 | 解决的问题 |
|------|------|-----------|
| `dont_force_structured_output=True` | 不添加 `response_format=json_schema` 参数 | 一些国产模型不支持 strict mode 的 JSON schema |
| `remove_min_items_from_schema=True` | 移除 schema 中的 `minItems` 字段 | 一些模型不支持 minItems 验证 |
| `remove_defaults_from_schema=True` | 移除 schema 中的 `default` 值 | 简化 schema，提高兼容性 |

### 实现细节

#### 1. 配置驱动的厂商识别

```python
# 国产模型配置
CHINESE_LLM_CONFIG = {
    "glm": {
        "dont_force_structured_output": True,
        "remove_min_items_from_schema": True,
        "remove_defaults_from_schema": True,
        "use_extra_body": False,  # GLM 使用 thinking 参数直接传递
    },
    "mimo": {
        "dont_force_structured_output": True,
        "remove_min_items_from_schema": True,
        "remove_defaults_from_schema": True,
        "use_extra_body": True,   # Mimo 使用 extra_body 传递 thinking 参数
    },
}
```

#### 2. 简化的 LLM 创建逻辑

```python
def _create_browser_use_llm_from_client(self, llm_client):
    # 检测厂商
    vendor = self._detect_vendor(model_name, url)

    # 准备基础参数
    llm_kwargs = {
        "model": model_name,
        "api_key": api_key,
        "base_url": url,
        "temperature": 0.1,
        "max_completion_tokens": 4096,
    }

    # 如果是国产模型，添加兼容性参数
    if vendor in self.CHINESE_LLM_CONFIG:
        config = self.CHINESE_LLM_CONFIG[vendor]
        llm_kwargs.update({
            "dont_force_structured_output": config["dont_force_structured_output"],
            "remove_min_items_from_schema": config["remove_min_items_from_schema"],
            "remove_defaults_from_schema": config["remove_defaults_from_schema"],
        })

    # 创建 LLM 实例
    return BUChatOpenAI(**llm_kwargs)
```

#### 3. 针对特殊情况的包装器

对于像 Mimo 这样需要通过 `extra_body` 传递 `thinking` 参数的模型，保留了简化的包装器：

```python
def _create_llm_with_extra_body(self, llm_class, llm_kwargs, vendor):
    """创建支持 extra_body 参数的 LLM 实例"""
    class LLMWithExtraBodyWrapper:
        async def ainvoke(self, messages, output_format=None, **kwargs):
            # 添加 extra_body 参数
            create_kwargs['extra_body'] = {"thinking": {"type": "disabled"}}
            # ... 省略实现

    base_llm = llm_class(**llm_kwargs)
    return LLMWithExtraBodyWrapper(base_llm)
```

## 📊 改进效果

### 代码量减少
- 删除了 ~100 行复杂的 wrapper 代码
- 配置更加清晰，易于维护

### 兼容性提升
- ✅ **解决了 JSON schema 兼容性问题**（主要问题）
- ✅ 解决了 thinking 模式问题
- ✅ 易于扩展新的国产模型

### 维护性提升
- 添加新厂商只需要在 `CHINESE_LLM_CONFIG` 中添加配置
- 不需要写复杂的 wrapper 类
- 逻辑更加清晰

## 🧪 测试建议

1. **GLM 模型测试**
```python
# 在 llm_config.json 中配置：
{
  "browser-use-llm": {
    "model_name": "glm-4.6",
    "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "api_key": "your-api-key"
  }
}
```

2. **Mimo 模型测试**
```python
{
  "browser-use-llm": {
    "model_name": "mimo-v2-flash",
    "url": "https://api.xiaomimimo.com/v1/chat/completions",
    "api_key": "your-api-key"
  }
}
```

3. **标准 OpenAI 模型测试**
```python
{
  "browser-use-llm": {
    "model_name": "gpt-4o",
    "url": "https://api.openai.com/v1/chat/completions",
    "api_key": "your-api-key"
  }
}
```

## 🔧 扩展新的国产模型

如果需要支持新的国产模型，只需在 `CHINESE_LLM_CONFIG` 中添加配置：

```python
CHINESE_LLM_CONFIG = {
    # 现有配置...
    "new_vendor": {
        "dont_force_structured_output": True,  # 根据实际情况调整
        "remove_min_items_from_schema": True,
        "remove_defaults_from_schema": True,
        "use_extra_body": False,  # 如果需要 extra_body，设置为 True
    },
}

VENDOR_PATTERNS = {
    # 现有模式...
    "new_vendor": ["keyword1", "keyword2"],  # 添加识别关键词
}
```

## 📝 总结

这次重构采用了"**使用内置功能而不是自己造轮子**"的最佳实践：

1. **充分利用 browser-use 的内置参数** - 这些参数就是为了解决兼容性问题而设计的
2. **配置驱动** - 通过配置而不是代码来管理不同厂商的差异
3. **简化代码** - 删除了 ~100 行复杂的 wrapper 代码
4. **提高可维护性** - 新增厂商只需添加配置，不需要写新代码

这个方案应该能够彻底解决你遇到的国产模型兼容性问题。
