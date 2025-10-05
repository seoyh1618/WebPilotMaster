# WebPilot/executor_agents/resource_selector_agent/cache.py

from typing import Dict, List, Optional, Tuple,Any
from datetime import datetime, timedelta
import numpy as np
import logging

logger = logging.getLogger(__name__)

class InMemoryEmbeddingCache:
    """메모리 기반 임베딩 캐시"""
    
    def __init__(self, ttl_minutes: int = 5):
        """
        Args:
            ttl_minutes: 캐시 유효 시간 (분)
        """
        self.cache: Dict[str, Dict] = {}
        self.ttl = timedelta(minutes=ttl_minutes)
        logger.info(f"메모리 캐시 초기화 (TTL: {ttl_minutes}분)")
    
    def get(self, domain_uri: str) -> Optional[Tuple[List[Dict], np.ndarray]]:
        """
        캐시에서 임베딩 조회
        
        Args:
            domain_uri: 도메인 URI
            
        Returns:
            (url_candidates, embeddings) 또는 None
        """
        if domain_uri not in self.cache:
            logger.debug(f"캐시 미스: {domain_uri}")
            return None
        
        cached = self.cache[domain_uri]
        
        # TTL 체크
        if datetime.now() - cached["timestamp"] > self.ttl:
            logger.debug(f"캐시 만료: {domain_uri}")
            del self.cache[domain_uri]
            return None
        
        logger.info(f"캐시 히트: {domain_uri} (URLs: {len(cached['url_candidates'])}개)")
        return cached["url_candidates"], cached["embeddings"]
    
    def set(self, domain_uri: str, url_candidates: List[Dict], embeddings: np.ndarray):
        """
        캐시에 임베딩 저장
        
        Args:
            domain_uri: 도메인 URI
            url_candidates: URL 후보 목록
            embeddings: 임베딩 벡터 배열
        """
        self.cache[domain_uri] = {
            "url_candidates": url_candidates,
            "embeddings": embeddings,
            "timestamp": datetime.now()
        }
        logger.info(f"캐시 저장: {domain_uri} (URLs: {len(url_candidates)}개)")
    
    def clear(self, domain_uri: Optional[str] = None):
        """
        캐시 삭제
        
        Args:
            domain_uri: 특정 도메인만 삭제 (None이면 전체 삭제)
        """
        if domain_uri:
            if domain_uri in self.cache:
                del self.cache[domain_uri]
                logger.info(f"캐시 삭제: {domain_uri}")
        else:
            self.cache.clear()
            logger.info("전체 캐시 삭제")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_urls = sum(len(c["url_candidates"]) for c in self.cache.values())
        return {
            "cached_domains": len(self.cache),
            "total_cached_urls": total_urls,
            "cache_entries": list(self.cache.keys())
        }

# 글로벌 캐시 인스턴스
embedding_cache = InMemoryEmbeddingCache(ttl_minutes=5)