# WebPilot/executor_agents/answer_creation_agent/prompt.py
from typing import List, Dict, Optional
ANSWER_CREATION_DESCRIPTION = "수집된 정보를 종합하여 최종 답변을 생성하는 에이전트"

ANSWER_CREATION_INSTRUCTION = """
여러 소스에서 수집된 정보를 종합하여 명확하고 구조화된 답변을 생성합니다.

[처리 과정]
1. 정보 검증 및 통합
2. 중요도 순 정렬
3. 자연어 답변 생성
4. 출처 명시
"""

def create_answer_prompt(query: str, information: List[Dict], sources: List[Dict]) -> str:
    """답변 생성 프롬프트"""
    
    # 정보 포맷팅
    info_text = ""
    for i, info in enumerate(information[:5]):  # 최대 5개
        info_text += f"\n[정보 {i+1}]\n"
        info_text += f"출처: {info.get('source_url', 'N/A')}\n"
        info_text += f"내용: {info.get('content', '')}...\n"
    
    prompt = f"""다음 정보를 종합하여 사용자 질의에 대한 명확한 답변을 작성하세요.

**질의**: {query}

**수집된 정보**:
{info_text}

**답변 작성 지침**:

1. **구조화**
   - 핵심 답변을 먼저
   - 세부 사항은 그 다음
   - 단계별 절차는 번호 매기기

2. **명확성**
   - 간결하고 이해하기 쉽게
   - 전문 용어는 설명 추가
   - 날짜, 장소, 방법 등 구체적으로

3. **완전성**
   - 질의의 모든 측면 다룸
   - 추가 정보가 필요하면 명시

4. **출처 명시**
   - 중요한 정보는 출처 표시
   - 형식: (출처: URL)

**출력 형식**:
```json
{{{{
  "answer": "구조화된 답변 (마크다운 가능)",
  "confidence": 0.9,
  "additional_notes": "추가 참고 사항",
  "sources_used": [
    {{{{
      "url": "...",
      "title": "...",
      "excerpt": "관련 내용 발췌"
    }}}}
  ]
}}}}
예시:
질의: "사물함 신청 방법"
답변:
**사물함 신청 방법**

**신청 기간**: 2025년 3월 1일 ~ 3월 10일

**신청 방법**:
1. 학생포털(portal.ssu.ac.kr) 접속
2. '시설 이용 신청' 메뉴 선택
3. 사물함 신청 페이지에서 희망 위치 선택
4. 신청서 제출

**주의사항**:
- 선착순 배정
- 학기당 1개만 신청 가능
- 보증금 10,000원 필요

(출처: https://grad.ssu.ac.kr/notice/12345)
이제 답변을 작성하세요.
"""
    return prompt