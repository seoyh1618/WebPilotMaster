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
    """VLM 응답 검증 (병렬 모드에서는 단순 검증만)"""
    
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
            
            # recommended_action 검증
            if parsed.get('recommended_action'):
                parsed['recommended_action'] = ResponseValidator._validate_recommended_action(
                    parsed['recommended_action'],
                    len(parsed['visible_elements'])
                )
            
            # PageAnalysisResult 생성
            analysis = PageAnalysisResult(**parsed)
            
            logger.info(f"VLM 응답 검증 완료: information_found={analysis.information_found}")
            if analysis.recommended_action:
                logger.info(f"VLM 추천: element_index={analysis.recommended_action.element_index}, "
                           f"confidence={analysis.recommended_action.confidence:.2f}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"VLM 응답 검증 실패: {e}")
            logger.error(f"원본 응답 (처음 500자):\n{raw_response[:500]}")
            raise ResponseValidationError(f"VLM 응답 검증 실패: {e}")
    
    @staticmethod
    def _extract_json(raw_response: str) -> Dict[str, Any]:
        """응답에서 JSON 추출"""
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
        if not isinstance(parsed.get('information_found'), bool):
            parsed['information_found'] = bool(parsed.get('information_found'))
        
        confidence = parsed.get('confidence', 0.0)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.0
        parsed['confidence'] = confidence
        
        if parsed.get('extracted_info') is not None:
            if not isinstance(parsed['extracted_info'], str):
                parsed['extracted_info'] = str(parsed['extracted_info'])
        
        valid_page_types = ['main_page', 'list_page', 'detail_page', 'form_page', 'login_page', 'error_page', 'unknown']
        if parsed.get('page_type') not in valid_page_types:
            parsed['page_type'] = 'unknown'
        
        parsed.setdefault('title', '')
        parsed.setdefault('summary', '')
        parsed.setdefault('visible_elements', [])
        parsed.setdefault('has_navigation_menu', False)
        parsed.setdefault('has_search_box', False)
        parsed.setdefault('has_login_form', False)
        parsed.setdefault('requires_interaction', False)
        parsed.setdefault('analysis_warnings', [])
        parsed.setdefault('recommended_action', None)
        
        if 'reasoning_process' not in parsed:
            parsed['reasoning_process'] = None
        
        return parsed
    
    @staticmethod
    def _validate_elements(elements: List[Dict]) -> List[ElementInfo]:
        """visible_elements 검증"""
        validated = []
        
        for elem in elements:
            try:
                if 'type' not in elem or 'text' not in elem:
                    continue
                
                valid_types = ['link', 'button', 'input', 'menu', 'text', 'image', 'form', 'dropdown']
                if elem['type'] not in valid_types:
                    elem['type'] = 'text'
                
                if 'coordinates' in elem and elem['coordinates']:
                    coords = elem['coordinates']
                    if isinstance(coords, str):
                        try:
                            coords = json.loads(coords)
                            elem['coordinates'] = coords
                        except json.JSONDecodeError:
                            elem['coordinates'] = None
                            coords = None
                    
                    if coords and (not isinstance(coords, dict) or 'x' not in coords or 'y' not in coords):
                        elem['coordinates'] = None
                    elif coords:
                        try:
                            elem['coordinates']['x'] = max(0, float(coords['x']))
                            elem['coordinates']['y'] = max(0, float(coords['y']))
                        except (ValueError, TypeError):
                            elem['coordinates'] = None
                
                elem.setdefault('href', None)
                elem.setdefault('selector', None)
                elem.setdefault('description', '')
                elem.setdefault('is_visible', True)
                
                element_info = ElementInfo(**elem)
                validated.append(element_info)
                
            except Exception as e:
                logger.warning(f"요소 검증 실패: {e}")
                continue
        
        logger.info(f"요소 검증 완료: {len(validated)}/{len(elements)}개")
        return validated
    
    @staticmethod
    def _validate_recommended_action(
        action: Dict[str, Any],
        num_elements: int
    ) -> Optional[RecommendedAction]:
        """recommended_action 검증"""
        try:
            if not isinstance(action.get('should_click'), bool):
                action['should_click'] = bool(action.get('should_click'))
            
            if not action['should_click']:
                return None
            
            element_index = action.get('element_index')
            if element_index is None:
                return None
            
            try:
                element_index = int(element_index)
            except (ValueError, TypeError):
                return None
            
            if element_index < 0 or element_index >= num_elements:
                return None
            
            action['element_index'] = element_index
            
            valid_action_types = ['click', 'hover', 'goto']
            if action.get('action_type') not in valid_action_types:
                action['action_type'] = 'click'
            
            confidence = action.get('confidence', 0.0)
            try:
                confidence = float(confidence)
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, TypeError):
                confidence = 0.5
            action['confidence'] = confidence
            
            if 'coordinates' in action and action['coordinates']:
                coords = action['coordinates']
                if isinstance(coords, str):
                    try:
                        coords = json.loads(coords)
                        action['coordinates'] = coords
                    except json.JSONDecodeError:
                        action['coordinates'] = None
                        coords = None
                
                if coords and (not isinstance(coords, dict) or 'x' not in coords or 'y' not in coords):
                    action['coordinates'] = None
                elif coords:
                    try:
                        action['coordinates']['x'] = max(0, float(coords['x']))
                        action['coordinates']['y'] = max(0, float(coords['y']))
                    except (ValueError, TypeError):
                        action['coordinates'] = None
            
            if 'is_fallback' not in action:
                action['is_fallback'] = False
            
            alternatives = action.get('alternative_elements', [])
            if not isinstance(alternatives, list):
                alternatives = []
            
            valid_alternatives = []
            for alt in alternatives:
                try:
                    alt_idx = int(alt)
                    if 0 <= alt_idx < num_elements and alt_idx != element_index:
                        valid_alternatives.append(alt_idx)
                except (ValueError, TypeError):
                    continue
            
            action['alternative_elements'] = valid_alternatives
            
            action.setdefault('element_text', '')
            action.setdefault('href', None)
            action.setdefault('reasoning', '')
            action.setdefault('requires_submenu_selection', False)
            action.setdefault('visible_submenus', [])
            action.setdefault('recommended_submenu_index', None)
            action.setdefault('should_download', False)
            action.setdefault('file_info', None)
            
            recommended = RecommendedAction(**action)
            
            logger.info(f"추천 액션 검증 완료: [{recommended.element_index}] {recommended.element_text} "
                       f"(confidence: {recommended.confidence:.2f})")
            
            return recommended
            
        except Exception as e:
            logger.error(f"recommended_action 검증 실패: {e}")
            return None