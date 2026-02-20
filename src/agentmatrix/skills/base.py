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
    """

    # 不需要定义抽象方法，这只是文档说明
    # Skill Mixins 通过约定而非继承来确保接口一致性
