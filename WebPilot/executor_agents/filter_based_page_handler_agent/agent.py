# WebPilot/executor_agents/filter_based_page_handler_agent/agent.py

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .state import *
from .filter_detector import FilterDetector
from .filter_extractor import FilterExtractor
from .filter_strategy import FilterStrategy
from .filter_executor import FilterExecutor
from .result_parser import ResultParser
from .prompt import FILTER_HANDLER_DESCRIPTION, FILTER_HANDLER_INSTRUCTION
from playwright.async_api import async_playwright
from WebPilot.constants import constants
import json
import logging
import asyncio
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class FilterBasedPageHandlerAgentClass:
    """Filter Based Page Handler"""
    
    def __init__(self):
        self.detector = FilterDetector()
        self.extractor = FilterExtractor()
        self.strategy = FilterStrategy()
        self.executor = FilterExecutor()
        self.parser = ResultParser()
        logger.info("FilterBasedPageHandler 초기화")
    
    def run(self, input_text: str) -> str:
        """동기 래퍼"""
        return asyncio.run(self._run_async(input_text))
    
    async def _run_async(self, input_text: str) -> str:
        start_time = time.time()
        
        try:
            input_data = json.loads(input_text)
            handler_input = FilterBasedPageHandlerInput(**input_data)
            
            logger.info(f"필터 페이지 처리 시작: {handler_input.url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                try:
                    # 1. 페이지 로드
                    logger.info("페이지 로딩...")
                    await page.goto(
                        handler_input.url,
                        wait_until="domcontentloaded",
                        timeout=30000
                    )
                    await asyncio.sleep(3)  # 동적 콘텐츠 로딩 대기
                    
                    html = await page.content()
                    
                    # 2. 필터 페이지 감지
                    detection = self.detector.detect(html, handler_input.url)
                    
                    if not detection['is_filter_page']:
                        logger.info("필터 페이지 아님")
                        return json.dumps(FilterBasedPageHandlerOutput(
                            success=True,
                            filter_info=FilterPageInfo(is_filter_page=False)
                        ).dict(), ensure_ascii=False)
                    
                    page_type = detection['page_type']
                    logger.info(f"✓ 필터 페이지: {page_type}")
                    
                    # 3. 필터 추출
                    extraction = self.extractor.extract(html, page_type)
                    filters = extraction['filters']
                    search_button = extraction['search_button']
                    
                    if not filters:
                        raise Exception("필터를 찾을 수 없습니다")
                    
                    logger.info(f"✓ {len(filters)}개 필터 추출")
                    
                    # 4. 전략 생성
                    strategy_dict = self.strategy.decide(
                        filters,
                        handler_input.query,
                        page_type
                    )
                    
                    steps = strategy_dict.get('steps', [])
                    confidence = strategy_dict.get('confidence', 0.5)
                    
                    if not steps:
                        raise Exception("전략 생성 실패")
                    
                    logger.info(f"✓ 전략: {len(steps)}개 단계 (confidence={confidence:.2f})")
                    
                    # 5. 필터 실행
                    success = await self.executor.execute(
                        page,
                        steps,
                        filters,
                        search_button
                    )
                    
                    if not success:
                        raise Exception("필터 조작 실패")
                    
                    logger.info("✓ 필터 조작 완료")
                    
                    # 6. 결과 파싱
                    result_html = await page.content()
                    result_rows = self.parser.parse(result_html, page_type)
                    
                    # FilterElement 변환
                    filter_elements = [FilterElement(**f) for f in filters]
                    search_btn_element = FilterElement(**search_button) if search_button else None
                    
                    # FilterStep 변환
                    filter_steps = [FilterStep(**s) for s in steps]
                    
                    # 출력 생성
                    output = FilterBasedPageHandlerOutput(
                        success=True,
                        filter_info=FilterPageInfo(
                            is_filter_page=True,
                            page_type=page_type,
                            page_title=detection.get('page_title', ''),
                            filters=filter_elements,
                            search_button=search_btn_element
                        ),
                        strategy_used=FilterManipulationStrategy(
                            steps=filter_steps,
                            estimated_time=time.time() - start_time,
                            confidence=confidence
                        ),
                        filters_manipulated=True,
                        results_found=len(result_rows) > 0,
                        result_rows=[ResultRow(**r) for r in result_rows],
                        total_results=len(result_rows)
                    )
                    
                    logger.info(f"✓ 처리 완료: {len(result_rows)}개 결과 ({time.time() - start_time:.2f}초)")
                    
                    return json.dumps(output.dict(), ensure_ascii=False, indent=2)
                    
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"필터 처리 실패: {e}", exc_info=True)
            
            # 스크린샷 (옵션)
            screenshot_path = None
            if handler_input.screenshot_on_error:
                try:
                    screenshot_path = f"/tmp/filter_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    await page.screenshot(path=screenshot_path)
                    logger.info(f"스크린샷 저장: {screenshot_path}")
                except:
                    pass
            
            return json.dumps(FilterBasedPageHandlerOutput(
                success=False,
                error_message=str(e),
                screenshot_path=screenshot_path
            ).dict(), ensure_ascii=False)


# Agent 생성
Filter_Based_Page_Handler_Agent = Agent(
    name="FilterBasedPageHandlerAgent",
    model=LiteLlm(model=constants.MODEL_O3_MINI),
    description=FILTER_HANDLER_DESCRIPTION,
    instruction=FILTER_HANDLER_INSTRUCTION
)