# WebPilot/executor_agents/multimodal_perceiver_agent/dom_analyzer.py

from openai import OpenAI
from typing import Dict, Any, List, Optional
import logging
import os
import json
import re
from WebPilot.constants import constants

logger = logging.getLogger(__name__)

class DOMAnalyzerError(Exception):
    """DOM 분석 오류"""
    pass

class DOMAnalyzer:
    """LLM 기반 DOM 구조 의미적 분석"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise DOMAnalyzerError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
        
        self.client = OpenAI(api_key=api_key)
        self.model = constants.MODEL_O3_MINI  # 텍스트 분석용 LLM
        
        logger.info(f"DOM Analyzer 초기화 (모델: {self.model})")
    
    def analyze_structure(
        self,
        html_summary: Dict[str, Any],
        query: str,
        vlm_failed: bool = False
    ) -> Dict[str, Any]:
        """
        HTML 구조를 의미적으로 분석하여 다음 액션 추천
        
        Args:
            html_summary: HTML 파서 결과
            query: 사용자 질의
            vlm_failed: VLM이 실패했는지 여부
            
        Returns:
            {
                "recommended_element_index": int,
                "recommended_element_text": str,
                "action_type": "click" | "hover",
                "confidence": float,
                "reasoning": str,
                "requires_submenu": bool,
                "submenu_index": Optional[int],
                "alternative_indices": List[int],
                "reasoning_chain": Dict  # 상세 추론 과정
            }
        """
        logger.info(f"DOM 구조 분석 시작: {query}")
        logger.info(f"VLM 실패 여부: {vlm_failed}")
        
        try:
            # 프롬프트 생성
            prompt = self._create_dom_analysis_prompt(html_summary, query, vlm_failed)
            
            logger.debug(f"DOM 분석 프롬프트 길이: {len(prompt)} 문자")
            
            # LLM 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 웹페이지 DOM 구조를 분석하는 전문가입니다. HTML 구조를 보고 사용자 질의에 가장 적합한 네비게이션 경로를 의미적으로 추론합니다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            if not content:
                raise DOMAnalyzerError("LLM 응답이 비어있습니다")
            
            # 토큰 사용량
            if hasattr(response, 'usage'):
                logger.info(f"LLM 토큰: {response.usage.total_tokens}")
            
            # JSON 파싱
            result = self._parse_llm_response(content)
            
            logger.info(f"DOM 분석 완료:")
            logger.info(f"  추천: [{result.get('recommended_element_index')}] {result.get('recommended_element_text')}")
            logger.info(f"  확신도: {result.get('confidence', 0):.2f}")
            logger.info(f"  이유: {result.get('reasoning', '')[:100]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"DOM 분석 실패: {e}", exc_info=True)
            raise DOMAnalyzerError(f"DOM 분석 실패: {e}")
    
    def _create_dom_analysis_prompt(
        self,
        html_summary: Dict[str, Any],
        query: str,
        vlm_failed: bool
    ) -> str:
        """DOM 분석 프롬프트 생성"""
        
        # 네비게이션 구조 포맷팅
        nav_structure = html_summary.get('navigation_structure', [])
        nav_text = ""
        nav_count = 0
        
        if nav_structure:
            nav_text = "**네비게이션 구조:**\n"
            for i, menu in enumerate(nav_structure[:15]):
                nav_text += f"[{i}] {menu['text']}"
                nav_count += 1
                
                if menu.get('has_submenu'):
                    nav_text += " **[드롭다운]**"
                    submenus = menu.get('submenus', [])
                    if submenus:
                        submenu_names = [s['text'] for s in submenus[:8]]
                        nav_text += f"\n    하위메뉴: {', '.join(submenu_names)}"
                
                nav_text += "\n"
        else:
            nav_text = "**네비게이션 구조:** 없음\n"
        
        # 주요 링크
        links = html_summary.get('links', [])[:20]
        links_text = ""
        links_start_index = nav_count
        
        if links:
            links_text = f"\n**주요 링크 (인덱스 {links_start_index}부터):**\n"
            for i, link in enumerate(links):
                actual_index = links_start_index + i
                links_text += f"[{actual_index}] {link['text']}\n"
        
        # VLM 실패 여부에 따른 컨텍스트
        context = ""
        if vlm_failed:
            context = """
⚠️ **VLM 분석 실패**: 스크린샷 분석이 실패했습니다.
→ HTML 구조만으로 의미적 분석을 수행해야 합니다.
→ 더 신중하게 분석하고, 확신도를 보수적으로 평가하세요.
"""
        else:
            context = """
✅ **VLM + LLM 하이브리드**: VLM 결과를 보완하기 위한 분석입니다.
→ VLM이 놓쳤을 수 있는 구조적 패턴을 찾으세요.
→ VLM과 다른 추천도 괜찮습니다 (확신도만 정확히).
"""
        
        prompt = f"""당신은 웹페이지 DOM 구조를 의미적으로 분석하는 전문가입니다.

{context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 **사용자 질의:** "{query}"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 **페이지 정보:**
- 제목: {html_summary.get('title', 'N/A')}
- 타입: {html_summary.get('page_type', 'unknown')}

{nav_text}{links_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 **분석 과제:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

위 HTML 구조를 보고 **5단계 추론**을 수행하세요:

**1단계: 의미적 분석**
   - 사용자가 찾는 정보는 어떤 카테고리에 속하는가?
   - 예: "신청" → 행정 절차, "장학금" → 학생 지원

**2단계: 일반적인 웹사이트 패턴**
   - 이런 정보는 보통 어디에 있는가?
   - 예: 신청 안내 → 공지사항, 시설 이용 → 학생지원

**3단계: HTML 구조 탐색**
   - 드롭다운 하위메뉴 분석
   - 메뉴 이름과 내용의 관계 파악
   - 직접 매칭 vs 간접 추론

**4단계: 확신도 평가**
   - 직접 매칭 (예: "장학금" 메뉴에 "장학금" 하위) → high (0.8~0.95)
   - 간접 추론 (예: "사물함 신청" → 공지사항) → medium (0.6~0.8)
   - 약한 추론 (예: 관련성 낮음) → low (0.3~0.6)
   - 추측 (예: 아무 단서 없음) → very low (0.1~0.3)

**5단계: 대안 제시**
   - 다른 가능성 있는 요소들

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 **출력 형식 (JSON만):**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{
  "reasoning_chain": {{
    "step1_semantic_category": "질의의 의미적 카테고리",
    "step2_typical_location": "일반적인 웹사이트에서 위치",
    "step3_structural_clues": "HTML에서 발견한 단서",
    "step4_best_match": "가장 적합한 요소",
    "step5_confidence_rationale": "확신도 평가 근거"
  }},
  "recommended_element_index": 1,
  "recommended_element_text": "정확히 위 HTML의 텍스트",
  "action_type": "click",
  "confidence": 0.75,
  "reasoning": "요약된 추천 이유",
  "requires_submenu": false,
  "submenu_index": null,
  "alternative_indices": [2, 5]
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ **중요 규칙:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **인덱스 정확히**: 위 HTML에 나온 인덱스만 사용
2. **텍스트 정확히**: element_text는 HTML의 정확한 텍스트
3. **확신도 정직하게**: 근거 약하면 낮게
4. **드롭다운 감지**: has_submenu이면 requires_submenu: true
5. **대안 제시**: alternative_indices에 차선책 2-3개

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 **예시:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**예시 1: 직접 매칭**

질의: "장학금 신청"
HTML:
  [0] 학사안내
  [1] 학생지원 [드롭다운]
      하위: 장학금, 생활관, 동아리

분석:
{{
  "reasoning_chain": {{
    "step1_semantic_category": "학생 복지/지원 - 장학금",
    "step2_typical_location": "학생지원 섹션",
    "step3_structural_clues": "[1] 학생지원 > 장학금 (직접 매칭)",
    "step4_best_match": "[1] 학생지원, 하위[0] 장학금",
    "step5_confidence_rationale": "high (0.9) - 하위메뉴에 정확히 존재"
  }},
  "recommended_element_index": 1,
  "recommended_element_text": "학생지원",
  "action_type": "hover",
  "confidence": 0.9,
  "reasoning": "학생지원 드롭다운 하위에 '장학금' 직접 명시",
  "requires_submenu": true,
  "submenu_index": 0,
  "alternative_indices": []
}}

**예시 2: 간접 추론**

질의: "사물함 신청 방법"
HTML:
  [0] 정보광장 [드롭다운]
      하위: 공지사항, FAQ
  [1] 학생지원

분석:
{{
  "reasoning_chain": {{
    "step1_semantic_category": "시설 이용 절차 - 행정 안내",
    "step2_typical_location": "공지사항에 안내 게시",
    "step3_structural_clues": "[0] 정보광장 > 공지사항 (간접 추론)",
    "step4_best_match": "[0] 정보광장, 하위[0] 공지사항",
    "step5_confidence_rationale": "medium (0.7) - 일반적 패턴 기반"
  }},
  "recommended_element_index": 0,
  "recommended_element_text": "정보광장",
  "action_type": "hover",
  "confidence": 0.7,
  "reasoning": "사물함 신청 안내는 보통 공지사항에 게시. 정보광장 > 공지사항 탐색",
  "requires_submenu": true,
  "submenu_index": 0,
  "alternative_indices": [1]
}}

**예시 3: 낮은 확신도**

질의: "주차 등록"
HTML:
  [0] 학사안내
  [1] 입학정보

분석:
{{
  "reasoning_chain": {{
    "step1_semantic_category": "시설 이용",
    "step2_typical_location": "학생지원 또는 시설관리",
    "step3_structural_clues": "관련 메뉴 없음",
    "step4_best_match": "[0] 학사안내 (약한 추론)",
    "step5_confidence_rationale": "low (0.3) - 명확한 단서 없음"
  }},
  "recommended_element_index": 0,
  "recommended_element_text": "학사안내",
  "action_type": "click",
  "confidence": 0.3,
  "reasoning": "관련 메뉴 없음. 학사안내가 가장 광범위. 대안 도메인 권장",
  "requires_submenu": false,
  "submenu_index": null,
  "alternative_indices": []
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**지금 위 HTML을 분석하고 JSON만 출력하세요.**
"""
        
        return prompt
    
    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """LLM 응답 파싱"""
        
        # JSON 코드 블록 제거
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content.strip()
        
        try:
            result = json.loads(json_str)
            
            # 필수 필드 검증
            required = ['recommended_element_index', 'recommended_element_text', 'confidence', 'reasoning']
            for field in required:
                if field not in result:
                    raise DOMAnalyzerError(f"필수 필드 누락: {field}")
            
            # 타입 변환
            result['recommended_element_index'] = int(result['recommended_element_index'])
            result['confidence'] = float(result['confidence'])
            result['confidence'] = max(0.0, min(1.0, result['confidence']))
            
            # 기본값
            result.setdefault('action_type', 'click')
            result.setdefault('requires_submenu', False)
            result.setdefault('submenu_index', None)
            result.setdefault('alternative_indices', [])
            result.setdefault('reasoning_chain', {})
            
            # reasoning_chain 로깅
            if result.get('reasoning_chain'):
                logger.debug("LLM 추론 과정:")
                for step, value in result['reasoning_chain'].items():
                    logger.debug(f"  {step}: {value}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패:\n{content[:500]}")
            raise DOMAnalyzerError(f"유효하지 않은 JSON: {e}")