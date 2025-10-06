# WebPilot/executor_agents/multimodal_perceiver_agent/screenshot.py

from playwright.async_api import async_playwright, Page, Error as PlaywrightError
import base64
from pathlib import Path
import logging
import asyncio
from typing import Optional, Tuple
from WebPilot.constants import constants

logger = logging.getLogger(__name__)

class ScreenshotCaptureError(Exception):
    """스크린샷 캡처 오류"""
    pass

class ScreenshotCapture:
    """Playwright 기반 스크린샷 캡처 (재시도 로직 포함)"""
    
    def __init__(self):
        # constants에서 직접 참조
        self.viewport_width = constants.PERCEIVER_VIEWPORT_WIDTH
        self.viewport_height = constants.PERCEIVER_VIEWPORT_HEIGHT
        self.page_timeout = constants.PERCEIVER_PAGE_TIMEOUT
        self.wait_after_load = constants.PERCEIVER_WAIT_AFTER_LOAD
        self.max_retries = constants.PERCEIVER_MAX_RETRIES
        self.retry_delay = constants.PERCEIVER_RETRY_DELAY
        self.save_screenshots = constants.PERCEIVER_SAVE_SCREENSHOTS
        self.screenshot_dir = constants.PERCEIVER_SCREENSHOT_DIR
        
        # 파일 저장 활성화 시에만 디렉토리 생성 시도
        if self.save_screenshots:
            try:
                screenshot_dir = Path(self.screenshot_dir)
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"스크린샷 저장 활성화: {screenshot_dir.absolute()}")
            except Exception as e:
                logger.warning(f"스크린샷 디렉토리 생성 실패 (저장 비활성화): {e}")
                self.save_screenshots = False  # 실패 시 저장 비활성화
        else:
            logger.info("스크린샷 저장 비활성화 (메모리만 사용)")
    
    async def capture(self, url: str, save_path: Optional[str] = None) -> Tuple[str, str]:
        """
        URL의 스크린샷 및 HTML 캡처 (재시도 포함)
        
        Args:
            url: 대상 URL
            save_path: 스크린샷 저장 경로 (선택)
            
        Returns:
            (base64_image, html_content)
            
        Raises:
            ScreenshotCaptureError: 캡처 실패 시
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"스크린샷 캡처 시도 {attempt + 1}/{self.max_retries}: {url}")
                
                result = await self._capture_once(url, save_path)
                
                logger.info(f"스크린샷 캡처 성공: {url}")
                return result
                
            except PlaywrightError as e:
                logger.warning(f"캡처 실패 (시도 {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise ScreenshotCaptureError(f"최대 재시도 횟수 초과: {e}")
            
            except Exception as e:
                logger.error(f"예상치 못한 오류: {e}")
                raise ScreenshotCaptureError(f"스크린샷 캡처 실패: {e}")
    
    async def _capture_once(self, url: str, save_path: Optional[str]) -> Tuple[str, str]:
        """단일 캡처 시도"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=constants.PLAYWRIGHT_HEADLESS,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            try:
                page = await browser.new_page(
                    viewport={
                        "width": self.viewport_width,
                        "height": self.viewport_height
                    },
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                
                # 타임아웃 설정
                page.set_default_timeout(self.page_timeout)
                
                # 페이지 로딩
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.page_timeout
                )
                
                # 응답 상태 확인
                if response and response.status >= 400:
                    raise ScreenshotCaptureError(f"HTTP {response.status}: {url}")
                
                # 동적 콘텐츠 대기
                await asyncio.sleep(self.wait_after_load)
                
                # 스크롤하여 lazy-loaded 콘텐츠 로드
                await self._smart_scroll(page)
                
                # HTML 추출
                html_content = await page.content()
                
                # 스크린샷 캡처 (메모리)
                screenshot_bytes = await page.screenshot(
                    full_page=True,
                    type='png'
                )
                
                # Base64 인코딩
                base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
                
                # 파일 저장 (활성화된 경우에만 시도)
                if self.save_screenshots and (save_path or True):
                    try:
                        actual_path = save_path or self._generate_screenshot_path(url)
                        self._save_screenshot(screenshot_bytes, actual_path)
                    except Exception as e:
                        # 저장 실패해도 계속 진행 (메모리의 base64는 유지)
                        logger.warning(f"스크린샷 파일 저장 실패 (계속 진행): {e}")
                
                return base64_image, html_content
                
            finally:
                await browser.close()
    
    async def _smart_scroll(self, page: Page):
        """스마트 스크롤 (lazy-loaded 콘텐츠 로드)"""
        try:
            await page.evaluate("""
                async () => {
                    const scrollStep = 300;
                    const scrollDelay = 100;
                    const maxScrolls = 5;
                    
                    let scrollCount = 0;
                    
                    while (
                        scrollCount < maxScrolls &&
                        window.scrollY + window.innerHeight < document.body.scrollHeight
                    ) {
                        window.scrollBy(0, scrollStep);
                        await new Promise(resolve => setTimeout(resolve, scrollDelay));
                        scrollCount++;
                    }
                    
                    // 맨 위로 복귀
                    window.scrollTo(0, 0);
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            """)
        except Exception as e:
            logger.warning(f"스크롤 중 오류 (무시): {e}")
    
    def _generate_screenshot_path(self, url: str) -> str:
        """스크린샷 저장 경로 자동 생성"""
        from urllib.parse import urlparse
        import hashlib
        from datetime import datetime
        
        parsed = urlparse(url)
        domain = parsed.netloc.replace('.', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        filename = f"{domain}_{timestamp}_{url_hash}.png"
        
        screenshot_dir = Path(self.screenshot_dir)
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        return str(screenshot_dir / filename)
    
    def _save_screenshot(self, screenshot_bytes: bytes, path: str):
        """스크린샷 파일 저장 (실패해도 예외 던지지 않음)"""
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'wb') as f:
                f.write(screenshot_bytes)
            logger.info(f"스크린샷 저장: {path}")
        except Exception as e:
            # ADK Web 환경에서 권한 오류 발생 가능
            # 오류를 던지지 않고 로깅만 (메모리의 base64는 유효)
            logger.warning(f"스크린샷 저장 실패 (무시): {e}")

# 동기 래퍼
def capture_screenshot_sync(url: str, save_path: Optional[str] = None) -> Tuple[str, str]:
    """동기 방식 스크린샷 캡처"""
    capture = ScreenshotCapture()
    return asyncio.run(capture.capture(url, save_path))