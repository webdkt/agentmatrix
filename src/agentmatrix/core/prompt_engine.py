"!!! 有点过时，需要review了 !!!"
from jinja2 import Environment, FileSystemLoader

class PromptEngine:
    def __init__(self, profile_path="./profiles", prompt_path="./prompts"):
        self.env = Environment(loader=FileSystemLoader(prompt_path))
        # 预加载一些全局配置
        self.global_context = {
            "env_description": "Local Development Environment",
            "core_value": "Reliability and Structure"
        }

    def render_system_prompt(self, agent_profile, team_manifests):
        """
        为指定 Agent 生成完整的 System Prompt
        """
        # 1. 选择模板：如果 profile 指定了模板则用指定的，否则根据角色判断
        template_name = agent_profile.get("prompt_template", "base.j2")
        template = self.env.get_template(template_name)

        # 2. 准备数据
        context = {
            **self.global_context,
            "agent_name": agent_profile["name"],
            "agent_role": agent_profile.get("role", "Worker"),
            "agent_description": agent_profile["description"],
            "team_members": team_manifests, # 这是一个包含 name, desc, instructions 的列表
        }

        # 3. 渲染
        return template.render(**context)