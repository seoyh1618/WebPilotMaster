# WebPilot/executor_agents/resource_selector_agent/state.py

from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field

class URLCandidate(BaseModel):
    """URL 후보 정보"""
    url: str
    title: str
    link_text: str
    parent_menu: Optional[str] = None
    depth: int = 1
    context: Optional[str] = None  # 링크 주변 텍스트
    
class ScoredURL(BaseModel):
    """유사도 점수가 부여된 URL"""
    url: str
    title: str
    similarity_score: float
    reasoning: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ResourceSelectorInput(BaseModel):
    """Resource Selector 입력"""
    primary_domain: str
    primary_uri: str
    query: str
    alternatives: Optional[List[Dict[str, Any]]] = None
    top_k: int = 3
    min_score: float = 0.6
    max_depth: int = 2

class ResourceSelectorOutput(BaseModel):
    """Resource Selector 출력"""
    selected_urls: List[ScoredURL]
    total_candidates: int
    filtered_out: int
    execution_time: float
    cache_hit: bool = False

class ResourceSelectorState(TypedDict):
    """Resource Selector 상태"""
    input: ResourceSelectorInput
    output: Optional[ResourceSelectorOutput]
    error: Optional[str]