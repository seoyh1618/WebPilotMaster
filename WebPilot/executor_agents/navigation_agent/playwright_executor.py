# WebPilot/executor_agents/navigation_agent/playwright_executor.py

from playwright.async_api import async_playwright, Page, Browser, Error as PlaywrightError
from typing import Optional, List
import asyncio
import logging
from .state import NavigationAction, NavigationResult
from WebPilot.constants import constants

logger = logging.getLogger(__name__)

class PlaywrightExecutorError(Exception):
    """Playwright 실행 오류"""
    pass

class PlaywrightExecutor:
    """Playwright 기반 네비게이션 액션 실행"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.timeout = constants.PLAYWRIGHT_TIMEOUT
    
    async def execute_actions(
        self,
        actions: List[NavigationAction],
        start_url: Optional[str] = None
    ) -> List[NavigationResult]:
        """
        액션 시퀀스 실행
        
        Args:
            actions: 실행할 액션 리스트
            start_url: 시작 URL
            
        Returns:
            각 액션의 실행 결과 리스트
        """
        results = []
    
        async with async_playwright() as p:
            try:
                # 브라우저 시작
                self.browser = await p.chromium.launch(
                    headless=constants.PLAYWRIGHT_HEADLESS,
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                self.page = await self.browser.new_page(
                    viewport={
                        "width": constants.PERCEIVER_VIEWPORT_WIDTH,
                        "height": constants.PERCEIVER_VIEWPORT_HEIGHT
                    }
                )
                
                self.page.set_default_timeout(self.timeout)
                
                # 시작 URL로 이동
                if start_url:
                    logger.info(f"━━━ 시작 URL ━━━")
                    logger.info(f"  이동: {start_url}")
                    await self.page.goto(start_url, wait_until="domcontentloaded")
                    await asyncio.sleep(1)
                    logger.info(f"  현재 URL: {self.page.url}")
                
                # 액션 순차 실행
                for i, action in enumerate(actions):
                    logger.info(f"━━━ 액션 {i+1}/{len(actions)} ━━━")
                    logger.info(f"  타입: {action.action_type}")
                    logger.info(f"  설명: {action.description}")
                    
                    url_before = self.page.url
                    
                    try:
                        result = await self._execute_single_action(action)
                        results.append(result)
                        
                        url_after = self.page.url
                        
                        if url_before != url_after:
                            logger.info(f"  ✓ URL 변경: {url_before} → {url_after}")
                        else:
                            logger.info(f"  - URL 유지: {url_after}")
                        
                        if not result.success:
                            logger.warning(f"  ✗ 액션 실패: {result.error_message}")
                    
                    except Exception as e:
                        logger.error(f"  ✗ 오류: {e}")
                        results.append(NavigationResult(
                            success=False,
                            error_message=str(e),
                            current_url=self.page.url
                        ))
                
                # 최종 상태
                final_url = self.page.url
                final_title = await self.page.title()
                
                logger.info(f"━━━ 완료 ━━━")
                logger.info(f"  성공: {sum(1 for r in results if r.success)}/{len(actions)}")
                logger.info(f"  최종 URL: {final_url}")
                logger.info(f"  페이지 제목: {final_title}")
                
                return results
                
            finally:
                if self.browser:
                    await self.browser.close()

    async def _execute_single_action(self, action: NavigationAction) -> NavigationResult:
        """단일 액션 실행"""
        import time
        start_time = time.time()
        
        try:
            if action.action_type == "goto":
                await self._action_goto(action)
            elif action.action_type == "click":
                await self._action_click(action)
            elif action.action_type == "type":
                await self._action_type(action)
            elif action.action_type == "wait":
                await self._action_wait(action)
            elif action.action_type == "scroll":
                await self._action_scroll(action)
            elif action.action_type == "hover":
                await self._action_hover(action)
            elif action.action_type == "back":
                await self.page.go_back(wait_until="domcontentloaded")
            elif action.action_type == "forward":
                await self.page.go_forward(wait_until="domcontentloaded")
            elif action.action_type == "reload":
                await self.page.reload(wait_until="domcontentloaded")
            else:
                raise PlaywrightExecutorError(f"지원하지 않는 액션: {action.action_type}")
            
            # 결과 생성
            current_url = self.page.url
            
            result = NavigationResult(
                success=True,
                current_url=current_url,  # ⭐ 실제 브라우저 URL
                page_title=await self.page.title(),
                execution_time=time.time() - start_time,
                is_loaded=True
            )
            
            return result
            
        except Exception as e:
            logger.error(f"  액션 실패: {e}")
            return NavigationResult(
                success=False,
                current_url=self.page.url,  # 실패해도 현재 URL
                error_message=str(e),
                execution_time=time.time() - start_time
            )

    async def _action_goto(self, action: NavigationAction):
        """페이지 이동"""
        response = await self.page.goto(
            action.url,
            wait_until="domcontentloaded",
            timeout=self.timeout
        )
        
        if response and response.status >= 400:
            raise PlaywrightExecutorError(f"HTTP {response.status}: {action.url}")
        
        await asyncio.sleep(1)
    
    async def _action_click(self, action: NavigationAction):
        """클릭"""
        if action.coordinates:
            await self.page.mouse.click(
                action.coordinates['x'],
                action.coordinates['y']
            )
            logger.info(f"    좌표: ({action.coordinates['x']}, {action.coordinates['y']})")
        elif action.selector:
            await self.page.click(action.selector)
            logger.info(f"    selector: {action.selector}")
        else:
            raise PlaywrightExecutorError("클릭 대상 없음")
        
        # 페이지 변화 대기
        try:
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except:
            logger.debug("    networkidle 타임아웃 (계속 진행)")
        
        await asyncio.sleep(1)
    
    async def _action_type(self, action: NavigationAction):
        """텍스트 입력"""
        if action.selector:
            await self.page.fill(action.selector, action.text)
        elif action.coordinates:
            await self.page.mouse.click(action.coordinates['x'], action.coordinates['y'])
            await asyncio.sleep(0.5)
            await self.page.keyboard.type(action.text)
        else:
            await self.page.keyboard.type(action.text)
    
    async def _action_wait(self, action: NavigationAction):
        """대기"""
        if action.wait_for:
            if action.wait_for == "networkidle":
                await self.page.wait_for_load_state("networkidle")
            elif action.wait_for == "domcontentloaded":
                await self.page.wait_for_load_state("domcontentloaded")
            elif action.wait_for == "load":
                await self.page.wait_for_load_state("load")
        elif action.duration:
            await asyncio.sleep(action.duration)
        else:
            await asyncio.sleep(1)
    
    async def _action_scroll(self, action: NavigationAction):
        """스크롤"""
        if action.direction == "top":
            await self.page.evaluate("window.scrollTo(0, 0)")
        elif action.direction == "bottom":
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif action.direction == "down":
            pixels = action.pixels or 300
            await self.page.evaluate(f"window.scrollBy(0, {pixels})")
        elif action.direction == "up":
            pixels = action.pixels or 300
            await self.page.evaluate(f"window.scrollBy(0, -{pixels})")
        
        await asyncio.sleep(0.5)
    
    async def _action_hover(self, action: NavigationAction):
        """마우스 호버"""
        if action.coordinates:
            await self.page.mouse.move(action.coordinates['x'], action.coordinates['y'])
            logger.info(f"    좌표: ({action.coordinates['x']}, {action.coordinates['y']})")
        elif action.selector:
            await self.page.hover(action.selector)
            logger.info(f"    selector: {action.selector}")
        else:
            raise PlaywrightExecutorError("호버 대상 없음")
        
        await asyncio.sleep(1.5)  # 드롭다운 대기


# ⭐ 동기 래퍼 함수 (올바른 정의)
def execute_actions_sync(
    actions: List[NavigationAction],
    start_url: Optional[str] = None
) -> List[NavigationResult]:
    """동기 방식으로 액션 실행 (asyncio.run 사용)"""
    executor = PlaywrightExecutor()
    return asyncio.run(executor.execute_actions(actions, start_url))