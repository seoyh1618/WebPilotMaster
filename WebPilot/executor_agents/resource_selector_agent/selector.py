# WebPilot/executor_agents/resource_selector_agent/selector.py

import numpy as np
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

def cosine_similarity_manual(query_embedding: np.ndarray, candidate_embeddings: np.ndarray) -> np.ndarray:
    """
    코사인 유사도 직접 구현 (scikit-learn 대체)
    
    Args:
        query_embedding: 질의 임베딩 벡터 (1D array)
        candidate_embeddings: 후보 임베딩 배열 (2D array: [N, embedding_dim])
        
    Returns:
        유사도 배열 (1D array: [N])
    """
    # 벡터 정규화
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    candidates_norm = candidate_embeddings / np.linalg.norm(candidate_embeddings, axis=1, keepdims=True)
    
    # 내적 계산 (코사인 유사도)
    similarities = np.dot(candidates_norm, query_norm)
    
    return similarities

class URLSelector:
    """유사도 기반 URL 선택기"""
    
    def __init__(self, top_k: int = 3, min_score: float = 0.6):
        """
        Args:
            top_k: 반환할 최대 URL 개수
            min_score: 최소 유사도 점수
        """
        self.top_k = top_k
        self.min_score = min_score
    
    def select_urls(
        self,
        query_embedding: np.ndarray,
        url_candidates: List[Dict],
        candidate_embeddings: np.ndarray
    ) -> List[Dict]:
        """
        유사도 기반 Top-K URL 선택
        
        Args:
            query_embedding: 사용자 질의 임베딩
            url_candidates: URL 후보 목록
            candidate_embeddings: URL 후보 임베딩 배열
            
        Returns:
            선택된 URL 목록 (점수 포함)
        """
        if len(url_candidates) == 0 or len(candidate_embeddings) == 0:
            logger.warning("빈 후보 목록")
            return []
        
        logger.info(f"URL 선택 시작: {len(url_candidates)}개 후보")
        
        # 코사인 유사도 계산 (직접 구현)
        similarities = cosine_similarity_manual(query_embedding, candidate_embeddings)
        
        # URL에 점수 추가
        scored_urls = []
        for i, (url_info, score) in enumerate(zip(url_candidates, similarities)):
            scored_urls.append({
                **url_info,
                "similarity_score": float(score),
                "rank": i + 1
            })
        
        # 점수 기준 정렬
        scored_urls.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        # 필터링: 최소 점수 이상
        filtered = [url for url in scored_urls if url["similarity_score"] >= self.min_score]
        
        # 필터링: 1위와 점수 차이가 큰 것 제거 (0.2 이상 차이)
        if filtered:
            top_score = filtered[0]["similarity_score"]
            filtered = [
                url for url in filtered
                if top_score - url["similarity_score"] <= 0.2
            ]
        
        # Top-K 선택
        selected = filtered[:self.top_k]
        
        logger.info(f"URL 선택 완료: {len(selected)}개 선택 (필터링: {len(scored_urls) - len(selected)}개)")
        
        # 선택 이유 추가
        for url in selected:
            url["reasoning"] = self._generate_reasoning(url)
        
        return selected
    
    def _generate_reasoning(self, scored_url: Dict) -> str:
        """선택 이유 생성"""
        score = scored_url["similarity_score"]
        title = scored_url.get("title", "")
        parent_menu = scored_url.get("parent_menu", "")
        
        if score >= 0.85:
            reason = f"질의와 매우 높은 유사도 ({score:.2f})"
        elif score >= 0.70:
            reason = f"질의와 높은 유사도 ({score:.2f})"
        else:
            reason = f"질의와 관련성 있음 ({score:.2f})"
        
        if parent_menu:
            reason += f", 메뉴: {parent_menu}"
        
        return reason