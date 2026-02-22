"""
Skill Base Module - Skill Mixin 基类和接口定义

定义了所有 Skill Mixins 必须遵循的接口规范
"""

from abc import ABC, abstractmethod


class SkillMixinInterface(ABC):
    """
    Skill Mixin 接口定义

    所有 Skill Mixin 类应该隐式遵循此接口（无需显式继承）

    关键约定：
    1. 所有 action 方法使用 @register_action 装饰器
    2. self 指向最终的 MicroAgent 实例（拥有所有必需属性）
    3. 可以访问的 MicroAgent 属性：
       - self.working_context: WorkingContext
       - self.logger: Logger
       - self.brain: Brain
       - self.cerebellum: Cerebellum

    依赖声明（可选）：
    4. 如果 skill 依赖其他 skills，可声明 _skill_dependencies 类属性：
       ```python
       class MySkillMixin:
           _skill_dependencies = ["browser", "file"]  # 声明依赖的 skills
       ```
       这样用户只需配置 skills: ["my_skill"]，系统会自动加载 browser 和 file。

    依赖解析规则：
    - 循环依赖：A→B→A 会被自动检测并处理（不会崩溃）
    - 重复声明：如果用户同时配置 ["my_skill", "browser"]，browser 只加载一次
    - 加载顺序：依赖优先于被依赖者（browser 先于 my_skill 加载）
    """

    # 不需要定义抽象方法，这只是文档说明
    # Skill Mixins 通过约定而非继承来确保接口一致性
