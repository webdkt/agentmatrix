from ..agents.base import BaseAgent
from ..skills.data_crawler import DigitalInternCrawlerMixin
import asyncio
import logging

class DataCrawler(BaseAgent, DigitalInternCrawlerMixin):
    _custom_log_level = logging.DEBUG
    def __init__(self, profile ):
        super().__init__(profile)
        self.browser_adapter = None
        #self.sem = asyncio.Semaphore(5)
        


