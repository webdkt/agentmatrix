"""
Memory Skill - 实体记忆技能

提供两层实体记忆系统：
- Session 级别记忆（临时信息，会话内有效）
- 全局级别记忆（长期信息，跨会话保留）

核心 Actions：
- recall: 查询实体记忆（合并 session + 全局）
- update_memory: 更新记忆（自动从会话历史提取）
"""

from .skill import MemorySkillMixin

__all__ = ["MemorySkillMixin"]
