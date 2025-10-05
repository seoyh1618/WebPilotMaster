
from openai import OpenAI
from typing import Dict, Any
import logging
import os
from .prompt import create_vision_prompt
from .response_validator import ResponseValidator, ResponseValidationError
from .state import PageAnalysisResult
from WebPilot.constants import constants

logger = logging.getLogger(__name__)

class VisionAnalyzerError(Exception):
    """Vision 분석 오류"""
    pass

class VisionAnalyzer:
    """GPT-4o Vision API를 사용한 스크린샷 분석 (다음 액션 추천 포함)"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise VisionAnalyzerError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
        
        self.client = OpenAI(api_key=api_key)
        self.model = constants.PERCEIVER_VLM_MODEL
        self.max_tokens = constants.PERCEIVER_VLM_MAX_TOKENS
        self.temperature = constants.PERCEIVER_VLM_TEMPERATURE
        
        logger.info(f"Vision Analyzer 초기화 (모델: {self.model})")
    
    def analyze(
        self,
        base64_image: str,
        html_summary: Dict[str, Any],
        query: str,
        url: str
    ) -> PageAnalysisResult:
        """
        스크린샷 + HTML 분석 + 다음 액션 추천
        
        Args:
            base64_image: Base64 인코딩된 이미지
            html_summary: HTML 파서 결과
            query: 사용자 질의
            url: 페이지 URL
            
        Returns:
            PageAnalysisResult 객체 (recommended_action 포함)
            
        Raises:
            VisionAnalyzerError: 분석 실패 시
        """
        logger.info(f"Vision 분석 시작: {query}")
        logger.info(f"URL: {url}")
        
        try:
            # 프롬프트 생성 (다음 액션 추천 포함)
            prompt = create_vision_prompt(html_summary, query)
            
            logger.debug(f"프롬프트 길이: {len(prompt)} 문자")
            
            # GPT-4o Vision API 호출
            logger.info("GPT-4o Vision API 호출 중...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # 응답 추출
            content = response.choices[0].message.content
            
            if not content:
                raise VisionAnalyzerError("VLM 응답이 비어있습니다")
            
            logger.debug(f"VLM 원본 응답:\n{content[:500]}...")
            
            # 토큰 사용량 로깅
            if hasattr(response, 'usage'):
                logger.info(f"토큰 사용량: {response.usage.total_tokens} "
                           f"(입력: {response.usage.prompt_tokens}, "
                           f"출력: {response.usage.completion_tokens})")
            
            # 응답 검증 및 파싱
            try:
                analysis = ResponseValidator.validate_and_parse(content)
                
                logger.info(f"Vision 분석 완료:")
                logger.info(f"  - 정보 발견: {analysis.information_found}")
                logger.info(f"  - 신뢰도: {analysis.confidence:.2f}")
                logger.info(f"  - 페이지 타입: {analysis.page_type}")
                logger.info(f"  - 보이는 요소: {len(analysis.visible_elements)}개")
                
                if analysis.recommended_action:
                    rec = analysis.recommended_action
                    logger.info(f"  - 추천 액션:")
                    logger.info(f"    * 요소: [{rec.element_index}] {rec.element_text}")
                    logger.info(f"    * 액션: {rec.action_type}")
                    logger.info(f"    * Confidence: {rec.confidence:.2f}")
                    logger.info(f"    * 폴백 여부: {rec.is_fallback}")
                    logger.info(f"    * 이유: {rec.reasoning[:100]}...")
                else:
                    logger.info(f"  - 추천 액션: 없음")
                
                return analysis
                
            except ResponseValidationError as e:
                logger.error(f"응답 검증 실패: {e}")
                # 폴백: HTML만으로 분석
                return ResponseValidator.create_fallback_response(
                    url=url,
                    query=query,
                    html_summary=html_summary,
                    error_message=f"응답 검증 실패: {e}"
                )
            
        except Exception as e:
            logger.error(f"Vision 분석 실패: {e}", exc_info=True)
            
            # 폴백: HTML만으로 분석
            return ResponseValidator.create_fallback_response(
                url=url,
                query=query,
                html_summary=html_summary,
                error_message=str(e)
            )