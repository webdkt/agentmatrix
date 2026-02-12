"!!! 过时待删除或者重做 !!!"
# think_with_image 使用指南

## 功能说明

`think_with_image` 是 `LLMClient` 新增的方法，用于调用支持视觉的大语言模型（Vision LLM）。

### 支持的模型

- **OpenAI 格式**: GPT-4V, GPT-4o, Claude 3.5 Sonnet（通过兼容API）
- **Gemini 格式**: Gemini Pro Vision, Gemini 1.5 Pro

### 方法签名

```python
async def think_with_image(
    self,
    messages: Union[str, List[Dict[str, str]]],
    image: str,
    **kwargs
) -> str:
    """
    Args:
        messages: 消息列表（OpenAI 格式）或单个字符串
        image: base64 编码的图片数据（不含 data:image/... 前缀）
        **kwargs: 额外的参数（temperature, max_tokens, detail 等）

    Returns:
        str: LLM 的文本回复
    """
```

## 使用示例

### 示例 1: 基本用法

```python
from agentmatrix.backends.llm_client import LLMClient

# 初始化客户端
llm_client = LLMClient(
    url="https://api.openai.com/v1/chat/completions",
    api_key="your-api-key",
    model_name="gpt-4o"  # 或 "gpt-4-vision-preview"
)

# 读取图片并转为 base64
import base64
with open("screenshot.png", "rb") as f:
    image_data = base64.b64encode(f.read()).decode('utf-8')

# 调用 Vision LLM
result = await llm_client.think_with_image(
    messages="请描述这张图片中的内容",
    image=image_data
)

print(result)
```

### 示例 2: 在浏览器自动化中使用

```python
from agentmatrix.core.browser.drission_page_adapter import DrissionPageAdapter
from agentmatrix.backends.llm_client import LLMClient

# 初始化
browser = DrissionPageAdapter(profile_path="./chrome_profile")
await browser.start(headless=False)

vision_llm = LLMClient(
    url="https://api.openai.com/v1/chat/completions",
    api_key="your-api-key",
    model_name="gpt-4o"
)

# 获取 tab 并截图
tab = await browser.get_tab()
screenshot = await browser.capture_screenshot(tab)

# 询问 Vision LLM
answer = await vision_llm.think_with_image(
    messages="页面上有登录按钮吗？如果有，它在哪个区域？（左上/右上/左下/右下）",
    image=screenshot
)

print(f"Vision 回答: {answer}")
```

### 示例 3: 在 BrowserAutomationSkill 中集成

```python
# 在 browser_automation_skill.py 中
class BrowserAutomationSkillMixin:

    async def _analyze_page_with_vision(self) -> str:
        """使用视觉分析页面"""
        browser = self._get_browser_adapter()
        vision = self._get_brain_with_vision()

        tab = await browser.get_tab()
        screenshot = await browser.capture_screenshot(tab)
        current_url = await asyncio.to_thread(lambda: tab.url)

        analysis_prompt = f"""请分析当前页面的截图：

1. 这是什么页面？（页面标题和主要功能）
2. 页面上有哪些主要的可交互元素？
3. 如果要完成任务，下一步应该做什么操作？

当前URL: {current_url}"""

        try:
            analysis = await vision.think_with_image(
                messages=analysis_prompt,
                image=screenshot,
                temperature=0.7,  # 可选参数
                max_tokens=500    # 可选参数
            )

            return f"页面分析结果：{analysis}"

        except Exception as e:
            return f"页面分析失败: {str(e)}"
```

### 示例 4: Gemini Vision

```python
# 使用 Gemini Pro Vision
gemini_vision = LLMClient(
    url="https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:streamGenerateContent",
    api_key="your-gemini-api-key",
    model_name="gemini-pro-vision"
)

result = await gemini_vision.think_with_image(
    messages="这张图片里有什么？",
    image=image_base64
)
```

### 示例 5: 自定义参数

```python
# OpenAI Vision API 支持的额外参数
result = await llm_client.think_with_image(
    messages="详细分析这张图片",
    image=image_base64,
    detail="high",        # 图片质量: low, high, auto
    temperature=0.5,      # 温度参数
    max_tokens=1000,      # 最大 tokens
    top_p=0.9            # top-p 采样
)

# Gemini Vision API 支持的额外参数
result = await gemini_vision.think_with_image(
    messages="分析图片",
    image=image_base64,
    temperature=0.7,
    maxOutputTokens=1000,  # Gemini 格式
    topP=0.9
)
```

## 参数说明

### messages 参数

支持两种格式：

**格式 1: 字符串**
```python
messages = "请描述这张图片"
```

**格式 2: 消息列表**
```python
messages = [
    {"role": "system", "content": "你是一个图片分析专家"},
    {"role": "user", "content": "请分析这张图片"}
]
# 会被合并成单个文本提示
```

### image 参数

必须是 base64 编码的图片数据，**不含** `data:image/...;base64,` 前缀。

```python
# ✅ 正确
image = "iVBORw0KGgoAAAANSUhEUgAAAAUA..."

# ❌ 错误
image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA..."
```

### detail 参数（仅 OpenAI）

控制图片的详细程度：
- `"low"`: 快速，低分辨率
- `"high"`: 慢，高分辨率（默认）
- `"auto"`: 自动选择

```python
result = await llm_client.think_with_image(
    messages="快速识别图片中的文字",
    image=image_base64,
    detail="low"  # 使用低质量模式加快速度
)
```

## 错误处理

```python
try:
    result = await llm_client.think_with_image(
        messages="分析图片",
        image=image_base64
    )
except Exception as e:
    print(f"Vision LLM 调用失败: {str(e)}")
    # 错误可能是：
    # - 网络连接问题
    # - API key 无效
    # - 模型不支持视觉
    # - 图片格式错误
```

## 性能优化建议

### 1. 图片大小控制

```python
def resize_image_if_needed(base64_data: str, max_size_kb: int = 500) -> str:
    """如果图片太大，进行压缩"""
    import io
    from PIL import Image

    # 解码 base64
    img_data = base64.b64decode(base64_data)
    img = Image.open(io.BytesIO(img_data))

    # 计算当前大小
    current_size_kb = len(img_data) / 1024

    if current_size_kb <= max_size_kb:
        return base64_data  # 不需要压缩

    # 计算缩放比例
    scale_factor = (max_size_kb / current_size_kb) ** 0.5
    new_size = tuple(int(dim * scale_factor) for dim in img.size)

    # 调整大小
    img_resized = img.resize(new_size, Image.LANCZOS)

    # 重新编码
    buffer = io.BytesIO()
    img_resized.save(buffer, format="PNG", optimize=True)
    resized_data = buffer.getvalue()

    return base64.b64encode(resized_data).decode('utf-8')

# 使用
resized_image = resize_image_if_needed(screenshot, max_size_kb=300)
result = await llm_client.think_with_image(
    messages="分析图片",
    image=resized_image,
    detail="low"  # 小图片可以用 low 质量
)
```

### 2. 缓存结果

```python
from functools import lru_cache
import hashlib

def cache_key_for_image(image_base64: str, prompt: str) -> str:
    """生成缓存键"""
    image_hash = hashlib.md5(image_base64.encode()).hexdigest()[:8]
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
    return f"vision_{image_hash}_{prompt_hash}"

# 使用缓存
@lru_cache(maxsize=100)
async def cached_vision_call(cache_key: str, image: str, prompt: str):
    return await llm_client.think_with_image(prompt, image)

key = cache_key_for_image(screenshot, "描述图片")
result = await cached_vision_call(key, screenshot, "描述图片")
```

### 3. 并行调用

```python
import asyncio

async def analyze_multiple_images(images_and_prompts):
    """并行分析多张图片"""
    tasks = []
    for image, prompt in images_and_prompts:
        task = llm_client.think_with_image(prompt, image)
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results

# 使用
results = await analyze_multiple_images([
    (img1, "描述图片1"),
    (img2, "描述图片2"),
    (img3, "描述图片3")
])
```

## 注意事项

1. **API 成本**: Vision LLM 通常比纯文本 LLM 贵，注意控制调用频率
2. **网络延迟**: 图片传输需要更多时间，建议使用异步并发
3. **模型限制**: 某些模型有图片大小限制（如 GPT-4V 限制 20MB）
4. **隐私安全**: 不要发送敏感或包含个人信息的图片
5. **流式输出**: 当前实现支持流式输出，但返回的是完整文本

## 与现有代码集成

### 在 IntelligentVisionLocator 中

```python
# browser_vision_locator.py 中的调用
async def _ask_vision_about_crosshair(self, screenshot_base64, element_description):
    prompt = f"""我正在寻找页面上的一个元素，描述如下：{element_description}

页面上有十字坐标线将页面分成四个区域。请告诉我这个目标元素：

1. 如果能明确分辨在哪个象限，请回答：左上、右上、左下、右下
2. 如果元素恰好被竖线穿过，请回答：左 或 右
3. 如果元素恰好被横线穿过，请回答：上 或 下
4. 如果元素就在十字交叉的正中间，请回答：中间

请只回答上述关键词中的一个，不要有其他内容。"""

    # 使用 think_with_image
    result = await self.vision.think_with_image(
        messages=prompt,
        image=screenshot_base64
    )

    return self._parse_vision_answer(result)
```

### 在 BrowserAutomationSkill 中

```python
async def _analyze_and_decide_action(self) -> str:
    browser = self._get_browser_adapter()
    vision = self._get_brain_with_vision()

    tab = await browser.get_tab()
    screenshot = await browser.capture_screenshot(tab)
    current_url = await asyncio.to_thread(lambda: tab.url)

    analysis_prompt = f"""请分析当前页面的截图，告诉我：

1. 这是什么页面？（页面标题和主要功能）
2. 页面上有哪些主要的可交互元素？
3. 如果要完成任务，下一步应该做什么操作？

当前URL: {current_url}

请简洁回答，重点说明第3点。"""

    try:
        analysis = await vision.think_with_image(
            messages=analysis_prompt,
            image=screenshot
        )

        return f"页面分析结果：{analysis}\n\n请根据分析结果选择具体的操作action。"

    except Exception as e:
        return f"页面分析失败: {str(e)}"
```

## 总结

`think_with_image` 方法提供了一个简洁统一的接口来调用各种 Vision LLM，支持：

- ✅ OpenAI Vision API (GPT-4V, GPT-4o)
- ✅ Gemini Pro Vision
- ✅ 流式输出
- ✅ 自定义参数
- ✅ 自动格式检测
- ✅ 错误处理

现在可以在浏览器自动化Skill中充分利用视觉理解能力！
