from ..agents.base import BaseAgent
from ..skills.project_management import ProjectManagementMixin
from ..skills.notebook import NotebookMixin
import json
class StatefulAgent(BaseAgent, ProjectManagementMixin, NotebookMixin):
    def __init__(self, profile):
        super().__init__(profile)
        # 这就是那个“动态文档”，可以是 JSON，也可以是 Markdown
        self.project_board = None
        self.vector_db = None