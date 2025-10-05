# WebPilot/planner_agents/Domain_Priority_Classifier_Agent/state.py

from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DomainInfo(BaseModel):
    """도메인 정보"""
    domain: str
    uri: str
    score: float
    priority: str  # "critical", "high", "medium", "low"
    confidence: str  # "high", "medium", "low"
    reasoning: str
    condition: str = ""  # 조건부 선택인 경우

class SelectionInfo(BaseModel):
    """선택 정보"""
    primary_count: int = 1
    alternatives_count: int = 0
    selection_rule: str = ""

class DomainMetadata(BaseModel):
    """메타데이터"""
    selection_info: SelectionInfo

class DomainPriorityResult(BaseModel):
    """도메인 우선순위 분류 결과"""
    primary: DomainInfo
    alternatives: List[DomainInfo] = Field(default_factory=list)
    reason: str = ""
    metadata: DomainMetadata  # ⭐ 필수 필드

class DomainClassifierInput(BaseModel):
    """Domain Classifier 입력"""
    query: str
    get_next: bool = False  # alternative 도메인 요청 여부
    current_domain: Optional[str] = None  # 현재 시도한 도메인

class DomainClassifierOutput(BaseModel):
    """Domain Classifier 출력"""
    result: DomainPriorityResult
    success: bool = True
    error_message: Optional[str] = None

class DomainClassifierState(TypedDict):
    """Domain Classifier 상태"""
    input: DomainClassifierInput
    output: Optional[DomainClassifierOutput]
    error: Optional[str]