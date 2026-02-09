# 浏览器自动化专家 Skill - 实现总结

## ✅ 已完成的实现

### 1. 核心组件

#### 1.1 DrissionPageAdapter 扩展
**文件**: `src/agentmatrix/core/browser/drission_page_adapter.py`

新增方法：
- `capture_screenshot()` - 捕获页面截图（base64）
- `draw_crosshair()` - 画出十字坐标线
- `remove_crosshair()` - 移除十字线
- `highlight_region()` - 加亮指定区域
- `highlight_elements()` - 加亮多个元素
- `remove_highlights()` - 清除所有高亮
- `get_elements_in_bounds()` - 获取边界内的元素
- `get_elements_crossed_by_line()` - 获取被坐标线穿过的元素
- `get_interactive_elements()` - 获取所有可交互元素

#### 1.2 SmartRegionDivider（智能区域划分器）
**文件**: `src/agentmatrix/skills/browser_vision_divider.py`

核心功能：
- `calculate_initial_quadrants()` - 计算初始4个象限
- `calculate_quadrant_bounds()` - 在父区域内计算象限边界
- `dynamic_divide_by_axis()` - 按坐标轴动态分块
- `should_stop_dividing()` - 判断是否停止细分
- `decide_next_strategy()` - 根据Vision回答决定下一步策略

#### 1.3 IntelligentVisionLocator（智能视觉定位器）
**文件**: `src/agentmatrix/skills/browser_vision_locator.py`

核心流程：
```python
locate_element_interactively()
  ├─ 画十字 → 问Vision
  ├─ 明确象限 → 递归细分
  ├─ 被线穿过 → 动态分块
  └─ 元素够少 → 候选确认
```

关键方法：
- `_ask_vision_about_crosshair()` - 询问元素在哪个区域
- `_recursive_quadrant_search()` - 递归象限搜索
- `_dynamic_divide_and_ask()` - 动态分块询问
- `_confirm_element()` - 候选元素确认
- `_ask_vision_select_division()` - 询问Vision选择分块
- `_ask_vision_confirm_element()` - 询问Vision确认元素

#### 1.4 BrowserAutomationSkillMixin（浏览器自动化Skill）
**文件**: `src/agentmatrix/skills/browser_automation_skill.py`

主要Actions：
- `browser_research(task)` - 主入口，启动ReAct循环
- `_analyze_and_decide_action()` - 分析页面并决策
- `_locate_and_click(description)` - 定位并点击
- `_locate_and_input(description, text)` - 定位并输入
- `_locate_and_scroll(direction, distance)` - 滚动页面
- `_finish_task(result, summary)` - 完成任务

#### 1.5 Vision Prompts 模板
**文件**: `src/agentmatrix/skills/browser_vision_prompts.py`

包含：
- `INITIAL_CROSSHAIR_PROMPT` - 初始十字划分询问
- `QUADRANT_PROMPT` - 象限内询问
- `DYNAMIC_DIVIDE_PROMPT` - 动态分块询问
- `ELEMENT_CONFIRM_PROMPT` - 元素确认询问
- `REFINE_DIRECTION_PROMPT` - 方向精调询问
- `PAGE_ANALYSIS_PROMPT` - 页面分析提示
- `REACT_THINK_PROMPT` - ReAct循环思考提示

#### 1.6 配置示例
**文件**: `src/agentmatrix/profiles/browser_agent.yml`

BrowserExpert agent的完整配置示例

### 2. 核心创新点

#### 2.1 智能自适应划分
不使用机械的固定网格，而是：
- 利用"元素被坐标线穿过"的信息
- 根据元素实际分布动态分块
- 自适应判断何时停止细分

#### 2.2 渐进式定位流程
```
十字划分 (2x2)
  ↓
Vision回答: 左/右/上/下/象限
  ↓
┌─────────┬─────────┬─────────┐
│ 明确象限 │ 被线穿过 │  中间   │
└─────────┴─────────┴─────────┘
    ↓           ↓         ↓
递归细分    动态分块   直接确认
    ↓           ↓
判断: 区域大小 + 元素数量
    ↓
候选元素确认（加亮+询问）
```

#### 2.3 上下文隔离
三层MicroAgent：
- Level 1: 主任务循环（ReAct）
- Level 2: 单步执行（定位+操作）
- Level 3: 渐进式定位

每层独立历史，不会污染主循环。

## 📋 使用指南

### 基本使用

```python
from agentmatrix.core.loader import AgentLoader

# 1. 加载BrowserExpert agent
loader = AgentLoader()
agent = loader.load_from_file("path/to/browser_agent.yml")

# 2. 注入browser_adapter和brain_with_vision
from agentmatrix.core.browser.drission_page_adapter import DrissionPageAdapter

browser = DrissionPageAdapter(profile_path="./chrome_profile")
await browser.start(headless=False)

agent.browser_adapter = browser
agent.brain_with_vision = your_vision_llm_client  # 需要支持视觉的LLM

# 3. 执行任务
result = await agent.browser_research("登录Gmail并发送邮件")
print(result)
```

### 配置要求

1. **浏览器适配器**: 任何实现了BrowserAdapter接口的适配器（已提供DrissionPageAdapter）

2. **Vision LLM**: 支持图片输入的大模型，如：
   - GPT-4o / GPT-4V
   - Claude 3.5 Sonnet
   - Gemini Pro Vision

3. **LLM Client接口**: 需要实现`think_with_image(messages, image)`方法

### 示例任务

```python
# 简单任务
await agent.browser_research("在Google搜索'Python教程'")

# 复杂任务
await agent.browser_research("""
登录Amazon，搜索iPhone 15，
查看前3个商品的价格，并加入购物车
""")

# 表单填写
await agent.browser_research("""
打开注册页面，填写以下信息：
- 用户名: testuser
- 邮箱: test@example.com
- 密码: password123
""")
```

## 🔧 已完成的 Vision LLM 集成

### think_with_image 方法实现

**文件**: `src/agentmatrix/backends/llm_client.py:284-510`

新增了完整的 `think_with_image()` 方法，支持主流 Vision LLM：

#### 支持的模型
- **OpenAI 格式**: GPT-4V, GPT-4o, Claude 3.5 Sonnet（兼容API）
- **Gemini 格式**: Gemini Pro Vision, Gemini 1.5 Pro

#### 核心功能
```python
async def think_with_image(
    messages: Union[str, List[Dict]],
    image: str,  # base64 编码
    **kwargs
) -> str:
```

#### 自动格式检测
- 通过 URL 或 model_name 自动识别使用哪种 API 格式
- OpenAI 格式: `content = [{"type": "text"}, {"type": "image_url"}]`
- Gemini 格式: `parts = [{"text": ...}, {"inline_data": ...}]`

#### 流式输出支持
- 两个私有方法处理不同的 API 格式：
  - `_think_with_image_openai()` - OpenAI Vision API
  - `_think_with_image_gemini()` - Gemini Vision API

#### 使用示例
```python
# 基本使用
result = await llm_client.think_with_image(
    messages="描述这张图片",
    image=screenshot_base64,
    detail="high"  # 可选：low/high/auto
)

# 在浏览器自动化中使用
screenshot = await browser.capture_screenshot(tab)
answer = await vision_llm.think_with_image(
    messages="页面上有登录按钮吗？它在哪个区域？",
    image=screenshot
)
```

详细使用指南：`docs/think_with_image_usage.md`

## 🔧 需要进一步完善的部分

### 1. 输入操作的完善

`_locate_and_input`目前只实现了框架，需要完善：
- 获取输入框的selector或直接使用element对象
- 调用`type_text()`方法输入文本
- 处理特殊输入（如回车、Tab等）

**建议实现**：
```python
async def _locate_and_input(self, element_description: str, text: str) -> str:
    browser = self._get_browser_adapter()
    tab = await browser.get_tab()

    # 定位元素
    locator_result = await self._vision_locator.locate_element_interactively(
        tab=tab,
        element_description=element_description,
        operation_type="input",
        max_steps=8
    )

    if not locator_result.success:
        return f"定位失败: {locator_result.reason}"

    # 获取底层element并输入
    try:
        chromium_element = locator_result.element.get_element()

        # 方法1: 直接使用element的input方法（如果支持）
        # await asyncio.to_thread(chromium_element.input, text, clear=True)

        # 方法2: 使用browser_adapter的type_text
        # 需要获取selector
        tag = await asyncio.to_thread(lambda: chromium_element.tag)
        attrs = await asyncio.to_thread(lambda: chromium_element.attrs)

        # 尝试通过唯一属性定位
        if 'name' in attrs:
            selector = f'{tag}[name="{attrs["name"]}"]'
        elif 'id' in attrs and attrs['id']:
            selector = f'#{attrs["id"]}'
        else:
            # 使用XPath或其他方式
            selector = None

        if selector:
            success = await browser.type_text(tab, selector, text)
            if success:
                return f"✓ 在 {element_description} 中输入了: {text}"
            else:
                return f"输入失败"

    except Exception as e:
        return f"输入操作失败: {str(e)}"
```

### 2. 错误恢复机制

虽然设计了"自然恢复"，但可以进一步增强：
- **显式错误检测**: 检测error messages, toast notifications等
- **状态回退**: 自动回退到上一个稳定状态
- **智能重试**: 指数退避 + 替代策略

**建议增强**：
```python
async def _detect_page_errors(self, tab) -> Optional[str]:
    """检测页面错误"""
    # 检查常见的error message
    error_selectors = [
        '.error-message', '.alert-error',
        '[role="alert"]', '.toast-error'
    ]

    for selector in error_selectors:
        error_elem = await browser.find_element(tab, selector, timeout=0.5)
        if error_elem:
            text = await asyncio.to_thread(lambda: error_elem.get_element().text)
            if text:
                return text

    return None
```

### 3. 性能优化

- **元素缓存**: 缓存页面元素（减少重复扫描）
- **并行Vision请求**: 批量确认元素时并行处理
- **智能截图**: 只在状态变化时截图

**建议实现**：
```python
class ElementCache:
    def __init__(self, ttl_seconds=10):
        self.cache = {}
        self.ttl = ttl_seconds

    async def get_elements(self, tab, browser):
        cache_key = id(tab)
        cached = self.cache.get(cache_key)

        if cached and time.time() - cached['timestamp'] < self.ttl:
            return cached['elements']

        # 重新扫描
        links, buttons = await browser.scan_elements(tab)
        all_elements = {**links, **buttons}

        self.cache[cache_key] = {
            'elements': all_elements,
            'timestamp': time.time()
        }

        return all_elements
```

### 4. 测试和调试

建议添加：
- **详细执行日志**: 每个步骤的截图、Vision回答、操作结果
- **可视化调试工具**: 显示定位路径、区域划分
- **单元测试**: 模拟Vision回答，测试定位逻辑

**示例测试**：
```python
import pytest

async def test_vision_locator_with_mock_vision():
    # Mock Vision LLM
    class MockVision:
        async def think_with_image(self, messages, image):
            # 模拟固定回答
            if "初始" in messages:
                return "左上"
            elif "象限" in messages:
                return "上"
            else:
                return "1"

    locator = IntelligentVisionLocator(browser, MockVision())

    # 测试定位流程
    result = await locator.locate_element_interactively(
        tab, "登录按钮", "click"
    )

    assert result.success is True
    assert len(result.steps_taken) > 0
```

## 🎯 技术亮点总结

1. **智能决策**: 利用"元素被线穿过"的信息，避免盲目细分
2. **动态分块**: 根据元素实际分布计算分块点
3. **上下文隔离**: 多层MicroAgent确保定位过程不污染主循环
4. **自适应停止**: 根据区域大小和元素数量智能判断停止时机
5. **自然恢复**: Vision看到新页面自然判断下一步，无需显式错误处理

## 📝 设计文档

参见：`docs/browser-automation-design.md`（待创建）

## 🐛 已知限制

1. **Vision依赖**: 强依赖Vision LLM的理解能力，复杂页面可能出错
2. **速度**: 多轮截图+Vision调用，速度较慢
3. **成本**: Vision API调用频繁，成本较高
4. **动态内容**: 页面内容动态变化时可能需要重新定位

## 🚀 未来扩展方向

1. **学习机制**: 记录常见页面的元素位置，加速后续定位
2. **多模态**: 结合DOM结构信息和视觉理解，提高准确性
3. **并行处理**: 多个浏览器同时工作，提高吞吐量
4. **知识库**: 积累常见网站的操作模式，形成知识库

---

**实现日期**: 2026-02-05
**版本**: v0.1.0
**作者**: Claude Code + 用户协同开发
