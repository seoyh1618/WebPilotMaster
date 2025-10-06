# WebPilot/executor_agents/crawler_agent/relevance_filter.py

from typing import List, Dict
from google.adk.models.lite_llm import LiteLlm
from WebPilot.constants import constants
import logging
import json

logger = logging.getLogger(__name__)

class RelevanceFilter:
    """관련도 필터링"""
    
    def __init__(self):
        self.llm = LiteLlm(model=constants.MODEL_O3_MINI)
    
    def filter_and_rank(
        self,
        items: List[Dict],
        query: str,
        top_k: int = 10
    ) -> List[Dict]:
        """관련도 계산 및 정렬"""
        
        if not items:
            return []
        
        logger.info(f"관련도 계산: {len(items)}개 항목")
        
        # 배치 크기
        batch_size = 20
        all_scores = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            scores = self._calculate_batch(batch, query)
            all_scores.extend(scores)
        
        # 점수 할당
        for item, score in zip(items, all_scores):
            item['relevance_score'] = score
        
        # 정렬
        sorted_items = sorted(items, key=lambda x: x['relevance_score'], reverse=True)
        
        logger.info(f"✓ Top {min(top_k, len(sorted_items))}개 선정 (최고: {sorted_items[0]['relevance_score']:.2f})")
        
        return sorted_items[:top_k]
    
    def _calculate_batch(self, items: List[Dict], query: str) -> List[float]:
        """배치 관련도 계산"""
        
        titles = [item['title'] for item in items]
        titles_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)])
        
        prompt = f"""다음 게시글 제목들이 질의와 얼마나 관련 있는지 0-1 사이 점수로 평가하세요.

        **질의**: {query}

        **제목들**:
        {titles_text}

        **평가 기준**:
        - 1.0: 질의와 정확히 일치
        - 0.8-0.9: 매우 관련 (핵심 키워드 포함)
        - 0.5-0.7: 관련 있음
        - 0.3-0.4: 약간 관련
        - 0.0-0.2: 관련 없음

        **출력 (JSON 배열)**:
        ```json
        [0.95, 0.3, 0.8, ...]
        각 제목의 점수를 순서대로 배열로 반환하세요.
        """
        try:
            response = self.llm.generate(prompt)
            
            # JSON 추출
            json_match = re.search(r'\[[\d.,\s]+\]', response)
            if json_match:
                scores = json.loads(json_match.group())
            else:
                scores = json.loads(response)
            
            # 길이 맞추기
            if len(scores) < len(titles):
                scores.extend([0.0] * (len(titles) - len(scores)))
            
            return scores[:len(titles)]
            
        except Exception as e:
            logger.error(f"LLM 평가 실패: {e}, 폴백")
            return self._simple_matching(titles, query)
    def _simple_matching(self, titles: List[str], query: str) -> List[float]:
        """폴백: 키워드 매칭"""
        
        keywords = query.lower().split()
        scores = []
        
        for title in titles:
            title_lower = title.lower()
            matches = sum(1 for kw in keywords if kw in title_lower)
            score = min(matches / max(len(keywords), 1), 1.0)
            scores.append(score)
        
        return scores