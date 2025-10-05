# WebPilot/executor_agents/resource_selector_agent/crawler.py

from playwright.async_api import async_playwright, Page
from typing import List, Dict
from urllib.parse import urljoin, urlparse
import logging
import asyncio

logger = logging.getLogger(__name__)

class WebCrawler:
    """Playwright 기반 웹 크롤러"""
    
    def __init__(self, max_depth: int = 2, timeout: int = 10000):
        """
        Args:
            max_depth: 최대 탐색 깊이
            timeout: 페이지 로딩 타임아웃 (ms)
        """
        self.max_depth = max_depth
        self.timeout = timeout
    
    async def crawl_urls(self, root_uri: str) -> List[Dict]:
        """
        루트 URI에서 링크 수집
        
        Args:
            root_uri: 루트 도메인 URI
            
        Returns:
            URL 후보 목록
        """
        logger.info(f"크롤링 시작: {root_uri}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # 페이지 로딩
                await page.goto(root_uri, timeout=self.timeout, wait_until="domcontentloaded")
                
                # 동적 콘텐츠 대기 (1초)
                await asyncio.sleep(1)
                
                # 링크 수집
                url_candidates = await self._extract_links(page, root_uri)
                
                logger.info(f"크롤링 완료: {len(url_candidates)}개 URL 수집")
                
            except Exception as e:
                logger.error(f"크롤링 실패: {e}")
                url_candidates = []
            
            finally:
                await browser.close()
        
        return url_candidates
    
    async def _extract_links(self, page: Page, root_uri: str) -> List[Dict]:
        """
        페이지에서 링크 추출
        
        Args:
            page: Playwright Page 객체
            root_uri: 루트 URI
            
        Returns:
            URL 후보 목록
        """
        links = []
        root_domain = urlparse(root_uri).netloc
        
        # <a> 태그 수집
        elements = await page.query_selector_all("a[href]")
        
        for element in elements:
            try:
                href = await element.get_attribute("href")
                text = await element.inner_text()
                
                if not href or not text:
                    continue
                
                # 절대 URL로 변환
                absolute_url = urljoin(root_uri, href)
                
                # 동일 도메인만 허용
                if urlparse(absolute_url).netloc != root_domain:
                    continue
                
                # 앵커, 파일 다운로드 제외
                if "#" in absolute_url or absolute_url.endswith(('.pdf', '.zip', '.doc', '.xls')):
                    continue
                
                # 부모 메뉴 추출 (선택적)
                parent_menu = await self._get_parent_menu(element)
                
                links.append({
                    "url": absolute_url,
                    "title": text.strip(),
                    "link_text": text.strip(),
                    "parent_menu": parent_menu,
                    "depth": 1,
                    "context": await self._get_link_context(element)
                })
                
            except Exception as e:
                logger.debug(f"링크 추출 실패: {e}")
                continue
        
        # 중복 제거 (URL 기준)
        unique_links = {link["url"]: link for link in links}.values()
        
        return list(unique_links)
    
    async def _get_parent_menu(self, element) -> str:
        """링크의 부모 메뉴 텍스트 추출"""
        try:
            parent = await element.evaluate("""
                (el) => {
                    let current = el.parentElement;
                    while (current) {
                        if (current.tagName === 'NAV' || current.classList.contains('menu')) {
                            return current.innerText.split('\\n')[0];
                        }
                        current = current.parentElement;
                    }
                    return '';
                }
            """)
            return parent.strip() if parent else ""
        except:
            return ""
    
    async def _get_link_context(self, element) -> str:
        """링크 주변 텍스트 추출 (임베딩 품질 향상)"""
        try:
            context = await element.evaluate("""
                (el) => {
                    const parent = el.parentElement;
                    return parent ? parent.innerText.substring(0, 200) : '';
                }
            """)
            return context.strip() if context else ""
        except:
            return ""

# 동기 래퍼 함수
def crawl_urls_sync(root_uri: str, max_depth: int = 2) -> List[Dict]:
    """동기 방식 크롤링 (AgentTool 호환)"""
    crawler = WebCrawler(max_depth=max_depth)
    return asyncio.run(crawler.crawl_urls(root_uri))