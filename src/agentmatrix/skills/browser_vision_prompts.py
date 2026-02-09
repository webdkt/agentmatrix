"""
浏览器视觉定位的Prompt模板

定义各类Vision LLM询问的prompt模板，确保一致性和有效性。
"""

# 初始十字划分询问
INITIAL_CROSSHAIR_PROMPT = """我正在寻找页面上的一个元素，描述如下：{element_description}

页面上有十字坐标线将页面分成四个区域。请仔细观察并告诉我这个目标元素：

1. 如果能明确分辨在哪个象限，请回答：左上、右上、左下、右下
2. 如果元素恰好被竖线穿过（你无法区分是左边还是右边），请回答：左 或 右
3. 如果元素恰好被横线穿过（你无法区分是上边还是下边），请回答：上 或 下
4. 如果元素就在十字交叉的正中间，请回答：中间

重要：只回答上述关键词中的一个，不要有其他内容。"""

# 象限内询问（递归使用）
QUADRANT_PROMPT = """我们在{quadrant_name}象限内寻找：{element_description}

该象限内也有十字坐标线将其进一步细分。请告诉我：

1. 如果能明确分辨在哪个子象限，请回答：左上、右上、左下、右下
2. 如果元素被竖线穿过，请回答：左 或 右
3. 如果元素被横线穿过，请回答：上 或 下
4. 如果元素在正中间，请回答：中间

只回答关键词。"""

# 动态分块询问
DYNAMIC_DIVIDE_PROMPT = """我正在寻找：{element_description}

页面已经按{axis_name}方向分成了{num_divisions}块，每块都有彩色标签：
{division_labels}

请仔细观察这些分块，告诉我目标元素在第几块？

回答格式：只回答数字（如"1"、"2"、"3"等），不要有其他内容。"""

# 候选元素确认
ELEMENT_CONFIRM_PROMPT = """我正在寻找：{element_description}

页面上有{num_elements}个元素被加亮，每个都有数字标签（1、2、3...）。

请仔细观察这些加亮的元素，告诉我：

1. 如果目标元素在其中，请回答它的数字标签（如"1"、"2"等）
2. 如果加亮的元素中没有目标，请回答"没有"

注意：只回答数字或"没有"，不要有其他解释。"""

# 方向精调询问
REFINE_DIRECTION_PROMPT = """我正在寻找：{element_description}

当前加亮的元素（红色边框）可能是目标，但不太确定。请告诉我：

目标元素相对于当前加亮元素的位置：
- 回答"上面"、"下面"、"左边"、"右边"表示方向
- 回答"就是它"表示这就是目标
- 回答"都不是"表示目标不在这里

只回答上述关键词。"""

# 页面分析prompt
PAGE_ANALYSIS_PROMPT = """请分析当前页面的截图，回答以下问题：

1. **这是什么页面？**
   - 页面标题是什么？
   - 主要功能是什么？（如登录页、搜索页、商品页等）

2. **页面上有哪些主要的可交互元素？**
   - 列出你看到的按钮、链接、输入框等
   - 简要说明每个元素的作用（如果可能）

3. **如果要完成任务，下一步应该做什么操作？**
   - 具体说明操作类型（点击/输入/滚动）
   - 说明操作目标（如"点击登录按钮"、"在搜索框输入..."）

当前URL: {current_url}

请简洁清晰地回答，重点说明第3点。"""

# ReAct循环思考prompt
REACT_THINK_PROMPT = """你正在执行浏览器任务：{overall_task}

**已完成步骤：**
{completed_steps}

**当前页面状态：**
{page_state}

**当前页面截图：**
[截图已提供]

请思考：
1. 当前任务进度如何？任务完成了吗？
2. 下一步应该做什么操作？（点击/输入/滚动/查看其他部分）
3. 具体要操作哪个元素？如何描述它？

请简洁说明你的思考和下一步计划。"""


def get_initial_crosshair_prompt(element_description: str) -> str:
    """获取初始十字划分prompt"""
    return INITIAL_CROSSHAIR_PROMPT.format(element_description=element_description)


def get_quadrant_prompt(element_description: str, quadrant_name: str) -> str:
    """获取象限内询问prompt"""
    return QUADRANT_PROMPT.format(
        element_description=element_description,
        quadrant_name=quadrant_name
    )


def get_dynamic_divide_prompt(
    element_description: str,
    axis_name: str,
    num_divisions: int,
    division_labels: str
) -> str:
    """获取动态分块询问prompt"""
    return DYNAMIC_DIVIDE_PROMPT.format(
        element_description=element_description,
        axis_name=axis_name,
        num_divisions=num_divisions,
        division_labels=division_labels
    )


def get_element_confirm_prompt(element_description: str, num_elements: int) -> str:
    """获取元素确认prompt"""
    return ELEMENT_CONFIRM_PROMPT.format(
        element_description=element_description,
        num_elements=num_elements
    )


def get_refine_direction_prompt(element_description: str) -> str:
    """获取方向精调prompt"""
    return REFINE_DIRECTION_PROMPT.format(element_description=element_description)


def get_page_analysis_prompt(current_url: str) -> str:
    """获取页面分析prompt"""
    return PAGE_ANALYSIS_PROMPT.format(current_url=current_url)


def get_react_think_prompt(
    overall_task: str,
    completed_steps: str,
    page_state: str
) -> str:
    """获取ReAct循环思考prompt"""
    return REACT_THINK_PROMPT.format(
        overall_task=overall_task,
        completed_steps=completed_steps,
        page_state=page_state
    )
