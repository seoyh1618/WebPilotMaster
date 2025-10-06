# WebPilot/executor_agents/filter_based_page_handler_agent/state.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal

class FilterElement(BaseModel):
    """필터 요소"""
    label: str
    type: Literal["dropdown", "text_input", "date_picker", "tab", "button"]
    selector: Optional[str] = None
    xpath: Optional[str] = None
    current_value: Optional[str] = None
    options: List[str] = Field(default_factory=list)
    coordinates: Optional[Dict[str, int]] = None

class FilterPageInfo(BaseModel):
    """필터 페이지 정보"""
    is_filter_page: bool = False
    page_type: str = "unknown"  # "sap", "iframe", "standard"
    page_title: str = ""
    filters: List[FilterElement] = Field(default_factory=list)
    search_button: Optional[FilterElement] = None
    result_container_selector: Optional[str] = None

class FilterStep(BaseModel):
    """필터 조작 단계"""
    step_number: int
    filter_label: str
    action: Literal["select_option", "input_text", "click_tab", "click_button"]
    value: Optional[str] = None
    wait_after: float = 1.5
    reasoning: str = ""

class FilterManipulationStrategy(BaseModel):
    """필터 조작 전략"""
    steps: List[FilterStep] = Field(default_factory=list)
    estimated_time: float = 0.0
    confidence: float = 0.0

class FilterBasedPageHandlerInput(BaseModel):
    """입력"""
    url: str
    query: str
    max_attempts: int = 3
    screenshot_on_error: bool = True

class ResultRow(BaseModel):
    """결과 행"""
    columns: List[str] = Field(default_factory=list)
    raw_data: Dict[str, str] = Field(default_factory=dict)

class FilterBasedPageHandlerOutput(BaseModel):
    """출력"""
    success: bool
    filter_info: Optional[FilterPageInfo] = None
    strategy_used: Optional[FilterManipulationStrategy] = None
    filters_manipulated: bool = False
    results_found: bool = False
    result_rows: List[ResultRow] = Field(default_factory=list)
    total_results: int = 0
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None