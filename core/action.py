from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict

class ActionType(Enum):
    SYNC = "SYNC"
    ASYNC = "ASYNC"
    TERMINAL = "TERMINAL"

@dataclass
class ActionMetadata:
    name: str
    description: str
    type: ActionType
    # 存储生成的 JSON Schema，给 SLM 看
    json_schema: Dict[str, Any] 

def register_action(
    description: str, 
    type: ActionType = ActionType.SYNC,
    param_infos: Dict[str, str] = None 
):
    """
    Args:
        description: 函数功能的自然语言描述
        type: 动作流类型
        param_infos: 参数名 -> 参数含义的映射 (e.g. {"to": "目标Agent名字"})
    """
    if param_infos is None:
        param_infos = {}

    def decorator(func):
        func._is_action = True
        func._action_desc = description
        func._action_type = type
        func._action_param_infos = param_infos
        return func
    return decorator

@dataclass
class ActionDef:
    name: str
    type: ActionType
    description: str
    parameters: Dict[str, str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            name=data["name"],
            type=data["type"],
            description=data["description"],
            parameters=data.get("parameters", {})
        )

    def to_prompt(self):
        return f"- {self.name}: {self.description} | Params: {json.dumps(self.parameters, ensure_ascii=False)}"