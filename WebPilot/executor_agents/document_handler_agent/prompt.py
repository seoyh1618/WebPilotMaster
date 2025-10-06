# WebPilot/executor_agents/document_handler_agent/prompt.py

DOCUMENT_HANDLER_DESCRIPTION = "파일 다운로드 및 RAG 기반 분석 전문 에이전트"

DOCUMENT_HANDLER_INSTRUCTION = """
파일을 다운로드하고 RAG로 관련 정보를 추출합니다.

[지원 파일]
- PDF
- Word (docx)
- Excel (xlsx)
- 텍스트

[RAG 파이프라인]
1. 파일 다운로드
2. 텍스트 추출
3. 청킹 (500자 단위)
4. 벡터화 (TF-IDF)
5. 유사도 계산
6. Top-K 추출
7. LLM 분석

[출력]
- 요약
- 핵심 정보
- 관련 섹션
"""

def create_analysis_prompt(context: str, query: str) -> str:
    """분석 프롬프트 생성"""
    return f"""다음 문서 내용에서 '{query}'에 대한 정보를 추출하세요.

{context}

요약과 핵심 정보를 JSON으로 반환하세요."""