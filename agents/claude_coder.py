# agents/claude_coder.py 
from agents.base import BaseAgent
from skills.terminal_ctrl import TerminalSkillMixin

class CoderAgent(BaseAgent, TerminalSkillMixin):
    def __init__(self, profile):
        super().__init__(profile)
        # Mixin 的方法会自动被 _scan_methods 扫描到