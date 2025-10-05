# WebPilot/executor_agents/multimodal_perceiver_agent/response_validator.py

from typing import Dict, Any, List, Optional
import json
import re
import logging
from .state import PageAnalysisResult, ElementInfo, RecommendedAction

logger = logging.getLogger(__name__)

class ResponseValidationError(Exception):
    """응답 검증 오류"""
    pass

class ResponseValidator:
    """VLM 응답 검증 및 수정"""
    
    @staticmethod
    def validate_and_parse(raw_response: str) -> PageAnalysisResult:
        """
        VLM 응답을 검증하고 PageAnalysisResult로 변환
        
        Args:
            raw_response: VLM 원본 응답
            
        Returns:
            PageAnalysisResult 객체
            
        Raises:
            ResponseValidationError: 검증 실패 시
        """
        try:
            # JSON 추출
            parsed = ResponseValidator._extract_json(raw_response)
            
            # 필수 필드 검증
            ResponseValidator._validate_required_fields(parsed)
            
            # 타입 검증 및 수정
            parsed = ResponseValidator._validate_types(parsed)
            
            # visible_elements 검증
            parsed['visible_elements'] = ResponseValidator._validate_elements(
                parsed.get('visible_elements', [])
            )
            
            # ⭐ recommended_action 검증 (새로 추가)
            if parsed.get('recommended_action'):
                parsed['recommended_action'] = ResponseValidator._validate_recommended_action(
                    parsed['recommended_action'],
                    len(parsed['visible_elements'])
                )
            
            # PageAnalysisResult 생성
            analysis = PageAnalysisResult(**parsed)
            
            logger.info(f"응답 검증 완료: information_found={analysis.information_found}")
            if analysis.recommended_action:
                logger.info(f"추천 액션: element_index={analysis.recommended_action.element_index}, "
                           f"confidence={analysis.recommended_action.confidence:.2f}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"응답 검증 실패: {e}")
            raise ResponseValidationError(f"VLM 응답 검증 실패: {e}")
    
    @staticmethod
    def _extract_json(raw_response: str) -> Dict[str, Any]:
        """응답에서 JSON 추출"""
        # JSON 코드 블록 제거
        json_match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = raw_response.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패:\n{json_str[:500]}")
            raise ResponseValidationError(f"유효하지 않은 JSON: {e}")
    
    @staticmethod
    def _validate_required_fields(parsed: Dict) -> None:
        """필수 필드 존재 확인"""
        required = ['information_found', 'page_type', 'title', 'summary']
        
        missing = [field for field in required if field not in parsed]
        
        if missing:
            raise ResponseValidationError(f"필수 필드 누락: {missing}")
    
    @staticmethod
    def _validate_types(parsed: Dict) -> Dict:
        """타입 검증 및 수정"""
        # information_found: boolean
        if not isinstance(parsed.get('information_found'), bool):
            logger.warning("information_found 타입 수정")
            parsed['information_found'] = bool(parsed.get('information_found'))
        
        # confidence: float (0.0 ~ 1.0)
        confidence = parsed.get('confidence', 0.0)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.0
        parsed['confidence'] = confidence
        
        # extracted_info: string or null
        if parsed.get('extracted_info') is not None:
            if not isinstance(parsed['extracted_info'], str):
                parsed['extracted_info'] = str(parsed['extracted_info'])
        
        # page_type: string
        valid_page_types = ['main_page', 'list_page', 'detail_page', 'form_page', 'login_page', 'error_page', 'unknown']
        if parsed.get('page_type') not in valid_page_types:
            logger.warning(f"잘못된 page_type: {parsed.get('page_type')}, 'unknown'으로 수정")
            parsed['page_type'] = 'unknown'
        
        # 기본값 설정
        parsed.setdefault('title', '')
        parsed.setdefault('summary', '')
        parsed.setdefault('visible_elements', [])
        parsed.setdefault('keyword_matches', {})
        parsed.setdefault('has_navigation_menu', False)
        parsed.setdefault('has_search_box', False)
        parsed.setdefault('has_login_form', False)
        parsed.setdefault('requires_interaction', False)
        parsed.setdefault('analysis_warnings', [])
        parsed.setdefault('recommended_action', None)
        
        return parsed
    
    @staticmethod
    def _validate_elements(elements: List[Dict]) -> List[ElementInfo]:
        """visible_elements 검증"""
        validated = []
        
        for elem in elements:
            try:
                # 필수 필드
                if 'type' not in elem or 'text' not in elem:
                    logger.warning(f"요소 필드 누락, 건너뜀: {repr(elem)}")
                    continue
                
                # 타입 검증
                valid_types = ['link', 'button', 'input', 'menu', 'text', 'image', 'form', 'dropdown']
                if elem['type'] not in valid_types:
                    logger.warning(f"잘못된 요소 타입: {elem['type']}, 'text'로 수정")
                    elem['type'] = 'text'
                
                # coordinates 검증
                if 'coordinates' in elem and elem['coordinates']:
                    coords = elem['coordinates']
                    
                    # ⭐ 문자열로 들어온 경우 dict로 파싱
                    if isinstance(coords, str):
                        try:
                            coords = json.loads(coords)
                            elem['coordinates'] = coords
                        except json.JSONDecodeError:
                            logger.warning(f"요소 좌표 파싱 실패, 제거: {repr(coords)}")
                            elem['coordinates'] = None
                            coords = None
                    
                    # dict 검증
                    if coords and (not isinstance(coords, dict) or 'x' not in coords or 'y' not in coords):
                        logger.warning(f"잘못된 좌표 형식, 제거: {repr(coords)}")
                        elem['coordinates'] = None
                    elif coords:
                        try:
                            # 음수 좌표 수정
                            elem['coordinates']['x'] = max(0, float(coords['x']))
                            elem['coordinates']['y'] = max(0, float(coords['y']))
                        except (ValueError, TypeError) as e:
                            logger.warning(f"좌표 값 변환 실패: {repr(coords)}, 오류: {e}")
                            elem['coordinates'] = None
                
                # 기본값
                elem.setdefault('href', None)
                elem.setdefault('selector', None)
                elem.setdefault('description', '')
                elem.setdefault('is_visible', True)
                
                # ElementInfo 생성
                element_info = ElementInfo(**elem)
                validated.append(element_info)
                
            except Exception as e:
                logger.warning(f"요소 검증 실패, 건너뜀: {repr(elem)}, 오류: {e}")
                continue
        
        logger.info(f"요소 검증 완료: {len(validated)}/{len(elements)}개")
        
        return validated
    
    @staticmethod
    def _validate_recommended_action(
        action: Dict[str, Any],
        num_elements: int
    ) -> Optional[RecommendedAction]:
        """
        recommended_action 검증 (새로 추가)
        
        Args:
            action: recommended_action 딕셔너리
            num_elements: visible_elements 개수
            
        Returns:
            RecommendedAction 객체 또는 None
        """
        try:
            # should_click 검증
            if not isinstance(action.get('should_click'), bool):
                action['should_click'] = bool(action.get('should_click'))
            
            # should_click == false면 None 반환
            if not action['should_click']:
                logger.info("추천 액션 없음 (should_click: false)")
                return None
            
            # element_index 검증
            element_index = action.get('element_index')
            if element_index is None:
                logger.warning("element_index 누락")
                return None
            
            try:
                element_index = int(element_index)
            except (ValueError, TypeError):
                logger.warning(f"잘못된 element_index: {element_index}")
                return None
            
            # 인덱스 범위 검증
            if element_index < 0 or element_index >= num_elements:
                logger.warning(f"element_index 범위 초과: {element_index} (총 {num_elements}개)")
                return None
            
            action['element_index'] = element_index
            
            # action_type 검증
            valid_action_types = ['click', 'hover', 'goto']
            if action.get('action_type') not in valid_action_types:
                logger.warning(f"잘못된 action_type: {action.get('action_type')}, 'click'으로 수정")
                action['action_type'] = 'click'
            
            # confidence 검증
            confidence = action.get('confidence', 0.0)
            try:
                confidence = float(confidence)
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, TypeError):
                confidence = 0.5
            action['confidence'] = confidence
            
            # confidence가 너무 낮으면 경고
            if confidence < 0.3:
                logger.warning(f"confidence가 매우 낮음: {confidence:.2f}")
            
            # coordinates 검증
            if 'coordinates' in action and action['coordinates']:
                coords = action['coordinates']
                
                # ⭐ 문자열로 들어온 경우 dict로 파싱 시도
                if isinstance(coords, str):
                    try:
                        coords = json.loads(coords)
                        action['coordinates'] = coords
                    except json.JSONDecodeError:
                        logger.warning(f"좌표 파싱 실패, 제거: {repr(coords)}")
                        action['coordinates'] = None
                        coords = None
                
                # dict 검증
                if coords and (not isinstance(coords, dict) or 'x' not in coords or 'y' not in coords):
                    logger.warning(f"잘못된 좌표 형식, 제거: {repr(coords)}")
                    action['coordinates'] = None
                elif coords:
                    try:
                        action['coordinates']['x'] = max(0, float(coords['x']))
                        action['coordinates']['y'] = max(0, float(coords['y']))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"좌표 값 변환 실패, 제거: {repr(coords)}, 오류: {e}")
                        action['coordinates'] = None
            # is_fallback 검증
            if 'is_fallback' not in action:
                action['is_fallback'] = False
            elif not isinstance(action['is_fallback'], bool):
                action['is_fallback'] = bool(action['is_fallback'])
            
            # alternative_elements 검증
            alternatives = action.get('alternative_elements', [])
            if not isinstance(alternatives, list):
                alternatives = []
            
            # 유효한 인덱스만 유지
            valid_alternatives = []
            for alt in alternatives:
                try:
                    alt_idx = int(alt)
                    if 0 <= alt_idx < num_elements and alt_idx != element_index:
                        valid_alternatives.append(alt_idx)
                except (ValueError, TypeError):
                    continue
            
            action['alternative_elements'] = valid_alternatives
            
            # 기본값 설정
            action.setdefault('element_text', '')
            action.setdefault('href', None)
            action.setdefault('reasoning', '')
            
            # RecommendedAction 생성
            recommended = RecommendedAction(**action)
            
            logger.info(f"추천 액션 검증 완료: [{recommended.element_index}] {recommended.element_text} "
                       f"(confidence: {recommended.confidence:.2f})")
            
            return recommended
            
        except Exception as e:
            logger.error(f"recommended_action 검증 실패: {e}")
            return None
    
    @staticmethod
    def create_fallback_response(
        url: str,
        query: str,
        html_summary: Dict[str, Any],
        error_message: str
    ) -> PageAnalysisResult:
        """
        VLM 실패 시 HTML 파서만으로 기본 응답 생성
        
        Args:
            url: 페이지 URL
            query: 사용자 질의
            html_summary: HTML 파서 결과
            error_message: 오류 메시지
            
        Returns:
            기본 PageAnalysisResult
        """
        logger.warning(f"VLM 실패, 폴백 응답 생성: {error_message}")
        
        # 키워드 검색 (간단한 매칭)
        keywords = ResponseValidator._extract_keywords(query)
        main_text = html_summary.get('main_text', '').lower()
        
        keyword_found = any(keyword in main_text for keyword in keywords)
        
        # 기본 요소 생성 (HTML에서)
        visible_elements = []
        
        for i, link in enumerate(html_summary.get('links', [])[:5]):
            visible_elements.append(ElementInfo(
                type='link',
                text=link['text'],
                href=link['href'],
                description=f"링크: {link['text']}",
                coordinates={"x": 100 + i * 100, "y": 100}  # 대략적 추정
            ))
        
        for i, button in enumerate(html_summary.get('buttons', [])[:3]):
            visible_elements.append(ElementInfo(
                type='button',
                text=button['text'],
                description=f"버튼: {button['text']}",
                coordinates={"x": 100 + i * 100, "y": 200}
            ))
        
        # 폴백 추천 액션 (휴리스틱 기반)
        recommended_action = ResponseValidator._create_fallback_recommendation(
            query=query,
            visible_elements=visible_elements,
            html_summary=html_summary
        )
        
        return PageAnalysisResult(
            information_found=False,  # 보수적으로 false
            extracted_info=None,
            confidence=0.3,  # 낮은 신뢰도
            page_type=html_summary.get('page_type', 'unknown'),
            title=html_summary.get('title', ''),
            summary=f"이 페이지는 {html_summary.get('page_type', '알 수 없는')} 타입입니다. VLM 분석 실패로 제한된 정보만 제공됩니다.",
            visible_elements=visible_elements,
            keyword_matches={},
            recommended_action=recommended_action,
            has_navigation_menu=html_summary.get('has_navigation', False),
            has_search_box=html_summary.get('has_search', False),
            has_login_form=html_summary.get('has_login', False),
            requires_interaction=False,
            analysis_warnings=[f"VLM 분석 실패: {error_message}", "HTML 파서만으로 제한된 분석 수행"]
        )
    
    @staticmethod
    def _create_fallback_recommendation(
        query: str,
        visible_elements: List[ElementInfo],
        html_summary: Dict[str, Any]
    ) -> Optional[RecommendedAction]:
        """
        VLM 실패 시 휴리스틱 기반 폴백 추천
        
        우선순위:
        1. "공지사항" 찾기
        2. menu 타입 찾기
        3. 첫 번째 링크
        """
        if not visible_elements:
            return None
        
        query_lower = query.lower()
        
        # 1순위: "공지사항" 찾기
        for i, elem in enumerate(visible_elements):
            text = elem.text.lower()
            if any(keyword in text for keyword in ['공지', 'notice', '안내', 'news']):
                logger.info(f"폴백 추천: '공지사항' 메뉴 발견 [{i}] {elem.text}")
                return RecommendedAction(
                    should_click=True,
                    element_index=i,
                    element_text=elem.text,
                    action_type='click',
                    coordinates=elem.coordinates,
                    href=elem.href,
                    confidence=0.5,
                    reasoning="VLM 실패로 휴리스틱 선택. '공지사항'에 정보가 있을 가능성이 있습니다.",
                    is_fallback=True,
                    alternative_elements=[]
                )
        
        # 2순위: menu 타입 찾기
        menu_elements = [(i, e) for i, e in enumerate(visible_elements) if e.type == 'menu']
        if menu_elements:
            i, elem = menu_elements[0]
            logger.info(f"폴백 추천: 첫 번째 메뉴 [{i}] {elem.text}")
            return RecommendedAction(
                should_click=True,
                element_index=i,
                element_text=elem.text,
                action_type='click',
                coordinates=elem.coordinates,
                href=elem.href,
                confidence=0.4,
                reasoning="VLM 실패로 휴리스틱 선택. 첫 번째 메뉴를 시도합니다.",
                is_fallback=True,
                alternative_elements=[]
            )
        
        # 3순위: 첫 번째 링크
        logger.info(f"폴백 추천: 첫 번째 요소 [{0}] {visible_elements[0].text}")
        return RecommendedAction(
            should_click=True,
            element_index=0,
            element_text=visible_elements[0].text,
            action_type='click',
            coordinates=visible_elements[0].coordinates,
            href=visible_elements[0].href,
            confidence=0.3,
            reasoning="VLM 실패로 휴리스틱 선택. 첫 번째 요소를 시도합니다.",
            is_fallback=True,
            alternative_elements=[]
        )
    
    @staticmethod
    def _extract_keywords(query: str) -> List[str]:
        """질의에서 키워드 추출 (간단한 버전)"""
        # 불용어 제거
        stopwords = {'은', '는', '이', '가', '을', '를', '의', '에', '에서', '로', '으로', 
                     '와', '과', '알려줘', '알려주세요', '해줘', '해주세요', '있나요', '어디'}
        
        words = query.split()
        keywords = [w.lower() for w in words if w not in stopwords and len(w) > 1]
        
        return keywords
    """VLM 응답 검증 및 수정"""
    
    @staticmethod
    def validate_and_parse(raw_response: str) -> PageAnalysisResult:
        """
        VLM 응답을 검증하고 PageAnalysisResult로 변환
        
        Args:
            raw_response: VLM 원본 응답
            
        Returns:
            PageAnalysisResult 객체
            
        Raises:
            ResponseValidationError: 검증 실패 시
        """
        try:
            # JSON 추출
            parsed = ResponseValidator._extract_json(raw_response)
            
            # 필수 필드 검증
            ResponseValidator._validate_required_fields(parsed)
            
            # 타입 검증 및 수정
            parsed = ResponseValidator._validate_types(parsed)
            
            # visible_elements 검증
            parsed['visible_elements'] = ResponseValidator._validate_elements(
                parsed.get('visible_elements', [])
            )
            
            # PageAnalysisResult 생성
            analysis = PageAnalysisResult(**parsed)
            
            logger.info(f"응답 검증 완료: information_found={analysis.information_found}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"응답 검증 실패: {e}")
            raise ResponseValidationError(f"VLM 응답 검증 실패: {e}")
    
    @staticmethod
    def _extract_json(raw_response: str) -> Dict[str, Any]:
        """응답에서 JSON 추출"""
        # JSON 코드 블록 제거
        json_match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = raw_response.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패:\n{json_str[:500]}")
            raise ResponseValidationError(f"유효하지 않은 JSON: {e}")
    
    @staticmethod
    def _validate_required_fields(parsed: Dict) -> None:
        """필수 필드 존재 확인"""
        required = ['information_found', 'page_type', 'title', 'summary']
        
        missing = [field for field in required if field not in parsed]
        
        if missing:
            raise ResponseValidationError(f"필수 필드 누락: {missing}")
    
    @staticmethod
    def _validate_types(parsed: Dict) -> Dict:
        """타입 검증 및 수정"""
        # information_found: boolean
        if not isinstance(parsed.get('information_found'), bool):
            logger.warning("information_found 타입 수정")
            parsed['information_found'] = bool(parsed.get('information_found'))
        
        # confidence: float (0.0 ~ 1.0)
        confidence = parsed.get('confidence', 0.0)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.0
        parsed['confidence'] = confidence
        
        # extracted_info: string or null
        if parsed.get('extracted_info') is not None:
            if not isinstance(parsed['extracted_info'], str):
                parsed['extracted_info'] = str(parsed['extracted_info'])
        
        # page_type: string
        valid_page_types = ['main_page', 'list_page', 'detail_page', 'form_page', 'login_page', 'error_page', 'unknown']
        if parsed.get('page_type') not in valid_page_types:
            logger.warning(f"잘못된 page_type: {parsed.get('page_type')}, 'unknown'으로 수정")
            parsed['page_type'] = 'unknown'
        
        # 기본값 설정
        parsed.setdefault('title', '')
        parsed.setdefault('summary', '')
        parsed.setdefault('visible_elements', [])
        parsed.setdefault('keyword_matches', {})
        parsed.setdefault('has_navigation_menu', False)
        parsed.setdefault('has_search_box', False)
        parsed.setdefault('has_login_form', False)
        parsed.setdefault('requires_interaction', False)
        parsed.setdefault('analysis_warnings', [])
        
        return parsed
    
    @staticmethod
    def _validate_elements(elements: List[Dict]) -> List[ElementInfo]:
        """visible_elements 검증"""
        validated = []
        
        for elem in elements:
            try:
                # 필수 필드
                if 'type' not in elem or 'text' not in elem:
                    logger.warning(f"요소 필드 누락, 건너뜀: {elem}")
                    continue
                
                # 타입 검증
                valid_types = ['link', 'button', 'input', 'menu', 'text', 'image', 'form', 'dropdown']
                if elem['type'] not in valid_types:
                    logger.warning(f"잘못된 요소 타입: {elem['type']}, 'text'로 수정")
                    elem['type'] = 'text'
                
                # coordinates 검증
                if 'coordinates' in elem and elem['coordinates']:
                    coords = elem['coordinates']
                    
                    # ⭐ 문자열로 들어온 경우 dict로 파싱
                    if isinstance(coords, str):
                        try:
                            coords = json.loads(coords)
                            elem['coordinates'] = coords
                        except json.JSONDecodeError:
                            logger.warning(f"요소 좌표 파싱 실패, 제거: {repr(coords)}")
                            elem['coordinates'] = None
                            coords = None
                    
                    # dict 검증
                    if coords and (not isinstance(coords, dict) or 'x' not in coords or 'y' not in coords):
                        logger.warning(f"잘못된 좌표 형식, 제거: {repr(coords)}")
                        elem['coordinates'] = None
                    elif coords:
                        try:
                            # 음수 좌표 수정
                            elem['coordinates']['x'] = max(0, float(coords['x']))
                            elem['coordinates']['y'] = max(0, float(coords['y']))
                        except (ValueError, TypeError) as e:
                            logger.warning(f"좌표 값 변환 실패: {repr(coords)}, 오류: {e}")
                            elem['coordinates'] = None
                
                # 기본값
                elem.setdefault('href', None)
                elem.setdefault('selector', None)
                elem.setdefault('description', '')
                elem.setdefault('is_visible', True)
                
                # ElementInfo 생성
                element_info = ElementInfo(**elem)
                validated.append(element_info)
                
            except Exception as e:
                logger.warning(f"요소 검증 실패, 건너뜀: {elem}, 오류: {e}")
                continue
        
        logger.info(f"요소 검증 완료: {len(validated)}/{len(elements)}개")
        
        return validated
    
    @staticmethod
    def create_fallback_response(
        url: str,
        query: str,
        html_summary: Dict[str, Any],
        error_message: str
    ) -> PageAnalysisResult:
        """
        VLM 실패 시 HTML 파서만으로 기본 응답 생성
        
        Args:
            url: 페이지 URL
            query: 사용자 질의
            html_summary: HTML 파서 결과
            error_message: 오류 메시지
            
        Returns:
            기본 PageAnalysisResult
        """
        logger.warning(f"VLM 실패, 폴백 응답 생성: {error_message}")
        
        # 키워드 검색 (간단한 매칭)
        keywords = ResponseValidator._extract_keywords(query)
        main_text = html_summary.get('main_text', '').lower()
        
        keyword_found = any(keyword in main_text for keyword in keywords)
        
        # 기본 요소 생성 (HTML에서)
        visible_elements = []
        
        for i, link in enumerate(html_summary.get('links', [])[:5]):
            visible_elements.append(ElementInfo(
                type='link',
                text=link['text'],
                href=link['href'],
                description=f"링크: {link['text']}",
                coordinates={"x": 100 + i * 100, "y": 100}  # 대략적 추정
            ))
        
        for i, button in enumerate(html_summary.get('buttons', [])[:3]):
            visible_elements.append(ElementInfo(
                type='button',
                text=button['text'],
                description=f"버튼: {button['text']}",
                coordinates={"x": 100 + i * 100, "y": 200}
            ))
        
        return PageAnalysisResult(
            information_found=False,  # 보수적으로 false
            extracted_info=None,
            confidence=0.3,  # 낮은 신뢰도
            page_type=html_summary.get('page_type', 'unknown'),
            title=html_summary.get('title', ''),
            summary=f"이 페이지는 {html_summary.get('page_type', '알 수 없는')} 타입입니다. VLM 분석 실패로 제한된 정보만 제공됩니다.",
            visible_elements=visible_elements,
            keyword_matches={},
            has_navigation_menu=html_summary.get('has_navigation', False),
            has_search_box=html_summary.get('has_search', False),
            has_login_form=html_summary.get('has_login', False),
            requires_interaction=False,
            analysis_warnings=[f"VLM 분석 실패: {error_message}", "HTML 파서만으로 제한된 분석 수행"]
        )
    
    @staticmethod
    def _extract_keywords(query: str) -> List[str]:
        """질의에서 키워드 추출 (간단한 버전)"""
        # 불용어 제거
        stopwords = {'은', '는', '이', '가', '을', '를', '의', '에', '에서', '로', '으로', '와', '과', '알려줘', '알려주세요', '해줘', '해주세요'}
        
        words = query.split()
        keywords = [w.lower() for w in words if w not in stopwords and len(w) > 1]
        
        return keywords