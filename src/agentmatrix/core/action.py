from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable
import json


class SkillType(Enum):
    """Skill 类型"""
    PYTHON_METHOD = "python_method"  # Python 可执行方法


@dataclass
class ActionMetadata:
    name: str
    description: str
    # 存储生成的 JSON Schema，给 SLM 看
    json_schema: Dict[str, Any]

    # 🆕 新架构字段
    skill_type: SkillType = SkillType.PYTHON_METHOD
    implementation: Optional[Callable] = None  # Python 实现（仅 PYTHON_METHOD） 

def register_action(
    short_desc: str,
    description: str,
    param_infos: Dict[str, str] = None,
    skill_type: SkillType = SkillType.PYTHON_METHOD  # 🆕 新参数（默认向后兼容）
):
    """
    Args:
        description: 函数功能的自然语言描述
        param_infos: 参数名 -> 参数含义的映射 (e.g. {"to": "目标Agent名字"})
        skill_type: 技能类型（PYTHON_METHOD 或 MD_DOCUMENT）
    """
    if param_infos is None:
        param_infos = {}

    def decorator(func):
        func._is_action = True
        func._action_short_desc = short_desc  # 🆕 保存简短描述
        func._action_desc = description
        func._action_param_infos = param_infos
        func._skill_type = skill_type  # 🆕
        return func
    return decorator

@dataclass
class ActionDef:
    name: str
    description: str
    parameters: Dict[str, str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            name=data["name"],
            description=data["description"],
            parameters=data.get("parameters", {})
        )

    def to_prompt(self):
        return f"- {self.name}: {self.description} | Params: {json.dumps(self.parameters, ensure_ascii=False)}"