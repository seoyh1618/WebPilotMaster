# WebPilot/executor_agents/crawler_agent/__init__.py

from .agent import Crawler_Agent, CrawlerAgentClass
from .state import (
    CrawlerInput,
    CrawlerOutput,
    ListItem,
    DetailedAnalysis,
    PaginationInfo
)

__all__ = [
    'Crawler_Agent',
    'CrawlerAgentClass',
    'CrawlerInput',
    'CrawlerOutput',
    'ListItem',
    'DetailedAnalysis',
    'PaginationInfo'
]