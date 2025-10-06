# WebPilot/executor_agents/filter_based_page_handler_agent/filter_strategy.py

from google.adk.models.lite_llm import LiteLlm
from WebPilot.constants import constants
from typing import List, Dict
import json
import logging

logger = logging.getLogger(__name__)

class FilterStrategy:
    """LLM 기반 필터 조작 전략"""
    
    def __init__(self):
        self.llm = LiteLlm(model=constants.MODEL_O3_MINI)
    
    def decide(self, filters: List[Dict], query: str, page_type: str) -> Dict:
        """필터 조작 전략 결정"""
        
        logger.info("전략 생성 중...")
        
        # 필터 정보 포맷팅
        filters_text = self._format_filters(filters)
        
        prompt = f"""다음 필터 페이지를 조작하여 '{query}'에 대한 정보를 조회하는 전략을 생성하세요.

        **페이지 타입**: {page_type}

        **질의**: {query}

        **사용 가능한 필터**:
        {filters_text}

        **전략 규칙**:
        1. 최소한의 필터만 조작 (1-3개)
        2. 질의와 직접 관련된 필터 우선
        3. 탭이 있으면 먼저 클릭
        4. 각 필터의 적절한 값 선택
        5. 명확한 순서 지정

        **출력 형식 (JSON)**:
        ```json
        {{
        "steps": [
            {{
            "step_number": 1,
            "filter_label": "학년도",
            "action": "select_option",
            "value": "2025학년도",
            "reasoning": "최신 학년도 선택"
            }},
            {{
            "step_number": 2,
            "filter_label": "학기",
            "action": "select_option",
            "value": "1학기",
            "reasoning": "현재 학기"
            }}
        ],
        "confidence": 0.8
        }}
        주의사항:

        action은 "select_option", "input_text", "click_tab", "click_button" 중 하나
        dropdown 필터는 options에 있는 값만 선택
        전략의 confidence (0-1)도 반환

        질의 '{query}'에 맞는 전략을 JSON으로 반환하세요.
        """
        try:
            response = self.llm.generate(prompt)
            
            # JSON 추출
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                strategy = json.loads(json_str)
            else:
                strategy = json.loads(response)
            
            steps = strategy.get('steps', [])
            confidence = strategy.get('confidence', 0.5)
            
            logger.info(f"✓ 전략 생성: {len(steps)}개 단계, confidence={confidence:.2f}")
            
            return {
                "steps": steps,
                "confidence": confidence
            }
            
        except Exception as e:
            logger.error(f"전략 생성 실패: {e}")
            
            # 폴백: 첫 번째 필터만
            return self._fallback_strategy(filters)

    def _format_filters(self, filters: List[Dict]) -> str:
        """필터 정보 포맷팅"""
        lines = []
        
        for i, f in enumerate(filters, 1):
            if f['type'] == 'dropdown':
                options_str = ', '.join(f.get('options', [])[:5])
                if len(f.get('options', [])) > 5:
                    options_str += ', ...'
                lines.append(f"{i}. [{f['type']}] {f['label']}: {options_str}")
            else:
                lines.append(f"{i}. [{f['type']}] {f['label']}")
        
        return '\n'.join(lines)

    def _fallback_strategy(self, filters: List[Dict]) -> Dict:
        """폴백 전략"""
        
        logger.warning("폴백 전략 사용")
        
        # 첫 번째 드롭다운 선택
        for f in filters:
            if f['type'] == 'dropdown' and f.get('options'):
                return {
                    "steps": [{
                        "step_number": 1,
                        "filter_label": f['label'],
                        "action": "select_option",
                        "value": f['options'][0],
                        "reasoning": "폴백: 첫 번째 옵션"
                    }],
                    "confidence": 0.3
                }
        
        return {"steps": [], "confidence": 0.0}

