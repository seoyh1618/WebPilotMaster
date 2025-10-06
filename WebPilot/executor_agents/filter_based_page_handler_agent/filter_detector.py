# WebPilot/executor_agents/filter_based_page_handler_agent/filter_detector.py

from bs4 import BeautifulSoup
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class FilterDetector:
    """필터 페이지 감지"""
    
    def detect(self, html: str, url: str) -> Dict:
        """필터 페이지 여부 및 타입 판단"""
        
        soup = BeautifulSoup(html, 'html.parser')
        
        result = {
            "is_filter_page": False,
            "page_type": "unknown",
            "page_title": ""
        }
        
        # 1. SAP 페이지 감지
        if self._is_sap_page(html, url):
            result["is_filter_page"] = True
            result["page_type"] = "sap"
            logger.info("✓ SAP WebDynpro 페이지 감지")
        
        # 2. iframe 감지
        elif self._has_iframe(soup):
            result["is_filter_page"] = True
            result["page_type"] = "iframe"
            logger.info("✓ iframe 기반 페이지 감지")
        
        # 3. 표준 필터 페이지 감지
        elif self._is_standard_filter_page(soup):
            result["is_filter_page"] = True
            result["page_type"] = "standard"
            logger.info("✓ 표준 필터 페이지 감지")
        
        # 타이틀 추출
        title_tag = soup.find('title')
        if title_tag:
            result["page_title"] = title_tag.get_text(strip=True)
        
        return result
    
    def _is_sap_page(self, html: str, url: str) -> bool:
        """SAP 페이지 여부"""
        
        # URL 패턴
        sap_url_patterns = [
            "sap/bc/webdynpro",
            "sap-language",
            "WDID_",
            "/sap/"
        ]
        
        if any(pattern in url for pattern in sap_url_patterns):
            return True
        
        # HTML 패턴
        sap_html_patterns = [
            "sapUiView",
            "sapUiBody",
            "urMT",
            "urLbl",
            "WDID_"
        ]
        
        if sum(1 for pattern in sap_html_patterns if pattern in html) >= 2:
            return True
        
        return False
    
    def _has_iframe(self, soup: BeautifulSoup) -> bool:
        """iframe 존재 여부"""
        iframes = soup.find_all('iframe')
        return len(iframes) > 0
    
    def _is_standard_filter_page(self, soup: BeautifulSoup) -> bool:
        """표준 필터 페이지 여부"""
        
        # 필터 요소 개수
        selects = len(soup.find_all('select'))
        text_inputs = len(soup.find_all('input', type='text'))
        
        # 검색/조회 버튼
        search_buttons = soup.find_all('button', string=lambda x: x and any(
            kw in x for kw in ['검색', '조회', 'Search', '확인']
        ))
        
        # 필터 2개 이상 + 검색 버튼
        if (selects + text_inputs >= 2) and len(search_buttons) > 0:
            return True
        
        return False