# WebPilot/executor_agents/document_handler_agent/state.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class DocumentInput(BaseModel):
    """입력"""
    file_url: str
    query: str
    file_type: str = "pdf"  # pdf, docx, xlsx, txt

class DocumentMetadata(BaseModel):
    """메타데이터"""
    file_name: str = ""
    file_size: int = 0
    page_count: Optional[int] = None
    author: Optional[str] = None
    file_format: str = ""

class ExtractedSection(BaseModel):
    """추출된 섹션"""
    title: str = ""
    content: str = ""
    relevance_score: float = 0.0

class DocumentAnalysis(BaseModel):
    """분석 결과"""
    summary: str = ""
    extracted_sections: List[ExtractedSection] = Field(default_factory=list)
    key_information: Dict[str, str] = Field(default_factory=dict)
    tables: List[Dict] = Field(default_factory=list)

class DocumentOutput(BaseModel):
    """출력"""
    success: bool
    metadata: Optional[DocumentMetadata] = None
    full_text: str = ""
    analysis: Optional[DocumentAnalysis] = None
    error_message: Optional[str] = None
    processing_time: float = 0.0