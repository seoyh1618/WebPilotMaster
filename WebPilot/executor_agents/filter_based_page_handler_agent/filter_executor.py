# WebPilot/executor_agents/filter_based_page_handler_agent/filter_executor.py

from playwright.async_api import Page
import asyncio
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class FilterExecutor:
    """Playwright 기반 필터 실행"""
    
    async def execute(
        self,
        page: Page,
        steps: List[Dict],
        filters: List[Dict],
        search_button: Optional[Dict]
    ) -> bool:
        """필터 조작 실행"""
        
        try:
            for step in steps:
                logger.info(f"[단계 {step['step_number']}] {step['filter_label']}")
                
                # 필터 찾기
                target_filter = self._find_filter(filters, step['filter_label'])
                
                if not target_filter:
                    logger.warning(f"  필터 못 찾음: {step['filter_label']}")
                    continue
                
                # 액션 실행
                action = step['action']
                
                if action == 'select_option':
                    await self._select_option(page, target_filter, step.get('value'))
                
                elif action == 'input_text':
                    await self._input_text(page, target_filter, step.get('value'))
                
                elif action == 'click_tab':
                    await self._click_element(page, target_filter)
                
                elif action == 'click_button':
                    await self._click_element(page, target_filter)
                
                # 대기
                wait_time = step.get('wait_after', 1.5)
                await asyncio.sleep(wait_time)
            
            # 검색 버튼 클릭
            if search_button:
                logger.info("검색 버튼 클릭")
                await self._click_search_button(page, search_button)
                
                # 결과 로딩 대기
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    logger.info("  결과 로딩 완료")
                except:
                    logger.warning("  네트워크 대기 타임아웃")
                
                await asyncio.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"필터 실행 실패: {e}")
            return False
    
    def _find_filter(self, filters: List[Dict], label: str) -> Optional[Dict]:
        """라벨로 필터 찾기"""
        for f in filters:
            if f['label'] == label or label in f['label'] or f['label'] in label:
                return f
        return None
    
    async def _select_option(self, page: Page, filter_elem: Dict, value: str):
        """드롭다운 선택"""
        try:
            selector = filter_elem['selector']
            options = filter_elem.get('options', [])
            
            # 정확히 일치하는 값
            if value in options:
                await page.select_option(selector, value)
                logger.info(f"  선택: {value}")
                return
            
            # 부분 일치
            for option in options:
                if value in option or option in value:
                    await page.select_option(selector, option)
                    logger.info(f"  선택: {option}")
                    return
            
            # 못 찾으면 첫 번째
            if options:
                await page.select_option(selector, options[0])
                logger.warning(f"  값 못 찾음, 첫 번째 선택: {options[0]}")
        
        except Exception as e:
            logger.error(f"  선택 실패: {e}")
            # XPath로 재시도
            try:
                await page.locator(f"xpath={filter_elem['xpath']}").select_option(value)
            except:
                pass
    
    async def _input_text(self, page: Page, filter_elem: Dict, value: str):
        """텍스트 입력"""
        try:
            selector = filter_elem['selector']
            await page.fill(selector, value)
            logger.info(f"  입력: {value}")
        except Exception as e:
            logger.error(f"  입력 실패: {e}")
    
    async def _click_element(self, page: Page, filter_elem: Dict):
        """요소 클릭"""
        try:
            selector = filter_elem['selector']
            await page.click(selector)
            logger.info(f"  클릭: {filter_elem['label']}")
        except Exception as e:
            logger.error(f"  클릭 실패: {e}")
            # XPath로 재시도
            try:
                await page.locator(f"xpath={filter_elem['xpath']}").click()
            except:
                pass
    
    async def _click_search_button(self, page: Page, button: Dict):
        """검색 버튼 클릭"""
        try:
            selector = button['selector']
            await page.click(selector)
        except Exception as e:
            logger.error(f"검색 버튼 클릭 실패: {e}")
            # XPath로 재시도
            try:
                await page.locator(f"xpath={button['xpath']}").click()
            except:
                pass