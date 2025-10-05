# WebPilot/planner_agents/Planner_Agent/state.py

from typing import TypedDict, List, Dict, Any, Literal, Optional
from pydantic import BaseModel, Field

class StepParameters(BaseModel):
    """개별 스텝의 파라미터"""
    query: Optional[str] = None
    primary_domain: Optional[str] = None
    primary_uri: Optional[str] = None
    alternatives: Optional[List[Dict[str, Any]]] = None
    target_url: Optional[str] = None
    action_type: Optional[str] = None
    additional_params: Dict[str, Any] = Field(default_factory=dict)

class ExecutionStep(BaseModel):
    """실행 단계 정의"""
    step_id: int
    agent: Literal[
        "domain_classifier",
        "resource_selector", 
        "perceiver",
        "navigation_agent",
        "document_handler",
        "answer_creation"
    ]
    action: str
    description: str
    params: StepParameters
    dependencies: List[int] = Field(default_factory=list)
    status: Literal["pending", "in_progress", "completed", "failed", "skipped"] = "pending"
    result: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    
class ExecutionPlan(BaseModel):
    """전체 실행 계획"""
    plan_id: str
    query: str
    intent: Literal["search", "extract_info", "perform_action", "multi_step", "document_processing"]
    steps: List[ExecutionStep]
    current_step_index: int = 0
    requires_replan: bool = False
    replan_reason: Optional[str] = None
    
class PlannerState(TypedDict):
    """Planner Agent 상태"""
    # 입력
    user_query: str
    
    # 실행 계획
    execution_plan: Optional[ExecutionPlan]
    
    # 실행 컨텍스트 (session.state 참조용)
    domain_classification: Optional[Dict[str, Any]]
    resource_selection: Optional[Dict[str, Any]]
    perceiver_output: Optional[Dict[str, Any]]
    navigation_result: Optional[Dict[str, Any]]
    document_extraction: Optional[Dict[str, Any]]
    
    # 동적 재계획
    replan_trigger: bool
    replan_context: Dict[str, Any]
    
    # 메타데이터
    total_steps: int
    completed_steps: int
    failed_steps: int
    timestamp: str