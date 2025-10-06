# WebPilot/executor_agents/document_handler_agent/rag_pipeline.py

from typing import List, Dict
import numpy as np
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class RAGPipeline:
    """간단한 RAG 파이프라인 (TF-IDF 기반)"""
    
    def __init__(self, chunk_size: int = 500):
        self.chunk_size = chunk_size
        self.vectorizer = TfidfVectorizer(max_features=1000)
        logger.info(f"RAG Pipeline 초기화 (chunk_size={chunk_size})")
    
    def process_document(
        self,
        full_text: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:
        """
        문서를 처리하여 관련 chunks 반환
        
        Returns:
            [
                {
                    "chunk_id": 0,
                    "text": "...",
                    "similarity_score": 0.85
                }
            ]
        """
        
        logger.info("RAG 파이프라인 시작")
        
        # 1. 청킹
        chunks = self._chunk_text(full_text)
        logger.info(f"  - {len(chunks)}개 chunk 생성")
        
        if not chunks:
            return []
        
        # 2. 벡터화
        try:
            # 모든 텍스트 (query + chunks) 벡터화
            all_texts = [query] + chunks
            vectors = self.vectorizer.fit_transform(all_texts)
            
            # query 벡터
            query_vector = vectors[0:1]
            
            # chunk 벡터들
            chunk_vectors = vectors[1:]
            
            # 3. 유사도 계산
            similarities = cosine_similarity(query_vector, chunk_vectors)[0]
            
            # 4. Top-K 선택
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                results.append({
                    "chunk_id": int(idx),
                    "text": chunks[idx],
                    "similarity_score": float(similarities[idx])
                })
            
            logger.info(f"  - Top {top_k} chunks 선택 (최고 유사도: {results[0]['similarity_score']:.2f})")
            
            return results
            
        except Exception as e:
            logger.error(f"RAG 처리 실패: {e}")
            # 폴백: 첫 5개 chunk 반환
            return [
                {
                    "chunk_id": i,
                    "text": chunk,
                    "similarity_score": 0.5
                }
                for i, chunk in enumerate(chunks[:top_k])
            ]
    
    def _chunk_text(self, text: str) -> List[str]:
        """텍스트를 청킹"""
        
        # 문장 단위로 분리
        sentences = text.replace('\n', ' ').split('. ')
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.chunk_size:
                if current_chunk:
                    chunks.append('. '.join(current_chunk) + '.')
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length
        
        # 마지막 chunk
        if current_chunk:
            chunks.append('. '.join(current_chunk) + '.')
        
        return chunks