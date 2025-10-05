# WebPilot/executor_agents/navigation_agent/state.py

from typing import TypedDict, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, validator

class NavigationAction(BaseModel):
    """네비게이션 액션 정의"""
    action_type: Literal["goto", "click", "type", "wait", "scroll", "hover", "back", "forward", "reload"]
    
    # goto
    url: Optional[str] = None
    
    # click, hover
    coordinates: Optional[Dict[str, float]] = None  # {"x": 250, "y": 150}
    selector: Optional[str] = None  # CSS selector (대체 방법)
    
    # type
    text: Optional[str] = None
    
    # wait
    duration: Optional[float] = None  # 초
    wait_for: Optional[str] = None  # "networkidle", "domcontentloaded", "load"
    
    # scroll
    direction: Optional[Literal["up", "down", "top", "bottom"]] = None
    pixels: Optional[int] = None
    
    description: str = ""
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if v is not None:
            if 'x' not in v or 'y' not in v:
                raise ValueError("coordinates는 x, y를 포함해야 합니다")
            if v['x'] < 0 or v['y'] < 0:
                raise ValueError("좌표는 음수일 수 없습니다")
        return v
    
    @validator('action_type')
    def validate_action_requirements(cls, v, values):
        """액션 타입별 필수 파라미터 검증"""
        if v == 'goto' and not values.get('url'):
            raise ValueError("goto 액션은 url이 필요합니다")
        if v == 'click' and not (values.get('coordinates') or values.get('selector')):
            raise ValueError("click 액션은 coordinates 또는 selector가 필요합니다")
        if v == 'type' and not values.get('text'):
            raise ValueError("type 액션은 text가 필요합니다")
        return v

class NavigationResult(BaseModel):
    """네비게이션 실행 결과"""
    success: bool
    current_url: str = ""
    page_title: str = ""
    error_message: Optional[str] = None
    execution_time: float = 0.0
    screenshot_path: Optional[str] = None
    
    # 페이지 상태
    status_code: Optional[int] = None
    is_loaded: bool = True
    has_errors: bool = False

class NavigationInput(BaseModel):
    """Navigation 입력"""
    actions: List[NavigationAction]
    start_url: Optional[str] = None  # 시작 URL (없으면 현재 페이지에서 계속)
    context: Dict[str, Any] = Field(default_factory=dict)  # Planner로부터의 추가 컨텍스트
    
    @validator('actions')
    def validate_actions_not_empty(cls, v):
        if not v:
            raise ValueError("최소 1개의 액션이 필요합니다")
        return v

class NavigationOutput(BaseModel):
    """Navigation 출력"""
    results: List[NavigationResult]
    final_url: str = ""
    total_execution_time: float = 0.0
    success: bool = True
    error_message: Optional[str] = None

class NavigationState(TypedDict):
    """Navigation 상태"""
    input: NavigationInput
    output: Optional[NavigationOutput]
    error: Optional[str]