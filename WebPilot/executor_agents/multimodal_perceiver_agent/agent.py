# WebPilot/executor_agents/multimodal_perceiver_agent/agent.py

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .prompt import PERCEIVER_DESCRIPTION, PERCEIVER_INSTRUCTION
from .state import PerceiverInput, PerceiverOutput, PageAnalysisResult
from .screenshot import capture_screenshot_sync, ScreenshotCaptureError
from .html_parser import HTMLParser, HTMLParserError
from .vision_analyzer import VisionAnalyzer, VisionAnalyzerError
from .response_validator import ResponseValidator
from WebPilot.constants import constants
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

class MultilmodalPerceiverAgentClass:
    """Multimodal Perceiver Agent 구현 (관찰자 + 다음 액션 추천)"""
    
    def __init__(self, model_name: str = constants.MODEL_O3_MINI):
        # Perceiver는 VLM만 사용하므로 LLM은 불필요
        # 하지만 Agent 인터페이스 호환성을 위해 유지
        self.llm = LiteLlm(model=model_name)
        self.agent = Agent(
            name="MultimodalPerceiver",
            model=self.llm,
            description=PERCEIVER_DESCRIPTION,
            instruction=PERCEIVER_INSTRUCTION
        )
        
        # 컴포넌트 초기화
        self.html_parser = HTMLParser()
        self.vision_analyzer = VisionAnalyzer()
        
        logger.info("Multimodal Perceiver Agent 초기화 완료")
    
    def run(self, input_text: str) -> str:
        """
        AgentTool 인터페이스 호환 메서드
        
        Args:
            input_text: JSON 형식 입력
            {
                "url": "https://grad.ssu.ac.kr/",
                "query": "사물함 신청 방법",
                "screenshot_required": true,
                "depth": 0
            }
            
        Returns:
            JSON 형식 출력
            {
                "analysis": {
                    "information_found": false,
                    "recommended_action": {
                        "should_click": true,
                        "element_index": 0,
                        "element_text": "학생지원",
                        "confidence": 0.85,
                        ...
                    },
                    ...
                },
                "execution_time": 5.23,
                "success": true
            }
        """
        start_time = time.time()
        
        try:
            # 입력 파싱
            input_data = json.loads(input_text)
            perceiver_input = PerceiverInput(**input_data)
            
            logger.info("="*80)
            logger.info(f"페이지 분석 시작")
            logger.info(f"  - URL: {perceiver_input.url}")
            logger.info(f"  - 질의: {perceiver_input.query}")
            logger.info(f"  - Depth: {perceiver_input.depth}")
            logger.info("="*80)
            
            # 1. 스크린샷 + HTML 캡처
            logger.info("Step 1: 페이지 캡처 중...")
            base64_image, html_content = self._capture_page(perceiver_input.url)
            logger.info("  ✓ 캡처 완료")
            
            # 2. HTML 파싱
            logger.info("Step 2: HTML 파싱 중...")
            html_summary = self._parse_html(html_content, perceiver_input.url)
            logger.info(f"  ✓ 파싱 완료 (링크: {len(html_summary.get('links', []))}개)")
            
            # 3. Vision 분석 (다음 액션 추천 포함)
            logger.info("Step 3: VLM 분석 중 (액션 추천 포함)...")
            analysis = self._analyze_with_vision(
                base64_image=base64_image,
                html_summary=html_summary,
                query=perceiver_input.query,
                url=perceiver_input.url
            )
            logger.info("  ✓ 분석 완료")
            
            # 4. 결과 생성
            execution_time = time.time() - start_time
            
            output = PerceiverOutput(
                analysis=analysis,
                screenshot_path=None,  # 필요시 저장 경로 추가
                execution_time=execution_time,
                success=True,
                fallback_used=analysis.confidence < 0.5
            )
            
            logger.info("="*80)
            logger.info(f"페이지 분석 완료:")
            logger.info(f"  - 정보 발견: {analysis.information_found}")
            logger.info(f"  - 실행 시간: {execution_time:.2f}초")
            
            if analysis.recommended_action and analysis.recommended_action.should_click:
                rec = analysis.recommended_action
                logger.info(f"  - 추천: [{rec.element_index}] {rec.element_text} (confidence: {rec.confidence:.2f})")
            else:
                logger.info(f"  - 추천: 없음")
            
            logger.info("="*80)
            
            return json.dumps(output.dict(), ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Perceiver 실행 실패: {e}", exc_info=True)
            
            # 에러 응답
            error_output = PerceiverOutput(
                analysis=PageAnalysisResult(
                    information_found=False,
                    confidence=0.0,
                    page_type='error_page',
                    title='',
                    summary=f'페이지 분석 실패: {str(e)}',
                    visible_elements=[],
                    keyword_matches={},
                    recommended_action=None,
                    analysis_warnings=[str(e)]
                ),
                execution_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
            
            return json.dumps(error_output.dict(), ensure_ascii=False, indent=2)
    
    def _capture_page(self, url: str) -> tuple:
        """페이지 캡처"""
        try:
            return capture_screenshot_sync(url)
        except ScreenshotCaptureError as e:
            logger.error(f"스크린샷 캡처 실패: {e}")
            raise
    
    def _parse_html(self, html_content: str, url: str) -> dict:
        """HTML 파싱"""
        try:
            return self.html_parser.parse(html_content, base_url=url)
        except HTMLParserError as e:
            logger.error(f"HTML 파싱 실패: {e}")
            # 최소한의 정보라도 반환
            return {
                'title': '',
                'page_type': 'unknown',
                'links': [],
                'buttons': [],
                'forms': [],
                'headings': [],
                'main_text': '',
                'total_links': 0,
                'total_buttons': 0,
                'has_navigation': False,
                'has_search': False,
                'has_login': False
            }
    
    def _analyze_with_vision(
        self,
        base64_image: str,
        html_summary: dict,
        query: str,
        url: str
    ) -> PageAnalysisResult:
        """Vision 분석 (폴백 포함)"""
        try:
            return self.vision_analyzer.analyze(
                base64_image=base64_image,
                html_summary=html_summary,
                query=query,
                url=url
            )
        except VisionAnalyzerError as e:
            logger.error(f"Vision 분석 실패, 폴백 사용: {e}")
            return ResponseValidator.create_fallback_response(
                url=url,
                query=query,
                html_summary=html_summary,
                error_message=str(e)
            )


# AgentTool이 사용할 Agent 인스턴스
Multimodal_Perceiver_Agent = Agent(
    name="MultimodalPerceiver",
    model=LiteLlm(model=constants.MODEL_GPT_4O),
    description=PERCEIVER_DESCRIPTION,
    instruction=PERCEIVER_INSTRUCTION
)