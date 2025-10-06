# WebPilot/executor_agents/answer_creation_agent/state.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class SourceInfo(BaseModel):
    """정보 출처"""
    url: str
    title: str = ""
    excerpt: str = ""
    relevance: float = 0.0

class AnswerInput(BaseModel):
    """Answer Creation 입력"""
    query: str
    collected_information: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[SourceInfo] = Field(default_factory=list)
    execution_summary: Optional[Dict[str, Any]] = None

class AnswerOutput(BaseModel):
    """Answer Creation 출력"""
    success: bool
    answer: str = ""
    confidence: float = 0.0
    sources_used: List[SourceInfo] = Field(default_factory=list)
    additional_notes: str = ""
    error_message: Optional[str] = None