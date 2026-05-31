"""
DesktopSubAgent — Desktop 层的 SubAgent 实现。

继承 core SubAgentShell，添加 prompt 模板组装逻辑。
类似 BaseAgent 和 BasicAgent 的关系。
"""

import re
from typing import Dict, List, Optional, Any

from ..core.sub_agent import SubAgentShell


class DesktopSubAgent(SubAgentShell):
    """
    Desktop 层 SubAgent —— 支持 prompt 模板组装。

    在 core SubAgentShell 基础上增加：
    - prompt_template 支持（从 PromptRegistry 加载模板）
    - $variable 模板渲染（persona 等）
    """

    def __init__(
        self,
        parent,                        # BaseAgent 实例
        name: str,
        available_skills: List[str],
        system_prompt: str = "",       # 自定义 prompt（优先）
        persona: str = None,           # persona（模板渲染用）
        prompt_template: str = None,   # prompt 模板名（如 "SIMPLE_MODE"）
        result_params: Dict[str, str] = None,
        max_result_retries: int = 3,
        micro_agent_attrs: Dict[str, Any] = None,
        md_skill_names: List[str] = None,
    ):
        # 如果没传 system_prompt 但传了 prompt_template，先组装 prompt
        if not system_prompt and prompt_template:
            template = parent.get_prompt_template(prompt_template)
            system_prompt = _render_template(template, persona=persona)

        super().__init__(
            parent=parent,
            name=name,
            available_skills=available_skills,
            system_prompt=system_prompt,
            result_params=result_params,
            max_result_retries=max_result_retries,
            micro_agent_attrs=micro_agent_attrs,
            md_skill_names=md_skill_names,
        )


def _render_template(template: str, persona: str = None) -> str:
    """替换 $variable 占位符。"""
    overrides = {}
    if persona:
        overrides["persona"] = persona

    def replacer(match):
        key = match.group(1)
        if key in overrides:
            return str(overrides[key])
        return match.group(0)

    return re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', replacer, template)
