# WebPilot/executor_agents/multimodal_perceiver_agent/state.py

from typing import TypedDict, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, validator

class ElementInfo(BaseModel):
    """페이지 요소 정보 (관찰 결과)"""
    type: Literal["link", "button", "input", "menu", "text", "image", "form"]
    text: str
    coordinates: Optional[Dict[str, float]] = None  # {"x": 100, "y": 200}
    href: Optional[str] = None  # 링크인 경우
    description: str = ""  # 요소 설명
class FileInfo(BaseModel):
    """파일 정보"""
    file_url: str
    file_type: str  # "pdf", "xlsx", "docx", "hwp"
    file_name: str = ""
    link_text: str = ""
    confidence: float = 0.0
    reasoning: str = ""

class RecommendedAction(BaseModel):
    """Perceiver가 추천하는 다음 액션"""
    should_click: bool = False
    element_index: Optional[int] = None
    element_text: str = ""
    action_type: Literal["click", "hover", "goto"] = "click"
    coordinates: Optional[Dict[str, float]] = None
    href: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    is_fallback: bool = False
    alternative_elements: List[int] = Field(default_factory=list)
    
    # ⭐ 드롭다운 지원
    requires_submenu_selection: bool = False
    visible_submenus: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_submenu_index: Optional[int] = None
    
    # ⭐ 파일 다운로드 지원
    should_download: bool = False
    file_info: Optional[FileInfo] = None

class PageAnalysisResult(BaseModel):
    """페이지 분석 결과 (관찰 보고서)"""
    
    # 정보 발견 여부
    information_found: bool
    extracted_info: Optional[str] = None
    confidence: float = 0.0
    
    # 페이지 구조 (관찰 사실)
    page_type: str = "general"  # main_page, list_page, detail_page, form_page, login_page
    title: str = ""
    summary: str = ""  # 페이지 요약 설명
    
    # 보이는 요소들 (객관적 사실)
    visible_elements: List[ElementInfo] = Field(default_factory=list)
    
    # 키워드 검색 결과
    keyword_matches: Dict[str, List[str]] = Field(default_factory=dict)
    recommended_action: Optional[RecommendedAction] = None
    
    has_navigation_menu: bool = False
    has_search_box: bool = False
    has_login_form: bool = False
    requires_interaction: bool = False
    
    analysis_warnings: List[str] = Field(default_factory=list)

class PerceiverInput(BaseModel):
    """Perceiver 입력"""
    url: str
    query: str
    screenshot_required: bool = True
    depth: int = Field(default=0, ge=0)  # 탐색 깊이
    previous_urls: List[str] = Field(default_factory=list)
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("유효한 URL이 아닙니다")
        return v

class PerceiverOutput(BaseModel):
    """Perceiver 출력"""
    analysis: PageAnalysisResult
    screenshot_path: Optional[str] = None
    execution_time: float = 0.0

class PerceiverState(TypedDict):
    """Perceiver 상태"""
    input: PerceiverInput
    output: Optional[PerceiverOutput]
    error: Optional[str]

