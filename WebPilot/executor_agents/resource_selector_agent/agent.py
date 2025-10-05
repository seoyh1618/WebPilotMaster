# WebPilot/executor_agents/resource_selector_agent/agent.py

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .prompt import RESOURCE_SELECTOR_DESCRIPTION, RESOURCE_SELECTOR_INSTRUCTION
from .state import (
    ResourceSelectorInput,
    ResourceSelectorOutput,
    ScoredURL,
    URLCandidate
)
from .cache import embedding_cache
from .crawler import crawl_urls_sync
from .embedder import embedding_generator
from .selector import URLSelector
from WebPilot.constants.constants import MODEL_O3_MINI
import json
import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ResourceSelectorAgentClass:
    """Resource Selector Agent 구현"""
    
    def __init__(self, model_name: str = MODEL_O3_MINI):
        self.llm = LiteLlm(model=model_name)
        self.agent = Agent(
            name="ResourceSelector",
            model=self.llm,
            description=RESOURCE_SELECTOR_DESCRIPTION,
            instruction=RESOURCE_SELECTOR_INSTRUCTION
        )
        logger.info("Resource Selector Agent 초기화 완료")
    
    def run(self, input_text: str) -> str:
        """
        AgentTool 인터페이스 호환 메서드
        
        Args:
            input_text: JSON 형식 입력
            
        Returns:
            JSON 형식 출력
        """
        start_time = time.time()
        
        try:
            # 입력 파싱
            input_data = json.loads(input_text)
            selector_input = ResourceSelectorInput(**input_data)
            
            logger.info(f"URL 탐색 시작: {selector_input.primary_domain} ({selector_input.query})")
            
            # 캐시 확인
            cached = embedding_cache.get(selector_input.primary_uri)
            cache_hit = cached is not None
            
            if cache_hit:
                url_candidates, candidate_embeddings = cached
                logger.info(f"캐시 히트: {len(url_candidates)}개 URL")
            else:
                # 크롤링 + 임베딩 생성
                url_candidates, candidate_embeddings = self._crawl_and_embed(selector_input)
                
                # 캐시 저장
                embedding_cache.set(
                    selector_input.primary_uri,
                    url_candidates,
                    candidate_embeddings
                )
            
            # 사용자 질의 임베딩
            query_embedding = embedding_generator.generate_single_embedding(selector_input.query)
            
            # URL 선택
            selector = URLSelector(
                top_k=selector_input.top_k,
                min_score=selector_input.min_score
            )
            selected_urls = selector.select_urls(
                query_embedding,
                url_candidates,
                candidate_embeddings
            )
            
            # 결과 생성
            output = ResourceSelectorOutput(
                selected_urls=[
                    ScoredURL(
                        url=url["url"],
                        title=url["title"],
                        similarity_score=url["similarity_score"],
                        reasoning=url["reasoning"],
                        metadata={
                            "parent_menu": url.get("parent_menu", ""),
                            "link_text": url.get("link_text", ""),
                            "depth": url.get("depth", 1)
                        }
                    )
                    for url in selected_urls
                ],
                total_candidates=len(url_candidates),
                filtered_out=len(url_candidates) - len(selected_urls),
                execution_time=time.time() - start_time,
                cache_hit=cache_hit
            )
            
            logger.info(f"URL 탐색 완료: {len(output.selected_urls)}개 선택")
            
            return json.dumps(output.dict(), ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Resource Selector 실행 실패: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "selected_urls": [],
                "total_candidates": 0,
                "filtered_out": 0,
                "execution_time": time.time() - start_time
            }, ensure_ascii=False)
    
    def _crawl_and_embed(self, selector_input: ResourceSelectorInput):
        """크롤링 + 임베딩 생성"""
        # 1. URL 크롤링
        url_candidates = crawl_urls_sync(
            selector_input.primary_uri,
            max_depth=selector_input.max_depth
        )
        
        if not url_candidates:
            logger.warning(f"크롤링 결과 없음: {selector_input.primary_uri}")
            return [], []
        
        # 2. 임베딩 텍스트 생성 (title + parent_menu + context)
        embedding_texts = [
            f"{url['title']} {url.get('parent_menu', '')} {url.get('context', '')}"
            for url in url_candidates
        ]
        
        # 3. 배치 임베딩 생성
        candidate_embeddings = embedding_generator.generate_embeddings(embedding_texts)
        
        return url_candidates, candidate_embeddings


# AgentTool이 사용할 Agent 인스턴스
Resource_Selector_Agent = Agent(
    name="ResourceSelector",
    model=LiteLlm(model=MODEL_O3_MINI),
    description=RESOURCE_SELECTOR_DESCRIPTION,
    instruction=RESOURCE_SELECTOR_INSTRUCTION
)