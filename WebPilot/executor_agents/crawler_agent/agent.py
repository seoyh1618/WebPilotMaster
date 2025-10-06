# WebPilot/executor_agents/crawler_agent/agent.py

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .state import *
from .list_extractor import ListExtractor
from .relevance_filter import RelevanceFilter
from .batch_analyzer import BatchAnalyzer
from .prompt import CRAWLER_DESCRIPTION, CRAWLER_INSTRUCTION  # ⭐ import
from WebPilot.constants import constants
import requests
from bs4 import BeautifulSoup
import json
import logging
import time

logger = logging.getLogger(__name__)

class CrawlerAgentClass:
    """Crawler Agent"""
    
    def __init__(self):
        self.extractor = None
        self.filter = RelevanceFilter()
        self.batch_analyzer = None
        logger.info("Crawler Agent 초기화")
    
    def run(self, input_text: str) -> str:
        """실행"""
        start_time = time.time()
        
        try:
            input_data = json.loads(input_text)
            crawler_input = CrawlerInput(**input_data)
            
            logger.info(f"크롤링 시작: {crawler_input.url}")
            
            # HTML 가져오기
            html = self._fetch_html(crawler_input.url)
            soup = BeautifulSoup(html, 'html.parser')
            
            # ListExtractor 초기화
            self.extractor = ListExtractor(crawler_input.url)
            
            # 리스트 페이지 확인
            is_list = self.extractor.is_list_page(soup)
            
            if not is_list:
                logger.warning("리스트 페이지 아님")
                return json.dumps(CrawlerOutput(
                    success=True,
                    is_list_page=False
                ).dict(), ensure_ascii=False)
            
            # 항목 추출
            raw_items = self.extractor.extract_items(soup, crawler_input.max_items)
            
            if not raw_items:
                return json.dumps(CrawlerOutput(
                    success=True,
                    is_list_page=True,
                    items=[]
                ).dict(), ensure_ascii=False)
            
            # 관련도 필터링
            if crawler_input.filter_by_relevance:
                filtered_items = self.filter.filter_and_rank(
                    raw_items,
                    crawler_input.query,
                    top_k=min(20, len(raw_items))
                )
            else:
                filtered_items = raw_items[:20]
            
            # ListItem 변환
            list_items = [
                ListItem(**item)
                for item in filtered_items
            ]
            
            # 페이지네이션
            pagination_dict = self.extractor.extract_pagination(soup)
            pagination = PaginationInfo(**pagination_dict)
            
            # 배치 분석
            detailed_analyses = []
            most_relevant = None
            
            if crawler_input.analyze_details and filtered_items:
                logger.info(f"배치 분석 시작 (Top-{crawler_input.detail_analysis_count})")
                
                from WebPilot.executor_agents.multimodal_perceiver_agent.agent import MultilmodalPerceiverAgentClass
                perceiver = MultilmodalPerceiverAgentClass()
                
                self.batch_analyzer = BatchAnalyzer(
                    perceiver,
                    max_workers=crawler_input.parallel_workers
                )
                
                analysis_results = self.batch_analyzer.analyze_multiple(
                    filtered_items,
                    crawler_input.query,
                    top_k=crawler_input.detail_analysis_count
                )
                
                detailed_analyses = [
                    DetailedAnalysis(**r)
                    for r in analysis_results
                ]
                
                successful = [a for a in detailed_analyses if a.success and a.information_found]
                if successful:
                    most_relevant = max(successful, key=lambda x: x.confidence)
            
            output = CrawlerOutput(
                success=True,
                is_list_page=True,
                items=list_items,
                pagination=pagination,
                total_items_found=len(raw_items),
                detailed_analyses=detailed_analyses,
                most_relevant_analysis=most_relevant
            )
            
            logger.info(f"✓ 크롤링 완료 ({time.time() - start_time:.2f}초)")
            
            return json.dumps(output.dict(), ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"크롤링 실패: {e}", exc_info=True)
            return json.dumps(CrawlerOutput(
                success=False,
                error_message=str(e)
            ).dict(), ensure_ascii=False)
    
    def _fetch_html(self, url: str) -> str:
        """HTML 가져오기"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            raise Exception(f"HTML 가져오기 실패: {e}")


# ⭐ prompt.py에서 import한 상수 사용
Crawler_Agent = Agent(
    name="CrawlerAgent",
    model=LiteLlm(model=constants.MODEL_O3_MINI),
    description=CRAWLER_DESCRIPTION,
    instruction=CRAWLER_INSTRUCTION
)