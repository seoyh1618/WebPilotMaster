# WebPilot/executor_agents/multimodal_perceiver_agent/vision_analyzer.py

from openai import OpenAI
from typing import Dict, Any, Optional, Tuple
import logging
import os
import json
from .prompt import create_vision_prompt_with_cot
from .response_validator import ResponseValidator, ResponseValidationError
from .dom_analyzer import DOMAnalyzer, DOMAnalyzerError
from .state import PageAnalysisResult, RecommendedAction
from WebPilot.constants import constants

logger = logging.getLogger(__name__)

class VisionAnalyzerError(Exception):
    """Vision 분석 오류"""
    pass

class VisionAnalyzer:
    """VLM + LLM 항상 병렬 분석 (전략 B)"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise VisionAnalyzerError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
        
        self.client = OpenAI(api_key=api_key)
        self.model = constants.PERCEIVER_VLM_MODEL
        self.max_tokens = 2500
        self.temperature = constants.PERCEIVER_VLM_TEMPERATURE
        
        # DOM Analyzer 초기화
        self.dom_analyzer = DOMAnalyzer()
        
        logger.info(f"Vision Analyzer 초기화 (VLM+LLM 병렬 모드, 모델: {self.model})")
    
    def analyze(
        self,
        base64_image: str,
        html_summary: Dict[str, Any],
        query: str,
        url: str
    ) -> PageAnalysisResult:
        """
        VLM + LLM 항상 병렬 분석
        
        전략:
        1. VLM 분석 시도
        2. LLM DOM 분석 시도
        3. 두 결과 융합 (consensus)
        
        Args:
            base64_image: Base64 인코딩된 이미지
            html_summary: HTML 파서 결과
            query: 사용자 질의
            url: 페이지 URL
            
        Returns:
            융합된 PageAnalysisResult
        """
        logger.info("="*80)
        logger.info(f"VLM+LLM 병렬 분석 시작: {query}")
        logger.info(f"URL: {url}")
        logger.info("="*80)
        
        # ========================================
        # Step 1: VLM 분석
        # ========================================
        vlm_result = None
        vlm_success = False
        
        try:
            logger.info("🔵 VLM 분석 시작...")
            vlm_result = self._analyze_with_vlm(base64_image, html_summary, query, url)
            vlm_success = True
            
            logger.info(f"✓ VLM 분석 완료")
            logger.info(f"  - 정보 발견: {vlm_result.information_found}")
            logger.info(f"  - 확신도: {vlm_result.confidence:.2f}")
            
            if vlm_result.recommended_action:
                rec = vlm_result.recommended_action
                logger.info(f"  - VLM 추천: [{rec.element_index}] {rec.element_text} "
                           f"(confidence: {rec.confidence:.2f})")
            else:
                logger.info(f"  - VLM 추천: 없음")
            
        except Exception as e:
            logger.warning(f"✗ VLM 분석 실패: {e}")
            vlm_success = False
        
        # ========================================
        # Step 2: LLM DOM 분석 (항상 실행)
        # ========================================
        llm_result = None
        llm_success = False
        
        try:
            logger.info("🟢 LLM DOM 분석 시작...")
            llm_dom_result = self.dom_analyzer.analyze_structure(
                html_summary=html_summary,
                query=query,
                vlm_failed=(not vlm_success)
            )
            llm_success = True
            
            logger.info(f"✓ LLM DOM 분석 완료")
            logger.info(f"  - 추천: [{llm_dom_result.get('recommended_element_index')}] "
                       f"{llm_dom_result.get('recommended_element_text')}")
            logger.info(f"  - 확신도: {llm_dom_result.get('confidence', 0):.2f}")
            logger.info(f"  - 이유: {llm_dom_result.get('reasoning', '')[:100]}...")
            
            # LLM 결과를 저장 (융합용)
            llm_result = llm_dom_result
            
        except Exception as e:
            logger.warning(f"✗ LLM DOM 분석 실패: {e}")
            llm_success = False
        
        # ========================================
        # Step 3: 결과 융합 (Consensus)
        # ========================================
        logger.info("="*80)
        logger.info("🔄 VLM + LLM 결과 융합 중...")
        logger.info("="*80)
        
        if vlm_success and llm_success:
            # 케이스 1: 둘 다 성공 → 융합
            logger.info("✓ VLM + LLM 둘 다 성공 → 결과 융합")
            final_result = self._merge_results(vlm_result, llm_result, html_summary)
        
        elif vlm_success and not llm_success:
            # 케이스 2: VLM만 성공
            logger.info("⚠️  VLM만 성공, LLM 실패 → VLM 결과 사용")
            final_result = vlm_result
            final_result.analysis_warnings.append("LLM DOM 분석 실패, VLM만 사용")
        
        elif not vlm_success and llm_success:
            # 케이스 3: LLM만 성공
            logger.info("⚠️  LLM만 성공, VLM 실패 → LLM 결과 변환")
            final_result = self._convert_llm_to_analysis(llm_result, html_summary, url, query)
            final_result.analysis_warnings.append("VLM 분석 실패, LLM DOM만 사용")
        
        else:
            # 케이스 4: 둘 다 실패
            logger.error("✗ VLM + LLM 모두 실패")
            final_result = self._create_emergency_fallback(html_summary, url, query)
        
        # ========================================
        # Step 4: 최종 결과 로깅
        # ========================================
        logger.info("="*80)
        logger.info("📊 최종 결과:")
        logger.info(f"  - 정보 발견: {final_result.information_found}")
        logger.info(f"  - 확신도: {final_result.confidence:.2f}")
        
        if final_result.recommended_action:
            rec = final_result.recommended_action
            logger.info(f"  - 최종 추천: [{rec.element_index}] {rec.element_text}")
            logger.info(f"  - 액션: {rec.action_type}")
            logger.info(f"  - 확신도: {rec.confidence:.2f}")
            logger.info(f"  - 이유: {rec.reasoning[:100]}...")
        else:
            logger.info(f"  - 최종 추천: 없음")
        
        logger.info("="*80)
        
        return final_result
    
    def _analyze_with_vlm(
        self,
        base64_image: str,
        html_summary: Dict[str, Any],
        query: str,
        url: str
    ) -> PageAnalysisResult:
        """VLM 분석"""
        
        # 스크린샷 검증
        if not base64_image or len(base64_image) < 100:
            logger.error(f"스크린샷 데이터 없음 또는 너무 작음: {len(base64_image) if base64_image else 0} bytes")
            raise VisionAnalyzerError("스크린샷 데이터 없음")
        
        logger.info(f"✓ 스크린샷 준비 완료: {len(base64_image)} bytes")
        
        # CoT 프롬프트 생성
        prompt = create_vision_prompt_with_cot(html_summary, query)
        
        logger.info(f"✓ VLM 프롬프트 생성: {len(prompt)} 문자")
        logger.debug(f"프롬프트 미리보기:\n{prompt[:500]}...")
        
        # GPT-4o Vision API 호출
        logger.info("📡 GPT-4o Vision API 호출 중...")
        
        try:
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
            
            logger.info("✓ VLM 응답 수신")
            
        except Exception as e:
            logger.error(f"VLM API 호출 실패: {e}")
            raise VisionAnalyzerError(f"VLM API 호출 실패: {e}")
        
        # 응답 추출
        content = response.choices[0].message.content
        
        if not content:
            raise VisionAnalyzerError("VLM 응답이 비어있습니다")
        
        logger.debug(f"VLM 원본 응답:\n{content[:500]}...")
        
        # 토큰 사용량
        if hasattr(response, 'usage'):
            logger.info(f"📊 토큰 사용: {response.usage.total_tokens} "
                    f"(입력: {response.usage.prompt_tokens}, 출력: {response.usage.completion_tokens})")
        
        # "볼 수 없다" 응답 감지
        if "확인할 수 없" in content or "cannot see" in content.lower():
            logger.error("❌ VLM이 스크린샷을 볼 수 없다고 응답")
            logger.error(f"응답 내용:\n{content[:200]}...")
            raise VisionAnalyzerError("VLM이 스크린샷 분석 거부")
        
        # 응답 검증 및 파싱
        try:
            analysis = ResponseValidator.validate_and_parse(content)
            
            # image_analysis_status 확인
            if hasattr(analysis, 'image_analysis_status'):
                if analysis.image_analysis_status == "failed":
                    logger.error("VLM이 image_analysis_status=failed 보고")
                    raise VisionAnalyzerError("VLM 스크린샷 분석 실패")
            
            logger.info(f"✓ VLM 분석 완료: confidence={analysis.confidence:.2f}")
            
            return analysis
            
        except ResponseValidationError as e:
            logger.error(f"VLM 응답 검증 실패: {e}")
            raise VisionAnalyzerError(f"응답 검증 실패: {e}")
    def _merge_results(
        self,
        vlm_result: PageAnalysisResult,
        llm_dom_result: Dict[str, Any],
        html_summary: Dict[str, Any]
    ) -> PageAnalysisResult:
        """
        VLM + LLM 결과 융합 (Consensus 전략)
        
        융합 규칙:
        1. information_found: VLM 우선 (시각 정보 있음)
        2. recommended_action: 
           - 둘이 같은 요소 추천 → 확신도 높임
           - 다른 요소 추천 → 확신도 높은 쪽 선택
           - 확신도 비슷 → VLM 우선, LLM은 대안
        3. confidence: 가중 평균
        """
        logger.info("🔄 결과 융합 시작:")
        
        # ========================================
        # 1. 정보 발견 여부 (VLM 우선)
        # ========================================
        information_found = vlm_result.information_found
        extracted_info = vlm_result.extracted_info
        
        if information_found:
            logger.info("  ✓ VLM이 정보 발견 → 그대로 사용")
            # 정보 발견했으면 추천 액션 불필요
            return vlm_result
        
        # ========================================
        # 2. 추천 액션 융합
        # ========================================
        vlm_action = vlm_result.recommended_action
        llm_element_idx = llm_dom_result.get('recommended_element_index')
        llm_confidence = llm_dom_result.get('confidence', 0.0)
        
        if vlm_action is None:
            # VLM 추천 없음 → LLM만 사용
            logger.info("  VLM 추천 없음 → LLM 결과 사용")
            merged_action = self._convert_llm_action_to_recommended(
                llm_dom_result, vlm_result.visible_elements, html_summary
            )
            
            final_result = vlm_result
            final_result.recommended_action = merged_action
            final_result.confidence = llm_confidence
            final_result.analysis_warnings.append("VLM 추천 없음, LLM 추천 사용")
            
            return final_result
        
        # VLM과 LLM 비교
        vlm_element_idx = vlm_action.element_index
        vlm_confidence = vlm_action.confidence
        
        logger.info(f"  VLM 추천: [{vlm_element_idx}] (confidence: {vlm_confidence:.2f})")
        logger.info(f"  LLM 추천: [{llm_element_idx}] (confidence: {llm_confidence:.2f})")
        
        # ========================================
        # 케이스 1: 같은 요소 추천 → 확신도 증폭
        # ========================================
        if vlm_element_idx == llm_element_idx:
            logger.info(f"  ✅ 일치! 같은 요소 [{vlm_element_idx}] 추천 → 확신도 증폭")
            
            # 확신도 부스트 (가중 평균 + 보너스)
            boosted_confidence = min(
                (vlm_confidence * 0.6 + llm_confidence * 0.4) + 0.1,  # 보너스 +0.1
                1.0
            )
            
            vlm_action.confidence = boosted_confidence
            vlm_action.reasoning = (
                f"[VLM+LLM 일치] {vlm_action.reasoning} "
                f"| LLM 분석: {llm_dom_result.get('reasoning', '')[:80]}..."
            )
            vlm_action.alternative_elements = llm_dom_result.get('alternative_indices', [])
            
            vlm_result.confidence = boosted_confidence
            vlm_result.analysis_warnings.append(
                f"VLM+LLM 동일 추천 (확신도 {vlm_confidence:.2f} → {boosted_confidence:.2f})"
            )
            
            return vlm_result
        
        # ========================================
        # 케이스 2: 다른 요소 추천 → 확신도 비교
        # ========================================
        logger.info(f"  ⚠️  불일치! VLM [{vlm_element_idx}] vs LLM [{llm_element_idx}]")
        
        # 확신도 차이
        confidence_diff = abs(vlm_confidence - llm_confidence)
        
        if confidence_diff >= 0.2:
            # 확신도 차이 큼 → 높은 쪽 선택
            if vlm_confidence > llm_confidence:
                logger.info(f"  → VLM 확신도 높음 ({vlm_confidence:.2f} > {llm_confidence:.2f}) → VLM 선택")
                vlm_action.alternative_elements = [llm_element_idx]
                vlm_action.reasoning += f" | LLM 대안: [{llm_element_idx}] {llm_dom_result.get('recommended_element_text')}"
                
                vlm_result.analysis_warnings.append(
                    f"VLM 우선 (확신도 {vlm_confidence:.2f} > LLM {llm_confidence:.2f})"
                )
                
                return vlm_result
            
            else:
                logger.info(f"  → LLM 확신도 높음 ({llm_confidence:.2f} > {vlm_confidence:.2f}) → LLM 선택")
                
                llm_action = self._convert_llm_action_to_recommended(
                    llm_dom_result, vlm_result.visible_elements, html_summary
                )
                llm_action.alternative_elements = [vlm_element_idx]
                llm_action.reasoning += f" | VLM 대안: [{vlm_element_idx}] {vlm_action.element_text}"
                
                vlm_result.recommended_action = llm_action
                vlm_result.confidence = llm_confidence
                vlm_result.analysis_warnings.append(
                    f"LLM 우선 (확신도 {llm_confidence:.2f} > VLM {vlm_confidence:.2f})"
                )
                
                return vlm_result
        
        else:
            # 확신도 비슷 → VLM 우선, LLM은 대안
            logger.info(f"  → 확신도 비슷 ({confidence_diff:.2f}) → VLM 우선, LLM은 대안")
            
            # 확신도 평균으로 낮춤 (불확실성 반영)
            avg_confidence = (vlm_confidence + llm_confidence) / 2
            
            vlm_action.confidence = avg_confidence
            vlm_action.alternative_elements = [llm_element_idx] + llm_dom_result.get('alternative_indices', [])
            vlm_action.reasoning = (
                f"[VLM+LLM 불일치] VLM: {vlm_action.reasoning[:80]}... | "
                f"LLM: {llm_dom_result.get('reasoning', '')[:80]}... | "
                f"대안 [{llm_element_idx}] 시도 권장"
            )
            
            vlm_result.confidence = avg_confidence
            vlm_result.analysis_warnings.append(
                f"VLM+LLM 불일치 (확신도 낮춤 {avg_confidence:.2f}), 대안 [{llm_element_idx}] 제공"
            )
            
            return vlm_result
    
    def _convert_llm_action_to_recommended(
        self,
        llm_dom_result: Dict[str, Any],
        visible_elements: list,
        html_summary: Dict[str, Any]
    ) -> Optional[RecommendedAction]:
        """LLM DOM 결과를 RecommendedAction으로 변환"""
        try:
            element_index = llm_dom_result.get('recommended_element_index')
            
            if element_index is None or element_index >= len(visible_elements):
                return None
            
            element = visible_elements[element_index]
            
            # 드롭다운 처리
            requires_submenu = llm_dom_result.get('requires_submenu', False)
            visible_submenus = []
            recommended_submenu_index = None
            
            if requires_submenu:
                nav_structure = html_summary.get('navigation_structure', [])
                element_text = llm_dom_result.get('recommended_element_text', '')
                
                for menu in nav_structure:
                    if menu.get('text') == element_text and menu.get('has_submenu'):
                        submenus = menu.get('submenus', [])
                        visible_submenus = [
                            {"text": s.get('text'), "coordinates": {"x": 100, "y": 80 + i*30}}
                            for i, s in enumerate(submenus[:8])
                        ]
                        recommended_submenu_index = llm_dom_result.get('submenu_index')
                        break
            
            return RecommendedAction(
                should_click=True,
                element_index=element_index,
                element_text=element.text,
                action_type=llm_dom_result.get('action_type', 'click'),
                coordinates=element.coordinates,
                href=element.href,
                confidence=llm_dom_result.get('confidence', 0.5),
                reasoning=f"[LLM DOM] {llm_dom_result.get('reasoning', '')}",
                is_fallback=False,
                alternative_elements=llm_dom_result.get('alternative_indices', []),
                requires_submenu_selection=requires_submenu,
                visible_submenus=visible_submenus,
                recommended_submenu_index=recommended_submenu_index,
                should_download=False,
                file_info=None
            )
            
        except Exception as e:
            logger.error(f"LLM 액션 변환 실패: {e}")
            return None
    
    def _convert_llm_to_analysis(
        self,
        llm_dom_result: Dict[str, Any],
        html_summary: Dict[str, Any],
        url: str,
        query: str
    ) -> PageAnalysisResult:
        """LLM 결과만으로 PageAnalysisResult 생성"""
        # visible_elements 생성
        visible_elements = []
        
        nav_structure = html_summary.get('navigation_structure', [])
        for i, menu in enumerate(nav_structure[:15]):
            from .state import ElementInfo
            visible_elements.append(ElementInfo(
                type='menu',
                text=menu['text'],
                href=menu.get('href'),
                description=f"네비게이션: {menu['text']}",
                coordinates={"x": 100 + i * 100, "y": 50},
                is_visible=True
            ))
        
        links = html_summary.get('links', [])[:15]
        for i, link in enumerate(links):
            from .state import ElementInfo
            visible_elements.append(ElementInfo(
                type='link',
                text=link['text'],
                href=link.get('href', ''),
                description=f"링크: {link['text']}",
                coordinates={"x": 100 + i * 80, "y": 150},
                is_visible=True
            ))
        
        # LLM 추천 액션 변환
        recommended_action = self._convert_llm_action_to_recommended(
            llm_dom_result, visible_elements, html_summary
        )
        
        return PageAnalysisResult(
            information_found=False,
            extracted_info=None,
            confidence=llm_dom_result.get('confidence', 0.5),
            page_type=html_summary.get('page_type', 'unknown'),
            title=html_summary.get('title', ''),
            summary=f"LLM DOM 분석 결과. {len(visible_elements)}개 요소.",
            visible_elements=visible_elements,
            recommended_action=recommended_action,
            has_navigation_menu=html_summary.get('has_navigation', False),
            has_search_box=html_summary.get('has_search', False),
            has_login_form=html_summary.get('has_login', False),
            requires_interaction=False,
            analysis_warnings=["VLM 실패, LLM DOM만 사용"]
        )
    
    def _create_emergency_fallback(
        self,
        html_summary: Dict[str, Any],
        url: str,
        query: str
    ) -> PageAnalysisResult:
        """VLM + LLM 모두 실패 시 최소 응답"""
        logger.error("모든 분석 실패 - 최소 응답 반환")
        
        return PageAnalysisResult(
            information_found=False,
            extracted_info=None,
            confidence=0.0,
            page_type=html_summary.get('page_type', 'unknown'),
            title=html_summary.get('title', ''),
            summary="VLM + LLM 모두 실패. 페이지 분석 불가.",
            visible_elements=[],
            recommended_action=None,
            has_navigation_menu=False,
            has_search_box=False,
            has_login_form=False,
            requires_interaction=False,
            analysis_warnings=[
                "VLM 분석 실패",
                "LLM DOM 분석 실패",
                "대안 도메인 탐색 필수"
            ]
        )