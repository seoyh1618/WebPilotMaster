# WebPilot/executor_agents/resource_selector_agent/embedder.py

from openai import OpenAI
from typing import List
import numpy as np
import logging
from WebPilot.constants import constants as config

logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    """OpenAI Embeddings API 래퍼"""
    
    def __init__(self, model: str = "text-embedding-3-small"):
        """
        Args:
            model: 임베딩 모델명
        """
        self.client = OpenAI()
        self.model = model
        logger.info(f"Embedding Generator 초기화 (모델: {model})")
    
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        텍스트 배치 임베딩 생성
        
        Args:
            texts: 텍스트 목록 (최대 100개 권장)
            
        Returns:
            임베딩 벡터 배열 (shape: [len(texts), embedding_dim])
        """
        if not texts:
            logger.warning("빈 텍스트 리스트")
            return np.array([])
        
        logger.info(f"임베딩 생성 시작: {len(texts)}개 텍스트")
        
        try:
            # OpenAI API 호출
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            
            # 임베딩 벡터 추출
            embeddings = [item.embedding for item in response.data]
            embeddings_array = np.array(embeddings)
            
            logger.info(f"임베딩 생성 완료 (shape: {embeddings_array.shape})")
            
            return embeddings_array
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            raise
    
    def generate_single_embedding(self, text: str) -> np.ndarray:
        """단일 텍스트 임베딩 생성"""
        embeddings = self.generate_embeddings([text])
        return embeddings[0] if len(embeddings) > 0 else np.array([])

# 글로벌 인스턴스
embedding_generator = EmbeddingGenerator()