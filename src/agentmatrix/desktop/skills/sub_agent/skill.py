"""
Sub Agent Skill — 任务结果返回

提供 return_result 和 return_error 两个 action，供 SubAgent 的 MicroAgent 使用：
- return_result: 返回结构化结果并退出
- return_error: 报告错误并退出

SubAgentShell 自动将 "sub_agent" 加入 available_skills，无需手动配置。
"""

from agentmatrix.core.action import register_action


class Sub_agentSkillMixin:
    """任务结果返回 skill"""

    _skill_description = "任务结果返回：完成任务后用 return_result 返回结果，遇到无法解决的问题用 return_error 返回错误"

    @register_action(
        short_desc="返回结果",
        description="任务完成，返回结构化结果并结束。result 为结果对象，字段格式参见任务描述。",
        param_infos={"result": "结果对象（如 {'key': 'value'} 格式）"},
    )
    async def return_result(self, result) -> str:
        import json

        # 支持 dict 和 str 两种输入
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except (json.JSONDecodeError, ValueError):
                data = {"result": result}
        elif isinstance(result, dict):
            data = result
        else:
            data = {"result": str(result)}

        # 校验 result_params（如果 parent 有定义）
        schema = getattr(self.parent, '_result_params', None)
        if schema and isinstance(schema, dict):
            missing = [k for k in schema if k not in data]
            if missing:
                return f"缺少字段: {missing}。请提供完整结果。"

        self.parent._validated_result = data
        self._should_exit = True
        return "ok"

    @register_action(
        short_desc="返回错误",
        description="遇到无法解决的问题，返回错误信息并结束任务。",
        param_infos={"error": "错误描述"},
    )
    async def return_error(self, error: str) -> str:
        self.parent._validated_result = {"error": error}
        self._should_exit = True
        return "ok"
