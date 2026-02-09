"""
智能视觉定位器

通过渐进式视觉理解，自适应地定位页面上的元素。
核心创新：利用十字坐标线和Vision LLM的交互，根据"元素被线穿过"的信息智能划分区域。
"""

import asyncio
from typing import Optional, List, Tuple
from dataclasses import dataclass

from .browser_vision_divider import SmartRegionDivider, RegionBounds
from ..core.browser.browser_adapter import PageElement, TabHandle


@dataclass
class LocatorResult:
    """定位结果"""
    element: Optional[PageElement]
    success: bool
    reason: str
    steps_taken: List[str]


@dataclass
class BoundaryProbe:
    """边界探测结果 - 使用区间跟踪

    跟踪元素边界的可能范围，每次探测缩小区间。
    """
    # X轴左边界
    x_left_min: float = 0.0
    x_left_max: float = 0.0

    # X轴右边界
    x_right_min: float = 0.0
    x_right_max: float = 0.0

    # Y轴上边界
    y_top_min: float = 0.0
    y_top_max: float = 0.0

    # Y轴下边界
    y_bottom_min: float = 0.0
    y_bottom_max: float = 0.0

    def __post_init__(self):
        """初始化时确保 max >= min"""
        if self.x_left_max < self.x_left_min:
            self.x_left_max = self.x_left_min
        if self.x_right_max < self.x_right_min:
            self.x_right_max = self.x_right_min
        if self.y_top_max < self.y_top_min:
            self.y_top_max = self.y_top_min
        if self.y_bottom_max < self.y_bottom_min:
            self.y_bottom_max = self.y_bottom_min

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
        """转换为区域（取区间的扩展范围）"""
        x = self.x_left_min
        y = self.y_top_min
        width = self.x_right_max - self.x_left_min
        height = self.y_bottom_max - self.y_top_min
        return RegionBounds(x, y, width, height)


class IntelligentVisionLocator:
    """
    智能视觉定位器

    负责通过Vision LLM的视觉理解能力，渐进式地定位页面元素。
    """

    def __init__(self, browser_adapter, brain_with_vision):
        """
        初始化定位器

        Args:
            browser_adapter: 浏览器适配器实例
            brain_with_vision: 支持视觉的LLM客户端
        """
        self.browser = browser_adapter
        self.vision = brain_with_vision
        self.divider = SmartRegionDivider()

    async def locate_element_interactively(
        self,
        tab: TabHandle,
        element_description: str,
        operation_type: str = "click",
        max_steps: int = 15
    ) -> LocatorResult:
        """
        边界探测法主流程

        核心逻辑：
        1. 初始化边界范围为整个视口
        2. 循环探测：画十字线 → 询问Vision → 更新边界 → 过滤候选元素
        3. 当候选元素 ≤ 5个时，提前终止并让Vision选择
        4. 当边界足够精确（<100px）或达到最大步数时停止

        Args:
            tab: 浏览器标签页
            element_description: 目标元素的描述
            operation_type: 操作类型 (暂未使用，保留扩展性)
            max_steps: 最大探测步数限制

        Returns:
            LocatorResult: 定位结果
        """
        import logging
        logger = logging.getLogger(__name__)

        steps = []

        try:
            # 1. 初始化
            # 获取真实的视口大小（使用JavaScript）
            get_viewport_js = "return { width: window.innerWidth, height: window.innerHeight }"
            viewport_result = await asyncio.to_thread(tab.run_js, get_viewport_js)
            viewport_size = (viewport_result['width'], viewport_result['height'])

            boundary = BoundaryProbe(
                x_left_max=viewport_size[0],
                x_right_max=viewport_size[0],
                y_top_max=viewport_size[1],
                y_bottom_max=viewport_size[1]
            )

            print(f"\n{'='*80}")
            print(f"🔍 边界探测初始化")
            print(f"{'='*80}")
            print(f"📐 检测到的窗口大小: {viewport_size[0]} x {viewport_size[1]} 像素")
            print(f"📊 初始边界状态:")
            print(f"   X左边界: [{boundary.x_left_min:.0f}, {boundary.x_left_max:.0f}] (范围: {boundary.x_left_range():.0f})")
            print(f"   Y上边界: [{boundary.y_top_min:.0f}, {boundary.y_top_max:.0f}] (范围: {boundary.y_top_range():.0f})")
            print(f"{'='*80}\n")

            steps.append(f"开始边界探测，视口大小: {viewport_size[0]}x{viewport_size[1]}")

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
                    steps.append("所有边界已精确，停止探测")
                    break

                # 2c. 画十字线并探测
                if probe_x is not None and probe_y is not None:
                    # 十字探测
                    print(f"\n{'='*80}")
                    print(f"🎨 准备画十字线")
                    print(f"{'='*80}")
                    print(f"📍 将要在位置 ({probe_x:.0f}, {probe_y:.0f}) 画十字线")
                    print(f"   竖线位置: {probe_x:.0f}px (从左边缘)")
                    print(f"   横线位置: {probe_y:.0f}px (从上边缘)")
                    print(f"{'='*80}\n")

                    logger.info(f"在({probe_x:.0f}, {probe_y:.0f})位置画十字线")
                    await self.browser.draw_crosshair_at(tab, probe_x, probe_y)
                    # 等待线渲染完成
                    await asyncio.sleep(0.5)
                else:
                    # 单线探测暂不支持
                    logger.warning("单线探测暂不支持")
                    break

                screenshot = await self.browser.capture_screenshot(tab)

                # 根据画的线类型选择询问方式
                if probe_x is not None and probe_y is not None:
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
                    # 清除坐标线
                    await self.browser.remove_crosshair(tab)

                    return await self._highlight_and_select_element(
                        tab, candidates, element_description, steps
                    )

                # 2f. 清除坐标线
                await self.browser.remove_crosshair(tab)

            # 3. 没有提前终止，使用最终边界获取元素
            region = boundary.to_region_bounds()
            elements = await self.browser.get_elements_in_bounds(tab, region)

            if not elements:
                return LocatorResult(
                    element=None,
                    success=False,
                    reason=f"边界区域内没有找到元素({region.width:.0f}x{region.height:.0f})",
                    steps_taken=steps
                )

            steps.append(f"最终边界区域有{len(elements)}个元素")

            # 4. 高亮确认
            return await self._highlight_and_select_element(
                tab, elements, element_description, steps
            )

        except Exception as e:
            logger.exception(f"定位过程出错: {e}")
            return LocatorResult(
                element=None,
                success=False,
                reason=f"定位过程出错: {str(e)}",
                steps_taken=steps
            )

    async def _ask_vision_about_division(
        self,
        screenshot_base64: str,
        element_description: str,
        valid_answers: List[str],
        division_type: str
    ) -> str:
        """
        询问Vision LLM元素在哪个区域

        Args:
            screenshot_base64: base64编码的截图
            element_description: 元素描述
            valid_answers: 有效答案列表
            division_type: 分割类型 ("十字分", "垂直分", "水平分")

        Returns:
            str: Vision的回答（从valid_answers中选择一个）
        """
        from .parser_utils import simple_section_parser

        # 构建 valid_answers 的描述文本
        if len(valid_answers) == 1:
            answers_text = valid_answers[0]
        else:
            answers_text = "、".join(valid_answers[:-1]) + f"或{valid_answers[-1]}"

        # 根据分割类型选择不同的 prompt
        if division_type == "十字分":
            prompt = f"""我正在寻找页面上的一个元素：{element_description}

页面上有十字坐标线将页面分成四个象限。根据元素是否完整的位于某个象限，告诉我元素的位置：
* 如果元素完全属于某个象限，回答该区域的名称（如"左上"、"右下" 等）
* 如果元素跨越多个象限，但是完全的在水平线或者垂直线的某一侧，可以区分是属于左或者右，上或者下，就回答"左"、"右"、"上"或"下"之一
* 如果看不出来，回答"不存在"
* 如果元素在中间位置，跨越分割线，无法明确区分区域，就回答"中间"

输出格式：
```
（可选）尽量简短的说明，可以没有
[位置]
（在这里填写你的答案，只选一个：{answers_text}）
```
"""
        elif division_type == "垂直分":
            prompt = f"""我正在寻找页面上的一个元素：{element_description}

页面上有一条垂直坐标线将页面分成左右两个区域。根据元素是否完整的位于某个区域，告诉我元素的位置：
* 如果元素完全属于某个区域，回答该区域的名称（如"左"、"右"）
* 如果看不出来，回答"不存在"
* 如果元素在中间位置，跨越坐标线，不完全属于某个区域，就回答"中间"

输出格式：
```
（可选）尽量简短的说明，可以没有
[位置]
（在这里填写你的答案，只选一个：{answers_text}）
```
"""
        else:  # 水平分
            prompt = f"""我正在寻找页面上的一个元素：{element_description}

页面上有一条水平坐标线将页面分成上下两个区域。根据元素是否完整的位于某个区域，告诉我元素的位置：
* 如果元素完全属于某个区域，回答该区域的名称（如"上"、"下"）
* 如果看不出来，回答"不存在"
* 如果元素在中间位置，跨越坐标线，不完全属于某个区域，就回答"中间"

输出格式：
```
（可选）尽量简短的说明，可以没有
[位置]
（在这里填写你的答案，只选一个：{answers_text}）
```
"""

        # 使用 look_and_retry + parser
        try:
            position = await self.vision.look_and_retry(
                prompt=prompt,
                image=screenshot_base64,
                parser=simple_section_parser,
                section_header="[位置]",
                max_retries=3
            )

            # 验证返回的位置是否有效
            position = position.strip()

            if position in valid_answers:
                return position
            else:
                # 如果 parser 提取的答案不在有效列表中，尝试在文本中查找
                for valid in valid_answers:
                    if valid in position:
                        return valid

                # 都没找到，记录警告并返回"不存在"
                self.logger.warning(f"Vision 返回了无效的位置: {position}，返回'不存在'")
                return "不存在"

        except Exception as e:
            self.logger.exception(f"Vision LLM 调用失败: {e}，返回'不存在'")
            return "不存在"

    def _calculate_sub_region(self, region: RegionBounds, answer: str) -> RegionBounds:
        """
        根据 Vision 的回答计算新的子区域

        Args:
            region: 当前区域边界（绝对坐标，像素）
            answer: Vision 的回答（"左上", "右上", "左下", "右下", "左", "右", "上", "下", "中间"）

        Returns:
            RegionBounds: 新的子区域边界

        Raises:
            ValueError: 如果无法理解的 answer
        """
        # 十字分（4象限）
        if answer in ["左上", "右上", "左下", "右下", "左", "右", "上", "下", "中间"]:
            mid_x = region.x + region.width / 2
            mid_y = region.y + region.height / 2

            if answer == "左上":
                return RegionBounds(region.x, region.y, region.width / 2, region.height / 2)
            elif answer == "右上":
                return RegionBounds(mid_x, region.y, region.width / 2, region.height / 2)
            elif answer == "左下":
                return RegionBounds(region.x, mid_y, region.width / 2, region.height / 2)
            elif answer == "右下":
                return RegionBounds(mid_x, mid_y, region.width / 2, region.height / 2)
            elif answer == "左":
                # 被竖线穿过，返回左边半区域
                return RegionBounds(region.x, region.y, region.width / 2, region.height)
            elif answer == "右":
                # 被竖线穿过，返回右边半区域
                return RegionBounds(mid_x, region.y, region.width / 2, region.height)
            elif answer == "上":
                # 被横线穿过，返回上方半区域
                return RegionBounds(region.x, region.y, region.width, region.height / 2)
            elif answer == "下":
                # 被横线穿过，返回下方半区域
                return RegionBounds(region.x, mid_y, region.width, region.height / 2)
            elif answer == "中间":
                # 中间位置，返回一个中心小区域（用于精细定位）
                center_size = min(region.width, region.height) / 4
                center_x = mid_x - center_size / 2
                center_y = mid_y - center_size / 2
                return RegionBounds(center_x, center_y, center_size, center_size)

        # 垂直2分（左右）
        elif answer in ["左", "右"]:
            mid_x = region.x + region.width / 2
            if answer == "左":
                return RegionBounds(region.x, region.y, region.width / 2, region.height)
            else:  # "右"
                return RegionBounds(mid_x, region.y, region.width / 2, region.height)

        # 水平2分（上下）
        elif answer in ["上", "下"]:
            mid_y = region.y + region.height / 2
            if answer == "上":
                return RegionBounds(region.x, region.y, region.width, region.height / 2)
            else:  # "下"
                return RegionBounds(region.x, mid_y, region.width, region.height / 2)

        else:
            raise ValueError(f"无法理解的 Vision 回答: {answer}")

    async def _confirm_element_by_region(
        self,
        tab: TabHandle,
        element_description: str,
        region: RegionBounds,
        steps: List[str]
    ) -> LocatorResult:
        """
        在指定区域内确认最终目标元素

        Args:
            tab: 浏览器标签页
            element_description: 元素描述
            region: 最终区域边界
            steps: 步骤记录

        Returns:
            LocatorResult: 定位结果
        """
        try:
            # 获取该区域内的所有元素
            elements = await self.browser.get_elements_in_bounds(tab, region)

            if not elements:
                return LocatorResult(
                    element=None,
                    success=False,
                    reason=f"区域内没有找到元素（{region.width:.0f}x{region.height:.0f}）",
                    steps_taken=steps
                )

            # 如果只有一个元素，直接返回
            if len(elements) == 1:
                steps.append(f"区域内只有1个元素，直接定位")
                return LocatorResult(
                    element=elements[0],
                    success=True,
                    reason=f"成功定位目标元素",
                    steps_taken=steps
                )

            # 多个元素，逐一高亮让Vision确认
            steps.append(f"区域内有{len(elements)}个元素，逐一确认")

            for i, element in enumerate(elements):
                await self.browser.highlight_element(tab, element, color="red")
                await asyncio.sleep(0.2)
                await self.browser.remove_highlight(tab, element)

            # 截图并让Vision选择
            screenshot = await self.browser.capture_screenshot(tab)

            # 这里简化处理：返回第一个元素
            # TODO: 可以增加让Vision选择的逻辑
            steps.append(f"返回第一个元素作为候选")
            return LocatorResult(
                element=elements[0],
                success=True,
                reason=f"区域内找到{len(elements)}个元素，返回第一个",
                steps_taken=steps
            )

        except Exception as e:
            self.logger.exception(f"确认元素时出错: {e}")
            return LocatorResult(
                element=None,
                success=False,
                reason=f"确认元素时出错: {str(e)}",
                steps_taken=steps
            )

    async def _confirm_element(
        self,
        tab: TabHandle,
        elements: List[PageElement],
        element_description: str,
        steps: List[str],
        batch_size: int = 5
    ) -> LocatorResult:
        """
        候选元素确认

        Args:
            tab: 浏览器标签页
            elements: 候选元素列表
            element_description: 元素描述
            steps: 步骤记录
            batch_size: 每批加亮的元素数量

        Returns:
            LocatorResult
        """
        if not elements:
            return LocatorResult(
                element=None,
                success=False,
                reason="没有候选元素",
                steps_taken=steps
            )

        # 分批确认
        for i in range(0, len(elements), batch_size):
            batch = elements[i:i+batch_size]
            labels = [str(j+1) for j in range(len(batch))]

            steps.append(f"加亮第{i+1}-{i+len(batch)}个元素")

            await self.browser.highlight_elements(
                tab, batch, color="#00FF00", labels=labels
            )
            await asyncio.sleep(0.5)

            screenshot = await self.browser.capture_screenshot(tab)

            selected_idx = await self._ask_vision_confirm_element(
                screenshot, element_description, len(batch)
            )

            await self.browser.remove_highlights(tab)

            if selected_idx is not None and selected_idx < len(batch):
                steps.append(f"Vision确认了第{i+selected_idx+1}个元素")
                return LocatorResult(
                    element=batch[selected_idx],
                    success=True,
                    reason=f"成功定位到{element_description}",
                    steps_taken=steps
                )

            # 如果这批没有，继续下一批
            steps.append(f"Vision没有在前{i+len(batch)}个元素中找到目标，继续下一批")

        return LocatorResult(
            element=None,
            success=False,
            reason=f"在{len(elements)}个候选元素中未找到目标",
            steps_taken=steps
        )

    async def _ask_vision_confirm_element(
        self,
        screenshot_base64: str,
        element_description: str,
        num_elements: int
    ) -> Optional[int]:
        """
        询问Vision确认哪个元素是目标

        Returns:
            int or None: 元素索引（0-based），如果没有找到返回None
        """
        prompt = f"""我正在寻找：{element_description}

页面上有{num_elements}个元素被加亮，每个都有数字标签（1、2、3...）。

请告诉我目标元素是第几个？（回答数字1-{num_elements}，或者回答"没有"）

如果加亮的元素中没有目标，请回答"没有"。"""

        result = await self.vision.think_with_image(
            messages=[{"role": "user", "content": prompt}],
            image=screenshot_base64
        )

        # 检查是否说"没有"
        if "没有" in result or "none" in result.lower():
            return None

        # 尝试提取数字
        import re
        numbers = re.findall(r'\d+', result)
        if numbers:
            idx = int(numbers[0]) - 1  # 转为0-based
            if 0 <= idx < num_elements:
                return idx

        return None

    # ==================== 边界探测法相关方法 ====================

    async def _filter_candidates_by_boundary(
        self,
        tab: TabHandle,
        boundary: BoundaryProbe,
        element_description: str
    ) -> List[PageElement]:
        """根据边界过滤可点击候选元素

        Args:
            tab: 浏览器标签页
            boundary: 边界探测结果
            element_description: 元素描述（用于日志）

        Returns:
            list: 候选元素列表
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 1. 获取所有可点击元素
            all_clickable = await self.browser.get_all_clickable_elements(tab)

            if not all_clickable:
                logger.warning("没有找到任何可点击元素")
                return []

            print(f"\n{'='*80}")
            print(f"🔍 找到 {len(all_clickable)} 个可点击元素")
            print(f"{'='*80}")

            # 检查是否包含 id="input-root" 的元素
            found_input_root = False
            for elem in all_clickable:
                try:
                    chromium_elem = elem.get_element()
                    elem_id = chromium_elem.attr('id') if chromium_elem else None

                    if elem_id and 'input-root' in str(elem_id).lower():
                        found_input_root = True
                        tag = elem.get_tag_name()
                        print(f"✅ 找到目标元素: <{tag}> id='{elem_id}'")
                        break
                except:
                    continue

            if not found_input_root:
                print(f"⚠️  未找到 id='input-root' 的元素")

            print(f"{'='*80}\n")

            # 2. 过滤：元素必须在边界范围内
            candidates = []
            for elem in all_clickable:
                try:
                    # 获取元素位置
                    rect = await self.browser.get_element_rect(tab, elem)

                    # 检查元素是否与边界相交
                    if self._is_intersect_boundary(rect, boundary):
                        candidates.append(elem)
                except Exception as e:
                    logger.debug(f"获取元素位置失败: {e}")
                    continue

            return candidates

        except Exception as e:
            logger.exception(f"过滤候选元素失败: {e}")
            return []

    def _is_intersect_boundary(
        self,
        elem_rect: dict,
        boundary: BoundaryProbe
    ) -> bool:
        """检查元素是否满足边界条件（4条边都必须在对应范围内）

        Args:
            elem_rect: 元素矩形 {'x': x, 'y': y, 'width': w, 'height': h}
            boundary: 边界探测结果

        Returns:
            bool: 是否满足所有边界条件
        """
        elem_x = elem_rect.get('x', 0)
        elem_y = elem_rect.get('y', 0)
        elem_w = elem_rect.get('width', 0)
        elem_h = elem_rect.get('height', 0)
        elem_right = elem_x + elem_w
        elem_bottom = elem_y + elem_h

        # 检查元素的4条边是否都满足边界条件
        # X轴：左边界必须在 [x_left_min, x_left_max]，右边界必须在 [x_right_min, x_right_max]
        x_valid = (elem_x >= boundary.x_left_min and elem_x <= boundary.x_left_max and
                  elem_right >= boundary.x_right_min and elem_right <= boundary.x_right_max)

        # Y轴：上边界必须在 [y_top_min, y_top_max]，下边界必须在 [y_bottom_min, y_bottom_max]
        y_valid = (elem_y >= boundary.y_top_min and elem_y <= boundary.y_top_max and
                  elem_bottom >= boundary.y_bottom_min and elem_bottom <= boundary.y_bottom_max)

        return x_valid and y_valid

    async def _ask_vision_about_crosshair(
        self,
        screenshot_base64: str,
        element_description: str,
        probe_x: float,
        probe_y: float
    ) -> Tuple[str, str]:
        """询问 Vision 元素相对十字线的位置

        Args:
            screenshot_base64: base64编码的截图
            element_description: 元素描述
            probe_x: 竖线位置
            probe_y: 横线位置

        Returns:
            tuple: (x_answer, y_answer) - X和Y轴的回答
        """
        from .parser_utils import multi_section_parser

        def crosshair_parser(raw_reply: str) -> dict:
            """专门的十字线 parser，支持宽容模式"""
            # 先尝试标准解析
            result = multi_section_parser(
                raw_reply,
                section_headers=["[竖线位置]", "[横线位置]"],
                match_mode="ALL"
            )

            # 如果标准解析成功，直接返回
            if result.get("status") == "success":
                return result

            # 宽容模式：检查是否是两行简短答案
            print(f"⚠️  标准 parser 失败，尝试宽容模式...")

            lines = [line.strip() for line in raw_reply.strip().split('\n') if line.strip()]
            valid_x = ["左边", "右边", "穿过", "未发现"]
            valid_y = ["上面", "下面", "穿过", "未发现"]

            # 尝试提取两行答案
            x_answer = None
            y_answer = None

            for line in lines:
                if line in valid_x:
                    x_answer = line
                elif line in valid_y:
                    y_answer = line

            # 如果成功提取到两个答案
            if x_answer and y_answer:
                print(f"✅ 宽容模式成功: X={x_answer}, Y={y_answer}")
                return {
                    "status": "success",
                    "content": {
                        "[竖线位置]": x_answer,
                        "[横线位置]": y_answer
                    }
                }

            # 宽容模式也失败
            print(f"❌ 宽容模式也失败")
            return result

        prompt = f"""这是一个浏览器页面截图，我正在寻找页面上的一个元素：{element_description}

页面上有一横一竖垂直交叉的两条金色（Gold）坐标线，坐标线贯穿整个页面。

请告诉我目标元素相对这两条坐标线的位置：

相对于垂直的竖线：
- 如果元素**整体完全**在垂直线左边，回答"左边"
- 如果元素**整体完全**在垂直线右边，回答"右边"
- 如果元素**整体在垂直线左右两边都有，或者看起来非常接近难以分辨，回答"穿过"
- 如果没发现元素，回答"未发现"


对于横线：
- 如果元素**整体完全**在横线上方，回答"上面"
- 如果元素**整体完全**在横线下方，回答"下面"
- 如果元素**整体在横线上下两边都有或者看起来非常接近难以分辨，回答"穿过"
- 如果没发现元素，回答"未发现"

按下面格式输出你的判断：
```
[相对垂直竖线位置]
（在这里填写"左边"、"右边"或"穿过"，或者"未发现"）

[相对水平横线位置]
（在这里填写"上面"、"下面"或"穿过"，或者"未发现"）
```
"""

        # 📝 打印发送给 Vision Brain 的 Prompt
        print(f"\n{'='*80}")
        print(f"🧠 发送给 Vision Brain 的 Prompt:")
        print(f"{'='*80}")
        print(prompt)
        print(f"{'='*80}\n")

        try:
            # 使用 look_and_retry + 自定义的 crosshair_parser
            result = await self.vision.look_and_retry(
                prompt=prompt,
                image=screenshot_base64,
                parser=crosshair_parser,
                max_retries=3
            )

            # 📝 打印 Vision Brain 的原始回答
            print(f"\n{'='*80}")
            print(f"💬 Vision Brain 的原始回答:")
            print(f"{'='*80}")
            for key, value in result.items():
                print(f"{key}: {value}")
            print(f"{'='*80}\n")

            x_answer = result.get("[竖线位置]", "").strip()
            y_answer = result.get("[横线位置]", "").strip()

            # 验证答案
            valid_x = ["左边", "右边", "穿过", "未发现"]
            valid_y = ["上面", "下面", "穿过", "未发现"]

            if x_answer not in valid_x:
                import logging
                logging.warning(f"无效的X轴回答: {x_answer}，默认为'穿过'")
                x_answer = "穿过"

            if y_answer not in valid_y:
                import logging
                logging.warning(f"无效的Y轴回答: {y_answer}，默认为'穿过'")
                y_answer = "穿过"

            # 📝 打印最终解析的答案
            print(f"\n{'='*80}")
            print(f"✅ Vision Brain 的最终答案:")
            print(f"{'='*80}")
            print(f"X轴（竖线）: {x_answer}")
            print(f"Y轴（横线）: {y_answer}")
            print(f"{'='*80}\n")

            return x_answer, y_answer

        except Exception as e:
            import logging
            logging.exception(f"Vision LLM 调用失败: {e}，返回'穿过'")
            return "穿过", "穿过"

    def _update_boundary(
        self,
        boundary: BoundaryProbe,
        probe_x: float,
        probe_y: float,
        x_answer: str,
        y_answer: str
    ) -> None:
        """根据探测结果更新边界区间

        Args:
            boundary: 边界探测结果
            probe_x: 竖线位置
            probe_y: 横线位置
            x_answer: X轴回答（"左边"/"右边"/"穿过"）
            y_answer: Y轴回答（"上面"/"下面"/"穿过"）
        """
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
        # "未发现"不更新边界

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
        # "未发现"不更新边界

    def _calculate_next_probe_position(
        self,
        boundary: BoundaryProbe,
        viewport_width: float,
        viewport_height: float
    ) -> Tuple[Optional[float], Optional[float]]:
        """计算下一个十字线位置

        Args:
            boundary: 当前边界探测结果
            viewport_width: 视口宽度
            viewport_height: 视口高度

        Returns:
            tuple: (probe_x, probe_y) - 如果某轴已精确，返回None
        """
        probe_x = None
        probe_y = None

        print(f"\n{'='*80}")
        print(f"🧮 计算下一个探测位置")
        print(f"{'='*80}")

        # X轴：探测左边界（在左边界范围的中间）
        if boundary.x_left_range() > 100:
            probe_x = (boundary.x_left_min + boundary.x_left_max) / 2
            print(f"X轴探测左边界:")
            print(f"   左边界范围: [{boundary.x_left_min:.0f}, {boundary.x_left_max:.0f}]")
            print(f"   计算: ({boundary.x_left_min:.0f} + {boundary.x_left_max:.0f}) / 2 = {probe_x:.0f}")
        # X轴：探测右边界（在右边界范围的中间）
        elif boundary.x_right_range() > 100:
            probe_x = (boundary.x_right_min + boundary.x_right_max) / 2
            print(f"X轴探测右边界:")
            print(f"   右边界范围: [{boundary.x_right_min:.0f}, {boundary.x_right_max:.0f}]")
            print(f"   计算: ({boundary.x_right_min:.0f} + {boundary.x_right_max:.0f}) / 2 = {probe_x:.0f}")
        else:
            probe_x = None  # X轴已精确，不需要探测
            print(f"X轴已精确，不需要探测 (左范围: {boundary.x_left_range():.0f}, 右范围: {boundary.x_right_range():.0f})")

        # Y轴同理
        if boundary.y_top_range() > 100:
            probe_y = (boundary.y_top_min + boundary.y_top_max) / 2
            print(f"Y轴探测上边界:")
            print(f"   上边界范围: [{boundary.y_top_min:.0f}, {boundary.y_top_max:.0f}]")
            print(f"   计算: ({boundary.y_top_min:.0f} + {boundary.y_top_max:.0f}) / 2 = {probe_y:.0f}")
        elif boundary.y_bottom_range() > 100:
            probe_y = (boundary.y_bottom_min + boundary.y_bottom_max) / 2
            print(f"Y轴探测下边界:")
            print(f"   下边界范围: [{boundary.y_bottom_min:.0f}, {boundary.y_bottom_max:.0f}]")
            print(f"   计算: ({boundary.y_bottom_min:.0f} + {boundary.y_bottom_max:.0f}) / 2 = {probe_y:.0f}")
        else:
            probe_y = None  # Y轴已精确
            print(f"Y轴已精确，不需要探测 (上范围: {boundary.y_top_range():.0f}, 下范围: {boundary.y_bottom_range():.0f})")

        print(f"📍 最终探测位置: ({probe_x if probe_x is not None else 'None'}, {probe_y if probe_y is not None else 'None'})")
        print(f"{'='*80}\n")

        return probe_x, probe_y

    async def _highlight_and_select_element(
        self,
        tab: TabHandle,
        elements: List[PageElement],
        element_description: str,
        steps: List[str]
    ) -> LocatorResult:
        """高亮候选元素并让 Vision 选择

        Args:
            tab: 浏览器标签页
            elements: 候选元素列表
            element_description: 元素描述
            steps: 步骤记录

        Returns:
            LocatorResult: 定位结果
        """
        import logging
        logger = logging.getLogger(__name__)

        if len(elements) == 1:
            steps.append("只有1个候选元素，直接定位")
            return LocatorResult(
                element=elements[0],
                success=True,
                reason="成功定位目标元素",
                steps_taken=steps
            )

        steps.append(f"有{len(elements)}个候选元素，让Vision选择")

        try:
            # 高亮所有候选元素
            for i, element in enumerate(elements):
                try:
                    await self.browser.highlight_element(tab, element, color="red", label=str(i+1))
                except Exception as e:
                    logger.debug(f"高亮元素失败: {e}")

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

        except Exception as e:
            logger.exception(f"高亮选择元素时出错: {e}")
            return LocatorResult(
                element=elements[0] if elements else None,
                success=bool(elements),
                reason=f"高亮选择出错: {str(e)}，返回第一个",
                steps_taken=steps
            )

    async def _ask_vision_select_element(
        self,
        screenshot_base64: str,
        element_description: str,
        num_elements: int
    ) -> Optional[int]:
        """询问Vision选择哪个元素是目标

        Args:
            screenshot_base64: base64编码的截图
            element_description: 元素描述
            num_elements: 元素数量

        Returns:
            int or None: 元素索引（0-based），如果没有找到返回None
        """
        from .parser_utils import simple_section_parser

        prompt = f"""我正在寻找：{element_description}

页面上有{num_elements}个元素被加亮，每个都有数字标签（1、2、3...）。

请告诉我目标元素是第几个？（回答数字1-{num_elements}）

只回答数字，不要有其他内容。"""

        try:
            result = await self.vision.look_and_retry(
                prompt=prompt,
                image=screenshot_base64,
                parser=simple_section_parser,
                section_header="[选择]",
                max_retries=2
            )

            # 尝试提取数字
            import re
            numbers = re.findall(r'\d+', result)
            if numbers:
                idx = int(numbers[0]) - 1  # 转为0-based
                if 0 <= idx < num_elements:
                    return idx

            return None

        except Exception as e:
            import logging
            logging.warning(f"Vision选择失败: {e}")
            return None

    # ==================== 渐进式接近定位方法 ====================

    async def locate_element_iteratively(
        self,
        tab: TabHandle,
        element_description: str,
        max_iterations: int = 10
    ) -> LocatorResult:
        """
        通过渐进式接近定位元素

        1. 询问 Vision Brain 目标的初始中心坐标
        2. 在坐标位置画鼠标光标
        3. 询问 Vision Brain 鼠标是否在目标上
        4. 如果不在，询问方向和距离，移动鼠标
        5. 重复步骤 2-4 直到命中或达到最大迭代次数

        Args:
            tab: 浏览器标签页
            element_description: 目标元素描述
            max_iterations: 最大迭代次数

        Returns:
            LocatorResult: 定位结果
        """
        steps = []
        viewport_width, viewport_height = await self.browser.get_viewport_size(tab)

        # 步骤1：询问初始坐标
        steps.append("询问目标元素的初始中心坐标")
        screenshot = await self.browser.capture_screenshot(tab)
        initial_x, initial_y = await self._ask_vision_initial_position(
            screenshot, element_description, viewport_width, viewport_height
        )

        if initial_x is None or initial_y is None:
            return LocatorResult(
                element=None,
                success=False,
                reason="Vision Brain 无法找到目标元素",
                steps_taken=steps
            )

        steps.append(f"Vision Brain 给出的初始坐标: ({initial_x:.0f}, {initial_y:.0f})")

        # 步骤2-5：循环渐进
        current_x, current_y = initial_x, initial_y

        for iteration in range(max_iterations):
            steps.append(f"第 {iteration + 1} 次迭代")

            # 画鼠标光标
            await self.browser.draw_mouse_cursor_at(tab, current_x, current_y)
            print(f"\n🖱️  鼠标已画在位置: ({current_x:.0f}, {current_y:.0f})")
            print(f"⏸️  按回车继续，调用 Vision Brain...")
            input()

            # 截图并询问
            screenshot = await self.browser.capture_screenshot(tab)
            print(f"📸 正在发送给 Vision Brain...")
            on_target, direction, distance = await self._ask_vision_if_on_target(
                screenshot, element_description
            )

            # 显示 Vision Brain 的回答
            if on_target:
                print(f"✅ Vision Brain 回答: 命中！")
            else:
                print(f"❌ Vision Brain 回答: 未命中")
                print(f"   方向: {direction}")
                print(f"   距离: {distance}")
            print(f"⏸️  按回车继续...")
            input()

            # 检查是否命中
            if on_target:
                steps.append(f"鼠标已命中目标元素，坐标: ({current_x:.0f}, {current_y:.0f})")
                # 尝试获取该位置的元素
                element = await self._get_element_at_position(tab, current_x, current_y)
                return LocatorResult(
                    element=element,
                    success=True,
                    reason=f"成功定位目标元素（迭代 {iteration + 1} 次）",
                    steps_taken=steps
                )

            steps.append(f"Vision Brain 回答: 方向={direction}, 距离={distance}")

            # 计算新位置
            current_x, current_y = self._calculate_next_position(
                current_x, current_y, direction, distance, viewport_width, viewport_height
            )

            steps.append(f"移动到新位置: ({current_x:.0f}, {current_y:.0f})")

        # 达到最大迭代次数
        return LocatorResult(
            element=None,
            success=False,
            reason=f"达到最大迭代次数 ({max_iterations})，未能精确定位元素",
            steps_taken=steps
        )

    async def _ask_vision_initial_position(
        self,
        screenshot_base64: str,
        element_description: str,
        viewport_width: int,
        viewport_height: int
    ) -> Tuple[Optional[float], Optional[float]]:
        """询问 Vision Brain 目标元素的初始中心坐标"""
        from .parser_utils import simple_section_parser

        prompt = f"""这是一个浏览器页面截图，页面大小是 {viewport_width} x {viewport_height} 像素。

你要找的元素是：{element_description}

请告诉我，以页面左上角为坐标原点（0, 0），该元素的中心位置坐标大概是多少？

按下面格式输出：
```
[X坐标]
（在这里填写X坐标数值，单位是像素）

[Y坐标]
（在这里填写Y坐标数值，单位是像素）
```

如果找不到元素，请回答"找不到"。"""

        def position_parser(raw_reply: str) -> dict:
            """解析坐标回答"""
            # 先尝试标准解析
            result = simple_section_parser(raw_reply, section_header="[坐标]")
            if result.get("status") == "success":
                return result

            # 宽容模式：查找两个数字
            if "找不到" in raw_reply:
                return {"status": "error", "feedback": "找不到元素"}

            import re
            numbers = re.findall(r'\d+', raw_reply)
            if len(numbers) >= 2:
                try:
                    x = float(numbers[0])
                    y = float(numbers[1])
                    if 0 <= x <= viewport_width and 0 <= y <= viewport_height:
                        return {
                            "status": "success",
                            "content": {"x": x, "y": y}
                        }
                except:
                    pass

            return {"status": "error", "feedback": "无法解析坐标"}

        try:
            result = await self.vision.look_and_retry(
                prompt=prompt,
                image=screenshot_base64,
                parser=position_parser,
                max_retries=3
            )

            if isinstance(result, dict):
                x = result.get("x")
                y = result.get("y")
                return x, y

            return None, None

        except Exception as e:
            import logging
            logging.exception(f"Ask vision initial position error: {e}")
            return None, None

    async def _ask_vision_if_on_target(
        self,
        screenshot_base64: str,
        element_description: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        询问 Vision Brain 鼠标是否在目标上

        Returns:
            tuple: (on_target, direction, distance)
                - on_target: 是否命中
                - direction: 方向（上、下、左、右、左上、右上、左下、右下）
                - distance: 距离程度（一点点、中等、很多）
        """
        from .parser_utils import simple_section_parser

        prompt = f"""你要找的元素是：{element_description}

页面上有一个鼠标光标（白色填充，红色边框，形状是箭头）。

请告诉我：
1. 鼠标光标在该元素上吗？
2. 如果不在，需要往哪个方向移动？移动多少距离？

回答格式：
```
[状态]
（如果鼠标在元素上，回答"命中"；如果不在，回答"未命中"）

[方向]
（如果未命中，回答：上、下、左、右、左上、右上、左下、右下）

[距离]
（如果未命中，回答：一点点、中等、很多）
```

注意：
- "一点点" = 移动短距离（10%）
- "中等" = 移动中等距离（40%）
- "很多" = 移动长距离（70%）"""

        def on_target_parser(raw_reply: str) -> dict:
            """解析是否命中及移动方向"""
            # 步骤1：检查状态（命中 vs 未命中）
            status_lower = raw_reply.lower()

            # 检查是否命中
            if "命中" in raw_reply:
                return {
                    "status": "success",
                    "content": {"on_target": True}
                }

            # 检查是否明确说明"未命中"
            if "未命中" in raw_reply or "不在" in raw_reply:
                # 需要解析方向和距离
                lines = [line.strip() for line in raw_reply.strip().split('\n') if line.strip()]
                direction = None
                distance = None

                valid_directions = ["上", "下", "左", "右", "左上", "右上", "左下", "右下"]
                valid_distances = ["一点点", "中等", "很多"]

                for line in lines:
                    if line in valid_directions:
                        direction = line
                    elif line in valid_distances:
                        distance = line

                if direction and distance:
                    return {
                        "status": "success",
                        "content": {
                            "on_target": False,
                            "direction": direction,
                            "distance": distance
                        }
                    }
                else:
                    # 找到了"未命中"但没有找到方向和距离
                    return {
                        "status": "error",
                        "feedback": f"找到了'未命中'但没有找到方向或距离。找到的 direction={direction}, distance={distance}"
                    }

            # 无法理解回答
            return {
                "status": "error",
                "feedback": "无法确定是'命中'还是'未命中'"
            }

        try:
            result = await self.vision.look_and_retry(
                prompt=prompt,
                image=screenshot_base64,
                parser=on_target_parser,
                max_retries=3
            )

            if isinstance(result, dict):
                on_target = result.get("on_target", False)
                if on_target:
                    return True, None, None
                else:
                    direction = result.get("direction")
                    distance = result.get("distance")
                    return False, direction, distance

            return False, None, None

        except Exception as e:
            import logging
            logging.exception(f"Ask vision if on target error: {e}")
            return False, None, None

    def _calculate_next_position(
        self,
        current_x: float,
        current_y: float,
        direction: str,
        distance: str,
        viewport_width: int,
        viewport_height: int
    ) -> Tuple[float, float]:
        """计算下一个鼠标位置"""
        # 距离映射到百分比
        distance_ratios = {
            "一点点": 0.10,
            "中等": 0.40,
            "很多": 0.70
        }
        ratio = distance_ratios.get(distance, 0.40)

        # 根据方向计算新位置
        if direction == "上":
            # 向上移动：减少 y
            distance_to_boundary = current_y  # 到上边界的距离
            move_distance = distance_to_boundary * ratio
            new_y = current_y - move_distance
            return current_x, new_y

        elif direction == "下":
            # 向下移动：增加 y
            distance_to_boundary = viewport_height - current_y
            move_distance = distance_to_boundary * ratio
            new_y = current_y + move_distance
            return current_x, new_y

        elif direction == "左":
            # 向左移动：减少 x
            distance_to_boundary = current_x
            move_distance = distance_to_boundary * ratio
            new_x = current_x - move_distance
            return new_x, current_y

        elif direction == "右":
            # 向右移动：增加 x
            distance_to_boundary = viewport_width - current_x
            move_distance = distance_to_boundary * ratio
            new_x = current_x + move_distance
            return new_x, current_y

        elif direction == "左上":
            # 向左上方移动
            distance_x = current_x * ratio
            distance_y = current_y * ratio
            return current_x - distance_x, current_y - distance_y

        elif direction == "右上":
            # 向右上方移动
            distance_x = (viewport_width - current_x) * ratio
            distance_y = current_y * ratio
            return current_x + distance_x, current_y - distance_y

        elif direction == "左下":
            # 向左下方移动
            distance_x = current_x * ratio
            distance_y = (viewport_height - current_y) * ratio
            return current_x - distance_x, current_y + distance_y

        elif direction == "右下":
            # 向右下方移动
            distance_x = (viewport_width - current_x) * ratio
            distance_y = (viewport_height - current_y) * ratio
            return current_x + distance_x, current_y + distance_y

        # 默认返回原位置
        return current_x, current_y

    async def _get_element_at_position(
        self,
        tab: TabHandle,
        x: float,
        y: float
    ) -> Optional[PageElement]:
        """获取指定位置的元素"""
        # 使用 JavaScript 获取该位置的元素
        js = f"""
        (function() {{
            const element = document.elementFromPoint({x}, {y});
            if (!element) return null;
            return element.tagName + (element.id ? '#' + element.id : '');
        }})();
        """

        try:
            result = await asyncio.to_thread(tab.run_js, js)
            if result:
                # 查找对应的 PageElement
                all_elements = await self.browser.get_all_clickable_elements(tab)
                for elem in all_elements:
                    try:
                        chromium_elem = elem.get_element()
                        rect = await self.browser.get_element_rect(tab, elem)
                        elem_x, elem_y = rect.get('x', 0), rect.get('y', 0)
                        elem_w, elem_h = rect.get('width', 0), rect.get('height', 0)

                        # 检查点是否在元素内
                        if elem_x <= x <= elem_x + elem_w and elem_y <= y <= elem_y + elem_h:
                            return elem
                    except:
                        continue
            return None
        except Exception as e:
            import logging
            logging.exception(f"Get element at position error: {e}")
            return None
