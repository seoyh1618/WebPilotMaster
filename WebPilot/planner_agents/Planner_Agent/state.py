# WebPilot/planner_agents/Planner_Agent/state.py

from typing import TypedDict, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
class StepParameters(BaseModel):
    query: Optional[str] = None                    # 사용자 질의
    primary_domain: Optional[str] = None           # 선택된 주 도메인
    primary_uri: Optional[str] = None              # 도메인 URI
    alternatives: Optional[List[Dict]] = None      # 대체 도메인 목록
    target_url: Optional[str] = None               # 타겟 URL
    search_keyword: Optional[str] = None           # 검색 키워드
    embedding_threshold: Optional[float] = None    # 임베딩 유사도 임계값
    additional_params: Dict[str, Any] = {}         # 추가 파라미터
class ExecutionStep(BaseModel):
    """실행 단계"""
    step_id: int
    agent: str
    action: str
    description: str
    params: Dict[str, Any]
    dependencies: List[int] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    result: Optional[Dict[str, Any]] = None

class ExecutionPlan(BaseModel):
    """실행 계획"""
    plan_id: str
    query: str
    intent: Literal["search", "multi_step", "unknown"] = "search"
    steps: List[ExecutionStep]
    reasoning: Optional[str] = None

class ReplanRequest(BaseModel):
    """재계획 요청"""
    replan: bool = True
    original_query: str
    current_attempt: int
    max_attempts: int = 5
    perceiver_result: Dict[str, Any]
    visited_urls: List[str] = Field(default_factory=list)
    current_url: str = ""
    domain_info: Optional[Dict[str, Any]] = None  

class PlannerInput(BaseModel):
    """Planner 입력"""
    query: Optional[str] = None
    replan_request: Optional[ReplanRequest] = None

class PlannerOutput(BaseModel):
    """Planner 출력"""
    plan: ExecutionPlan
    should_continue: bool = True  # 계속 진행할지 여부
    is_complete: bool = False  # 작업 완료 여부

class PlannerState(TypedDict):
    """Planner 상태"""
    input: PlannerInput
    output: Optional[PlannerOutput]
    error: Optional[str]