from agents.base import BaseAgent
from skills.crawler import RecursiveCrawlerMixin

class DataCrawler(BaseAgent, RecursiveCrawlerMixin):
    def __init__(self, profile ):
        super().__init__(profile)
        


