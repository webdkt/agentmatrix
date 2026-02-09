# 边界探测法设计文档（Boundary Detection with Crosshair）

## 概述

本文档描述了基于边界探测的视觉元素定位方法。与传统的象限选择法不同，该方法通过逐步探测元素的边界范围，精确定位页面元素。

**使用场景：**
- ✅ **适用**：定位可互动元素（按钮、链接、输入框、下拉菜单等可点击元素）
- ❌ **不适用**：查找表格、label、文字、图片等展示性内容（这些需要采用别的策略）

**关键假设：**
- 可互动元素数量通常较少（一个页面的可点击元素通常在10-50个范围内）
- 通过边界过滤，可以快速将候选范围缩小到少数几个元素

**核心思想：**
- ❌ 旧方法（象限选择）：画十字线 → 问元素在哪个象限 → 选择子区域递归 → 越到后面截图越小，丢失上下文
- ✅ 新方法（边界探测）：画十字线 → 问元素相对线的位置 → 缩小边界区间 → 移动线继续探测 → 每次全屏截图，保留完整上下文 → **每次更新后过滤候选元素，≤5个时提前终止**

## 核心设计：区间跟踪

### 为什么需要区间跟踪？

在探测过程中，我们得到的不是**精确值**，而是**约束条件**。因此需要跟踪每个边界的可能范围。

### 探测示例

假设页面大小 1920x1080，元素位置未知：

```
初始状态：
  x_left ∈ [0, 1920]
  x_right ∈ [0, 1920]
  y_top ∈ [0, 1080]
  y_bottom ∈ [0, 1080]

第1次：在 x=960, y=540 画十字线
  回答：左边，穿过
  更新：
    x_right_max = min(1920, 960) = 960
    y_top_max = min(1080, 540) = 540
    y_bottom_min = max(0, 540) = 540
  结果：
    x_left ∈ [0, 1920]
    x_right ∈ [0, 960]
    y_top ∈ [0, 540]
    y_bottom ∈ [540, 1080]

第2次：在 x=480, y=270 画十字线
  回答：右边，下面
  更新：
    x_left_min = max(0, 480) = 480
    y_top_min = max(0, 270) = 270
  结果：
    x_left ∈ [480, 1920]
    x_right ∈ [0, 960]
    y_top ∈ [270, 540]
    y_bottom ∈ [540, 1080]

第3次：在 x=720, y=405 画十字线
  回答：穿过，穿过
  更新：
    x_left_max = min(1920, 720) = 720
    x_right_min = max(0, 720) = 720
    y_top_max = min(540, 405) = 405
    y_bottom_min = max(540, 405) = 540
  结果：
    x_left ∈ [480, 720]      （范围 240px）
    x_right ∈ [720, 960]     （范围 240px）
    y_top ∈ [270, 405]       （范围 135px）
    y_bottom ∈ [540, 1080]   （范围 540px）

第4次：继续探测 y_bottom...
重复直到所有区间 < 100px
```

## 数据结构

### BoundaryProbe 类

```python
@dataclass
class BoundaryProbe:
    """边界探测结果 - 使用区间跟踪"""

    # X轴左边界
    x_left_min: float = 0.0
    x_left_max: float = 0.0  # 初始化为 viewport_width

    # X轴右边界
    x_right_min: float = 0.0
    x_right_max: float = 0.0  # 初始化为 viewport_width

    # Y轴上边界
    y_top_min: float = 0.0
    y_top_max: float = 0.0  # 初始化为 viewport_height

    # Y轴下边界
    y_bottom_min: float = 0.0
    y_bottom_max: float = 0.0  # 初始化为 viewport_height

    def x_left_range(self) -> float:
        """左边界的不确定范围"""
        return self.x_left_max - self.x_left_min

    def x_right_range(self) -> float:
        """右边界的不确定范围"""
        return self.x_right_max - self.x_right_min

    def y_top_range(self) -> float:
        """上边界的不确定范围"""
        return self.y_top_max - self.y_top_min

    def y_bottom_range(self) -> float:
        """下边界的不确定范围"""
        return self.y_bottom_max - self.y_bottom_min

    def is_precise_enough(self, threshold: float = 100) -> bool:
        """是否足够精确（所有区间都小于阈值）"""
        return (
            self.x_left_range() < threshold and
            self.x_right_range() < threshold and
            self.y_top_range() < threshold and
            self.y_bottom_range() < threshold
        )

    def to_region_bounds(self) -> RegionBounds:
        """转换为区域（取区间的中间值）"""
        x = (self.x_left_min + self.x_left_max) / 2
        y = (self.y_top_min + self.y_top_max) / 2
        width = self.x_right_max - self.x_left_min
        height = self.y_bottom_max - self.y_top_min
        return RegionBounds(x, y, width, height)
```

**关键点：**
- 初始值不是 `[0, inf]`，而是 `[0, viewport_width]` 和 `[0, viewport_height]`
- 每次探测都会缩小区间
- 当所有区间 < 100px 时认为足够精确

## 边界更新逻辑

### 竖线探测（在 x=pos）

| Vision 回答 | 含义 | 更新操作 |
|------------|------|----------|
| 左边 | 元素完全在左边 → 右边界 ≤ pos | `x_right_max = min(x_right_max, pos)` |
| 右边 | 元素完全在右边 → 左边界 ≥ pos | `x_left_min = max(x_left_min, pos)` |
| 穿过 | 左边界 ≤ pos ≤ 右边界 | `x_left_max = min(x_left_max, pos)`<br>`x_right_min = max(x_right_min, pos)` |

### 横线探测（在 y=pos）

| Vision 回答 | 含义 | 更新操作 |
|------------|------|----------|
| 上面 | 元素完全在上面 → 下边界 ≤ pos | `y_bottom_max = min(y_bottom_max, pos)` |
| 下面 | 元素完全在下面 → 上边界 ≥ pos | `y_top_min = max(y_top_min, pos)` |
| 穿过 | 上边界 ≤ pos ≤ 下边界 | `y_top_max = min(y_top_max, pos)`<br>`y_bottom_min = max(y_bottom_min, pos)` |

## 探测流程

### 主流程

```
1. 初始化
   - 获取 viewport_size (width, height)
   - 创建 BoundaryProbe，初始范围为整个视口
   - max_probes = 15（避免无限循环）

2. 循环探测（最多15次）
   for step in range(max_probes):
     a. 计算下一个探测位置
        - 优先探测区间最大的边界
        - 在区间中心画线

     b. 如果所有区间 < 100px
        - 退出循环

     c. 画十字线，截图

     d. 问 Vision 位置
        - "相对竖线：左边/右边/穿过？"
        - "相对横线：上面/下面/穿过？"

     e. 更新边界区间

     f. 清除十字线

3. 获取候选元素
   - boundary.to_region_bounds() → region
   - elements = browser.get_elements_in_bounds(region)

4. 高亮确认
   - 如果只有1个元素 → 直接返回
   - 如果有多个元素 → 高亮让 Vision 选择

5. 返回 LocatorResult
```

### 下一个探测位置计算

```python
def _calculate_next_probe_position(
    self,
    boundary: BoundaryProbe,
    viewport_width: float,
    viewport_height: float
) -> Tuple[Optional[float], Optional[float]]:
    """计算下一个十字线位置"""

    # X轴：探测左边界（在左边界范围的中间）
    if boundary.x_left_range() > 100:
        probe_x = (boundary.x_left_min + boundary.x_left_max) / 2
    # X轴：探测右边界（在右边界范围的中间）
    elif boundary.x_right_range() > 100:
        probe_x = (boundary.x_right_min + boundary.x_right_max) / 2
    else:
        probe_x = None  # X轴已精确，不需要探测

    # Y轴同理
    if boundary.y_top_range() > 100:
        probe_y = (boundary.y_top_min + boundary.y_top_max) / 2
    elif boundary.y_bottom_range() > 100:
        probe_y = (boundary.y_bottom_min + boundary.y_bottom_max) / 2
    else:
        probe_y = None  # Y轴已精确

    return probe_x, probe_y
```

**策略：**
- 优先探测不确定性最大的边界（区间最大的）
- 在区间中心探测，效率最高（二分法）

## 实现方法

### 1. locate_element_interactively（重写）

```python
async def locate_element_interactively(
    self,
    tab: TabHandle,
    element_description: str,
    operation_type: str = "click",
    max_steps: int = 15
) -> LocatorResult:
    """边界探测法主流程"""

    steps = []

    # 1. 初始化
    viewport_size = await asyncio.to_thread(lambda: tab.rect.size)
    boundary = BoundaryProbe(
        x_left_max=viewport_size[0],
        x_right_max=viewport_size[0],
        y_top_max=viewport_size[1],
        y_bottom_max=viewport_size[1]
    )

    # 2. 循环探测
    for step_num in range(max_steps):
        # 2a. 检查是否足够精确
        if boundary.is_precise_enough():
            steps.append(f"边界已精确: X({boundary.x_left_range():.0f}, {boundary.x_right_range():.0f}) Y({boundary.y_top_range():.0f}, {boundary.y_bottom_range():.0f})")
            break

        # 2b. 计算下一个探测位置
        probe_x, probe_y = self._calculate_next_probe_position(
            boundary, viewport_size[0], viewport_size[1]
        )

        if probe_x is None and probe_y is None:
            steps.append("所有边界已精确")
            break

        # 2c. 画十字线并探测
        await self.browser.draw_crosshair_at(tab, probe_x, probe_y)
        await asyncio.sleep(0.3)

        screenshot = await self.browser.capture_screenshot(tab)
        x_answer, y_answer = await self._ask_vision_about_crosshair(
            screenshot, element_description, probe_x, probe_y
        )

        steps.append(f"探测({probe_x:.0f}, {probe_y:.0f}): X={x_answer}, Y={y_answer}")

        # 2d. 更新边界
        self._update_boundary(boundary, probe_x, probe_y, x_answer, y_answer)

        # 2e. 过滤候选元素（关键优化！）
        candidates = await self._filter_candidates_by_boundary(
            tab, boundary, element_description
        )

        steps.append(f"当前边界范围内有 {len(candidates)} 个可点击候选元素")

        # 如果候选元素足够少，直接让 Vision 选择
        if len(candidates) <= 5:
            steps.append(f"候选元素≤5个，提前终止探测")
            await self.browser.remove_crosshair(tab)
            return await self._highlight_and_select_element(
                tab, candidates, element_description, steps
            )

        # 2f. 清除十字线
        await self.browser.remove_crosshair(tab)

    # 3. 没有提前终止，使用最终边界获取元素
    region = boundary.to_region_bounds()
    elements = await self.browser.get_elements_in_bounds(tab, region)

    if not elements:
        return LocatorResult(
            element=None,
            success=False,
            reason=f"边界区域内没有找到元素",
            steps_taken=steps
        )

    # 4. 高亮确认
    return await self._highlight_and_select_element(
        tab, elements, element_description, steps
    )
```

### 2. _ask_vision_about_crosshair

```python
async def _ask_vision_about_crosshair(
    self,
    screenshot_base64: str,
    element_description: str,
    probe_x: float,
    probe_y: float
) -> Tuple[str, str]:
    """询问 Vision 元素相对十字线的位置"""

    from .parser_utils import multi_section_parser

    prompt = f"""我正在寻找页面上的一个元素：{element_description}

页面上有两条线，一条竖线一条横线，

请告诉我目标元素相对这两条线的位置：

对于竖线：
- 如果元素整体完全在竖线左边，回答"左边"
- 如果元素整体完全在竖线右边，回答"右边"
- 如果竖线穿过元素或者看起来非常接近难以分辨，回答"穿过"
- 如果没发现元素，回答"未发现"


对于横线：
- 如果元素整体完全在横线上方，回答"上面"
- 如果元素完全在横线下方，回答"下面"
- 如果横线穿过元素或者看起来非常接近难以分辨，回答"穿过"
- 如果没发现元素，回答"未发现"

按下面格式输出你的判断：
```
[竖线位置]
（在这里填写"左边"、"右边"或"穿过"，或者”未发现“）

[横线位置]
（在这里填写"上面"、"下面"或"穿过"，或者”未发现“）
```
"""

    # 使用 look_and_retry + multi_section_parser
    result = await self.vision.look_and_retry(
        prompt=prompt,
        image=screenshot_base64,
        parser=multi_section_parser,
        section_headers=["[竖线位置]", "[横线位置]"],
        max_retries=3
    )

    x_answer = result.get("[竖线位置]", "").strip()
    y_answer = result.get("[横线位置]", "").strip()

    # 验证答案
    valid_x = ["左边", "右边", "穿过","未发现"]
    valid_y = ["上面", "下面", "穿过","未发现"]

    if x_answer not in valid_x:
        self.logger.warning(f"无效的X轴回答: {x_answer}，默认为'穿过'")
        x_answer = "穿过"

    if y_answer not in valid_y:
        self.logger.warning(f"无效的Y轴回答: {y_answer}，默认为'穿过'")
        y_answer = "穿过"

    return x_answer, y_answer
```

### 3. _update_boundary

```python
def _update_boundary(
    self,
    boundary: BoundaryProbe,
    probe_x: float,
    probe_y: float,
    x_answer: str,
    y_answer: str
) -> None:
    """根据探测结果更新边界区间"""

    # 更新X轴
    if x_answer == "左边":
        # 右边界 ≤ probe_x
        boundary.x_right_max = min(boundary.x_right_max, probe_x)
    elif x_answer == "右边":
        # 左边界 ≥ probe_x
        boundary.x_left_min = max(boundary.x_left_min, probe_x)
    elif x_answer == "穿过":
        # 左边界 ≤ probe_x ≤ 右边界
        boundary.x_left_max = min(boundary.x_left_max, probe_x)
        boundary.x_right_min = max(boundary.x_right_min, probe_x)

    # 更新Y轴
    if y_answer == "上面":
        # 下边界 ≤ probe_y
        boundary.y_bottom_max = min(boundary.y_bottom_max, probe_y)
    elif y_answer == "下面":
        # 上边界 ≥ probe_y
        boundary.y_top_min = max(boundary.y_top_min, probe_y)
    elif y_answer == "穿过":
        # 上边界 ≤ probe_y ≤ 下边界
        boundary.y_top_max = min(boundary.y_top_max, probe_y)
        boundary.y_bottom_min = max(boundary.y_bottom_min, probe_y)
```

### 4. _filter_candidates_by_boundary（关键优化）

```python
async def _filter_candidates_by_boundary(
    self,
    tab: TabHandle,
    boundary: BoundaryProbe,
    element_description: str
) -> List[PageElement]:
    """根据边界过滤可点击候选元素"""

    # 1. 获取所有可点击元素
    all_clickable = await self.browser.get_all_clickable_elements(tab)

    # 2. 过滤：元素必须在边界范围内
    candidates = []
    for elem in all_clickable:
        # 获取元素位置
        rect = await self.browser.get_element_rect(tab, elem)

        # 检查元素是否与边界相交
        if self._is_intersect_boundary(rect, boundary):
            candidates.append(elem)

    return candidates


def _is_intersect_boundary(
    self,
    elem_rect: dict,  # {'x': x, 'y': y, 'width': w, 'height': h}
    boundary: BoundaryProbe
) -> bool:
    """检查元素是否与边界区间相交"""

    elem_x = elem_rect['x']
    elem_y = elem_rect['y']
    elem_w = elem_rect['width']
    elem_h = elem_rect['height']
    elem_right = elem_x + elem_w
    elem_bottom = elem_y + elem_h

    # 元素的任何部分在边界范围内即可
    # X轴：元素的右边界 >= boundary.x_left_min 且元素的左边界 <= boundary.x_right_max
    x_intersect = (elem_right >= boundary.x_left_min and
                   elem_x <= boundary.x_right_max)

    # Y轴：元素的下边界 >= boundary.y_top_min 且元素的上边界 <= boundary.y_bottom_max
    y_intersect = (elem_bottom >= boundary.y_top_min and
                   elem_y <= boundary.y_bottom_max)

    return x_intersect and y_intersect
```

**关键优化点：**
- 每次更新边界后立即过滤候选元素
- 使用"相交"判断而非"包含"（元素只要部分在范围内即可）
- 当候选元素 ≤ 5个时，提前终止探测，直接让 Vision 选择
- 可以显著减少 Vision 调用次数（运气好只需2-3次探测）

**为什么是5个？**
- 1-5个元素：高亮后 Vision 可以轻松选择
- 超过5个：选择困难，继续探测更高效

### 5. _highlight_and_select_element

```python
async def _highlight_and_select_element(
    self,
    tab: TabHandle,
    elements: List[PageElement],
    element_description: str,
    steps: List[str]
) -> LocatorResult:
    """高亮候选元素并让 Vision 选择"""

    if len(elements) == 1:
        steps.append("只有1个候选元素，直接定位")
        return LocatorResult(
            element=elements[0],
            success=True,
            reason="成功定位目标元素",
            steps_taken=steps
        )

    steps.append(f"有{len(elements)}个候选元素，让Vision选择")

    # 高亮所有候选元素
    for i, element in enumerate(elements):
        await self.browser.highlight_element(tab, element, color="red", label=str(i+1))

    await asyncio.sleep(0.5)
    screenshot = await self.browser.capture_screenshot(tab)

    # 让 Vision 选择
    selected_idx = await self._ask_vision_select_element(
        screenshot, element_description, len(elements)
    )

    # 清除高亮
    await self.browser.remove_highlights(tab)

    if selected_idx is not None and 0 <= selected_idx < len(elements):
        steps.append(f"Vision选择了第{selected_idx+1}个元素")
        return LocatorResult(
            element=elements[selected_idx],
            success=True,
            reason="成功定位目标元素",
            steps_taken=steps
        )

    # 选择失败，返回第一个
    steps.append("Vision选择失败，返回第一个候选元素")
    return LocatorResult(
        element=elements[0],
        success=True,
        reason="返回第一个候选元素",
        steps_taken=steps
    )
```

## 关键优势

### 1. 保留完整上下文
- **旧方法**：越到后面区域越小，截图中丢失 label、icon 等关联信息
- **新方法**：每次都是全屏截图，Vision 能看到完整的元素上下文

### 2. 不会丢失元素
- **旧方法**：选择象限可能截断长元素（如导航栏、banner）
- **新方法**：通过探测得到真实边界范围，不会截断

### 3. 逻辑清晰
- **旧方法**：递归分割，状态复杂
- **新方法**：逐步逼近边界，每次探测都有明确的物理意义

### 4. 精度可控
- 通过区间范围直接判断是否足够精确
- 可以动态调整停止条件（如 50px, 100px）

### 5. 提前终止机制（关键优化！）
- **传统方法**：必须等到边界足够精确才能获取元素
- **新方法**：每次更新边界后立即过滤候选元素
- **优势**：当候选元素 ≤ 5个时提前终止，直接让 Vision 选择
- **效果**：运气好只需 2-3 次探测就能定位（而不是必须到 6-12 次）

## 预期效果

### 性能指标
- **最佳情况**：2-3 次探测（运气好，候选元素很快 ≤ 5个）
- **平均情况**：4-8 次探测（大多数场景）
- **最坏情况**：10-15 次探测（元素很多或边界复杂）
- **精度**：±50px（所有区间 < 100px）
- **成功率**：预期显著高于旧方法

### 成本考虑
- 每次 Vision 调用：同时获得 X 和 Y 信息
- 可使用便宜模型（如 GPT-4o-mini, GLM-4V-flash）
- 可部署本地模型（如 LLaVA）降低成本

## 测试计划

### 测试场景
1. **简单场景**：搜索框（明确、居中的元素）
2. **边缘场景**：小按钮、边缘元素
3. **复杂场景**：多个相似元素、半透明元素

### 测试方法
使用 `tests/ai_browse/test_real_baidu_interactive.py` 进行互动式测试

## 文件修改清单

### 需要修改的文件
1. `/Users/frwang/myprojects/agentmatrix/src/agentmatrix/skills/browser_vision_locator.py`
   - 添加 BoundaryProbe 类
   - 重写 locate_element_interactively
   - 新增探测相关方法

2. `/Users/frwang/myprojects/agentmatrix/src/agentmatrix/core/browser/drission_page_adapter.py`
   - 确认 `draw_crosshair_at` 方法支持任意位置（已有 `draw_crosshair(tab, region)` 可能需要增强）
   - 新增 `get_all_clickable_elements(tab)` 方法
   - 新增 `get_element_rect(tab, element)` 方法（或确认已有）

### 需要确认的依赖
- `parser_utils.py` 中是否有 `multi_section_parser`
- 如果没有，需要新增

## 后续优化方向

1. **自适应探测策略**：根据区间大小动态调整探测位置
2. **成本优化**：根据探测阶段选择不同的 Vision 模型
3. **并行探测**：如果支持，可以同时探测多个位置
4. **缓存机制**：缓存页面结构信息，加速后续定位
