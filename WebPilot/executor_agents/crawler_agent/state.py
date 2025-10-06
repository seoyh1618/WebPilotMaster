# WebPilot/executor_agents/crawler_agent/state.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class ListItem(BaseModel):
    """리스트 항목"""
    title: str
    url: str
    date: Optional[str] = None
    author: Optional[str] = None
    preview: Optional[str] = None
    relevance_score: float = 0.0

class DetailedAnalysis(BaseModel):
    """상세 분석 결과"""
    url: str
    title: str
    success: bool
    information_found: bool = False
    extracted_info: str = ""
    confidence: float = 0.0
    error_message: Optional[str] = None

class CrawlerInput(BaseModel):
    """Crawler 입력"""
    url: str
    query: str
    max_items: int = 50
    filter_by_relevance: bool = True
    analyze_details: bool = False  # 배치 분석 여부
    detail_analysis_count: int = 5  # 분석할 개수
    parallel_workers: int = 5

class PaginationInfo(BaseModel):
    """페이지네이션 정보"""
    has_pagination: bool = False
    current_page: int = 1
    total_pages: Optional[int] = None
    next_page_url: Optional[str] = None
    next_page_selector: Optional[str] = None

class CrawlerOutput(BaseModel):
    """Crawler 출력"""
    success: bool
    is_list_page: bool = False
    items: List[ListItem] = Field(default_factory=list)
    pagination: Optional[PaginationInfo] = None
    total_items_found: int = 0
    detailed_analyses: List[DetailedAnalysis] = Field(default_factory=list)
    most_relevant_analysis: Optional[DetailedAnalysis] = None
    error_message: Optional[str] = None