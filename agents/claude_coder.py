# agents/claude_coder.py 
from agents.stateful import StatefulAgent
from agents.base import BaseAgent
from skills.terminal_ctrl import TerminalSkillMixin
from skills.project_management import ProjectManagementMixin

class CoderAgent(BaseAgent, TerminalSkillMixin,ProjectManagementMixin ):
    def __init__(self, profile):
        super().__init__(profile)
        # Mixin 的方法会自动被 _scan_methods 扫描到