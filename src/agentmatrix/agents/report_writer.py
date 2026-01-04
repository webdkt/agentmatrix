from ..agents.base import BaseAgent
from ..skills.report_writer import ReportWriterSkillMixin
import asyncio
import logging

class ReportWriter(BaseAgent, ReportWriterSkillMixin):
    _custom_log_level = logging.DEBUG
    def __init__(self, profile ):
        super().__init__(profile)
        self.research_state = None
        #self.sem = asyncio.Semaphore(5)
        


