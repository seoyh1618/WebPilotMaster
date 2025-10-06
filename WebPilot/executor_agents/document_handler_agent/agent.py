# WebPilot/executor_agents/document_handler_agent/agent.py

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .prompt import (
    DOCUMENT_HANDLER_DESCRIPTION,
    DOCUMENT_HANDLER_INSTRUCTION,
    create_analysis_prompt
)
from .state import (
    DocumentInput,
    DocumentOutput,
    DocumentMetadata,
    DocumentAnalysis,
    ExtractedSection
)
from .file_parsers import PDFParser, DOCXParser, XLSXParser, TXTParser
from .rag_pipeline import RAGPipeline  # ⭐ RAG 추가
from WebPilot.constants import constants
import requests
import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class DocumentHandlerAgentClass:
    """Document Handler Agent 구현 (RAG 포함)"""
    
    def __init__(self, model_name: str = constants.MODEL_O3_MINI):
        self.llm = LiteLlm(model=model_name)
        self.download_dir = Path("./WebPilot/artifacts/downloads")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.parsers = {
            "pdf": PDFParser,
            "docx": DOCXParser,
            "xlsx": XLSXParser,
            "txt": TXTParser
        }
        
        self.rag = RAGPipeline()  # ⭐ RAG 초기화
        
        logger.info("Document Handler Agent 초기화 완료 (RAG 포함)")
    
    def run(self, input_text: str) -> str:
        """AgentTool 인터페이스 호환 메서드"""
        start_time = time.time()
        
        try:
            # 입력 파싱
            input_data = json.loads(input_text)
            doc_input = DocumentInput(**input_data)
            
            logger.info(f"문서 처리 시작: {doc_input.file_url}")
            logger.info(f"파일 타입: {doc_input.file_type}")
            logger.info(f"질의: {doc_input.query}")
            
            # 1. 파일 다운로드
            file_path = self._download_file(doc_input.file_url, doc_input.file_type)
            
            if not file_path:
                raise Exception("파일 다운로드 실패")
            
            # 2. 파일 파싱
            parse_result = self._parse_file(file_path, doc_input.file_type)
            
            if not parse_result.get('success'):
                raise Exception(f"파일 파싱 실패: {parse_result.get('error')}")
            
            full_text = parse_result.get('full_text', '')
            
            # 3. RAG 파이프라인 실행
            logger.info("⭐ RAG 파이프라인 시작")
            relevant_chunks = self.rag.process_document(
                full_text=full_text,
                query=doc_input.query,
                top_k=5
            )
            
            # 4. 메타데이터 생성
            metadata = DocumentMetadata(
                file_name=Path(file_path).name,
                file_size=Path(file_path).stat().st_size,
                page_count=parse_result.get('metadata', {}).get('page_count'),
                author=parse_result.get('metadata', {}).get('author'),
                file_format=doc_input.file_type
            )
            
            # 5. LLM으로 분석 (관련 chunks만)
            analysis = self._analyze_with_llm_rag(
                relevant_chunks,
                doc_input.query
            )
            
            # 6. 결과 생성
            output = DocumentOutput(
                success=True,
                metadata=metadata,
                full_text=full_text[:5000],  # 처음 5000자
                analysis=analysis,
                processing_time=time.time() - start_time
            )
            
            logger.info(f"✓ 문서 처리 완료 ({output.processing_time:.2f}초)")
            logger.info(f"  - {len(relevant_chunks)}개 관련 chunk 추출")
            logger.info(f"  - {len(analysis.extracted_sections)}개 섹션 분석")
            
            return json.dumps(output.dict(), ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Document Handler 실행 실패: {e}", exc_info=True)
            
            error_output = DocumentOutput(
                success=False,
                error_message=str(e),
                processing_time=time.time() - start_time
            )
            
            return json.dumps(error_output.dict(), ensure_ascii=False, indent=2)
    
    def _download_file(self, url: str, file_type: str) -> Optional[str]:
        """파일 다운로드"""
        try:
            logger.info(f"파일 다운로드: {url}")
            
            response = requests.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # 파일명 생성
            file_name = f"document_{int(time.time())}.{file_type}"
            file_path = self.download_dir / file_name
            
            # 저장
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"✓ 다운로드 완료: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"다운로드 실패: {e}")
            return None
    
    def _parse_file(self, file_path: str, file_type: str) -> dict:
        """파일 파싱"""
        parser_class = self.parsers.get(file_type)
        
        if not parser_class:
            return {
                "success": False,
                "error": f"지원하지 않는 파일 타입: {file_type}"
            }
        
        logger.info(f"파일 파싱 시작: {file_type}")
        result = parser_class.parse(file_path)
        
        if result.get('success'):
            text_length = len(result.get('full_text', ''))
            logger.info(f"✓ 파싱 완료: {text_length}자 추출")
        
        return result
    
    def _analyze_with_llm_rag(
        self,
        relevant_chunks: list,
        query: str
    ) -> DocumentAnalysis:
        """
        LLM으로 문서 분석 (RAG 기반)
        
        관련 chunks만 LLM에 전달
        """
        try:
            logger.info("LLM 분석 시작 (RAG 기반)")
            
            # 관련 chunks를 하나의 컨텍스트로
            context = "\n\n".join([
                f"[Chunk {chunk['chunk_id']} - 관련도: {chunk['similarity_score']:.2f}]\n{chunk['text']}"
                for chunk in relevant_chunks
            ])
            
            prompt = f"""다음은 문서에서 질의와 가장 관련 있는 섹션들입니다.

                **질의:** {query}

                **관련 섹션:**
                {context}

                **당신의 임무:**

                1. **요약** (2-3문장)
                - 이 섹션들의 핵심 내용

                2. **핵심 정보 추출**
                - 질의에 대한 직접적 답변
                - Key-Value 형식
                - 예: {{"신청 기간": "2025.03.01 ~ 03.10", "신청 방법": "온라인 포털"}}

                3. **섹션별 정리**
                - 각 관련 섹션의 제목과 내용
                - 관련도 점수 포함

                **출력 형식:**
                ```json{{{{
                "summary": "문서 요약",
                "extracted_sections": [
                {{{{
                "title": "신청 기간 및 방법",
                "content": "...",
                "relevance_score": 0.95
                }}}}
                ],
                "key_information": {{{{
                "신청 기간": "...",
                "신청 방법": "...",
                "제출 서류": "..."
                }}}}
                }}}}
            """
            response = self.llm.generate(prompt)
            result = json.loads(response)
            
            # ExtractedSection 객체로 변환
            sections = [
                ExtractedSection(**section)
                for section in result.get('extracted_sections', [])
            ]
            
            analysis = DocumentAnalysis(
                summary=result.get('summary', ''),
                extracted_sections=sections,
                key_information=result.get('key_information', {}),
                tables=[]
            )
            
            logger.info(f"✓ LLM 분석 완료: {len(sections)}개 섹션")
            
            return analysis
            
        except Exception as e:
            logger.error(f"LLM 분석 실패: {e}")
            
            # 폴백: RAG chunks를 그대로 섹션으로
            sections = [
                ExtractedSection(
                    title=f"관련 섹션 {chunk['chunk_id']}",
                    content=chunk['text'][:500],
                    relevance_score=chunk['similarity_score']
                )
                for chunk in relevant_chunks[:3]
            ]
            
            return DocumentAnalysis(
                summary="문서 분석 실패, RAG 결과 반환",
                extracted_sections=sections,
                key_information={}
            )


# AgentTool이 사용할 Agent 인스턴스
Document_Handler_Agent = Agent(
    name="DocumentHandlerAgent",
    model=LiteLlm(model=constants.MODEL_O3_MINI),
    description=DOCUMENT_HANDLER_DESCRIPTION,
    instruction=DOCUMENT_HANDLER_INSTRUCTION
)