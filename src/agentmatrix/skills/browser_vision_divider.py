"""
!!! 探索性脚本，请忽略 !!!

智能区域划分工具

支持自适应的区域划分策略，根据Vision LLM的回答动态决定下一步的划分方式。
核心思想：利用"元素被坐标线穿过"的信息，进行智能分块。
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from ..core.browser.browser_adapter import PageElement


@dataclass
class RegionBounds:
    """区域边界"""
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict:
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height
        }


@dataclass
class Quadrant:
    """象限信息"""
    name: str  # "左上", "右上", "左下", "右下"
    bounds: RegionBounds
    parent_bounds: Optional[RegionBounds] = None


@dataclass
class ElementDivision:
    """元素分块结果"""
    elements: List[PageElement]
    bounds: RegionBounds
    label: str
    division_type: str  # "horizontal", "vertical", "region"


class SmartRegionDivider:
    """
    智能区域划分器

    根据Vision LLM的回答和页面元素分布，动态决定如何划分区域。
    """

    # 阈值配置
    MIN_REGION_SIZE = 300  # 最小区域尺寸（像素），小于此值停止细分

    def __init__(self):
        pass  # 不再需要跟踪层级和历史

    def increase_division_level(self):
        """增加细分层级"""
        pass  # 保留空方法以保持兼容性（如果有外部调用）

    def calculate_initial_quadrants(self, viewport_width: int, viewport_height: int) -> List[Quadrant]:
        """
        计算初始的4个象限

        Args:
            viewport_width: 视口宽度
            viewport_height: 视口高度

        Returns:
            list: 4个象限的信息
        """
        half_w = viewport_width / 2
        half_h = viewport_height / 2

        quadrants = [
            Quadrant("左上", RegionBounds(0, 0, half_w, half_h)),
            Quadrant("右上", RegionBounds(half_w, 0, half_w, half_h)),
            Quadrant("左下", RegionBounds(0, half_h, half_w, half_h)),
            Quadrant("右下", RegionBounds(half_w, half_h, half_w, half_h)),
        ]

        return quadrants

    def calculate_quadrant_bounds(self, parent_bounds: RegionBounds, quadrant_name: str) -> RegionBounds:
        """
        在给定的父区域内计算象限边界

        Args:
            parent_bounds: 父区域边界
            quadrant_name: 象限名称（"左上", "右上", "左下", "右下"）

        Returns:
            RegionBounds: 计算出的象限边界
        """
        half_w = parent_bounds.width / 2
        half_h = parent_bounds.height / 2

        if quadrant_name == "左上":
            return RegionBounds(
                parent_bounds.x,
                parent_bounds.y,
                half_w,
                half_h
            )
        elif quadrant_name == "右上":
            return RegionBounds(
                parent_bounds.x + half_w,
                parent_bounds.y,
                half_w,
                half_h
            )
        elif quadrant_name == "左下":
            return RegionBounds(
                parent_bounds.x,
                parent_bounds.y + half_h,
                half_w,
                half_h
            )
        elif quadrant_name == "右下":
            return RegionBounds(
                parent_bounds.x + half_w,
                parent_bounds.y + half_h,
                half_w,
                half_h
            )
        else:
            raise ValueError(f"Invalid quadrant name: {quadrant_name}")

    def calculate_elements_bounding_box(self, elements: List[PageElement]) -> RegionBounds:
        """
        计算一组元素的边界框

        Args:
            elements: PageElement 对象列表

        Returns:
            RegionBounds: 包含所有元素的最小边界框
        """
        if not elements:
            return RegionBounds(0, 0, 0, 0)

        # 注意：这里需要异步获取，但为了简化，假设调用者已经处理
        # 实际使用时，需要在调用方获取元素位置
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')

        # 这个方法需要配合异步使用，返回的是计算逻辑
        # 实际的元素位置获取在 browser_adapter 中完成
        return RegionBounds(min_x, min_y, max_x - min_x, max_y - min_y)

    def dynamic_divide_by_axis(
        self,
        elements: List[PageElement],
        elements_coords: List[Tuple[float, float]],  # 每个元素的 (x, y) 坐标
        axis: str,  # "x" 或 "y"
        num_parts: int = 3
    ) -> List[ElementDivision]:
        """
        按坐标轴动态分块

        Args:
            elements: PageElement 对象列表
            elements_coords: 每个元素的坐标列表 [(x1, y1), (x2, y2), ...]
            axis: 分割轴 ("x" 按水平分割, "y" 按垂直分割)
            num_parts: 分成几份（默认3份）

        Returns:
            list: ElementDivision 对象列表
        """
        if axis not in ["x", "y"]:
            raise ValueError(f"Invalid axis: {axis}, must be 'x' or 'y'")

        if not elements:
            return []

        # 提取指定轴的坐标
        idx = 0 if axis == "x" else 1
        coords = [coord[idx] for coord in elements_coords]

        # 计算分块点
        min_coord = min(coords)
        max_coord = max(coords)
        range_size = max_coord - min_coord

        # 如果范围太小，不分块
        if range_size < self.MIN_REGION_SIZE:
            return [ElementDivision(
                elements=elements,
                bounds=RegionBounds(min_coord, min_coord, range_size, range_size),
                label="全部",
                division_type="region"
            )]

        # 计算分块边界
        divisions = []
        part_size = range_size / num_parts

        for i in range(num_parts):
            part_min = min_coord + i * part_size
            part_max = min_coord + (i + 1) * part_size

            # 筛选在这个分块内的元素
            part_elements = []
            part_coords = []

            for elem, coord in zip(elements, elements_coords):
                elem_coord = coord[idx]
                if part_min <= elem_coord < part_max:
                    part_elements.append(elem)
                    part_coords.append(coord)

            # 生成标签
            if axis == "x":
                label = f"水平分块{i+1}"
            else:
                label = f"垂直分块{i+1}"

            # 计算边界
            if axis == "x":
                bounds = RegionBounds(
                    part_min,
                    min_coord,  # Y轴使用最小值（会在调用方调整）
                    part_size,
                    range_size
                )
            else:
                bounds = RegionBounds(
                    min_coord,  # X轴使用最小值（会在调用方调整）
                    part_min,
                    range_size,
                    part_size
                )

            division = ElementDivision(
                elements=part_elements,
                bounds=bounds,
                label=label,
                division_type=f"horizontal" if axis == "x" else "vertical"
            )
            divisions.append(division)

        # 过滤掉空的分块
        divisions = [d for d in divisions if len(d.elements) > 0]

        return divisions

    def decide_next_strategy(
        self,
        vision_answer: str,
        current_region: RegionBounds,
        crossed_elements: List[PageElement],
        viewport_size: Tuple[int, int]
    ) -> Dict:
        """
        根据Vision的回答决定下一步策略

        Args:
            vision_answer: Vision LLM的回答
            current_region: 当前区域边界
            crossed_elements: 被坐标线穿过的元素列表
            viewport_size: 视口大小 (width, height)

        Returns:
            dict: {
                "strategy": "cross_divide" | "horizontal_divide" | "vertical_divide" | "ask_elements",
                "target_region": RegionBounds | None,
                "axis": str | None,
                "reason": str
            }
        """
        # 明确象限 → 继续十字划分
        if vision_answer in ["左上", "右上", "左下", "右下"]:
            target_region = self.calculate_quadrant_bounds(current_region, vision_answer)

            # 检查是否应该停止细分
            if self.should_stop_dividing(target_region, len(crossed_elements)):
                return {
                    "strategy": "ask_elements",
                    "target_region": target_region,
                    "axis": None,
                    "reason": f"象限{vision_answer}足够小，直接询问元素"
                }

            return {
                "strategy": "cross_divide",
                "target_region": target_region,
                "axis": None,
                "reason": f"进入{vision_answer}象限，继续十字划分"
            }

        # 被竖线穿过 → 按Y轴分块
        elif vision_answer in ["左", "右"]:
            return {
                "strategy": "horizontal_divide",
                "target_region": None,
                "axis": "y",
                "reason": f"元素被{'竖' if vision_answer == '左' else '竖'}线穿过，按Y轴动态分块"
            }

        # 被横线穿过 → 按X轴分块
        elif vision_answer in ["上", "下"]:
            return {
                "strategy": "vertical_divide",
                "target_region": None,
                "axis": "x",
                "reason": f"元素被横线穿过，按X轴动态分块"
            }

        # 十字交叉 → 直接询问
        elif vision_answer == "中间":
            return {
                "strategy": "ask_elements",
                "target_region": current_region,
                "axis": None,
                "reason": "元素在十字交叉处，直接确认"
            }

        else:
            raise ValueError(f"Invalid vision answer: {vision_answer}")

    def reset(self):
        """重置划分器状态"""
        pass  # 不再需要重置状态
