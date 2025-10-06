# WebPilot/executor_agents/filter_based_page_handler_agent/filter_extractor.py

from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class FilterExtractor:
    """필터 요소 추출"""
    
    def extract(self, html: str, page_type: str) -> Dict:
        """필터 요소 추출"""
        
        soup = BeautifulSoup(html, 'html.parser')
        
        filters = []
        search_button = None
        
        # 페이지 타입별 전략
        if page_type == "sap":
            filters, search_button = self._extract_sap_filters(soup)
        else:
            filters, search_button = self._extract_standard_filters(soup)
        
        logger.info(f"추출 완료: {len(filters)}개 필터, 검색 버튼: {bool(search_button)}")
        
        return {
            "filters": filters,
            "search_button": search_button
        }
    
    def _extract_sap_filters(self, soup: BeautifulSoup) -> tuple:
        """SAP 필터 추출"""
        
        filters = []
        
        # 1. 드롭다운
        selects = soup.find_all('select')
        for select in selects:
            label = self._find_label_sap(select)
            
            options = [
                opt.get_text(strip=True)
                for opt in select.find_all('option')
                if opt.get_text(strip=True)
            ]
            
            if label and options:
                filters.append({
                    "label": label,
                    "type": "dropdown",
                    "selector": self._get_selector(select),
                    "xpath": self._get_xpath(select),
                    "options": options[:20]
                })
        
        # 2. 텍스트 입력
        text_inputs = soup.find_all('input', type='text')
        for inp in text_inputs[:5]:
            label = self._find_label_sap(inp)
            if label:
                filters.append({
                    "label": label,
                    "type": "text_input",
                    "selector": self._get_selector(inp),
                    "xpath": self._get_xpath(inp)
                })
        
        # 3. 탭 (있으면)
        tabs = self._extract_tabs(soup)
        filters.extend(tabs)
        
        # 4. 검색 버튼
        search_button = self._find_search_button(soup)
        
        logger.info(f"  SAP 필터: 드롭다운 {len([f for f in filters if f['type']=='dropdown'])}개, "
                   f"입력 {len([f for f in filters if f['type']=='text_input'])}개, "
                   f"탭 {len([f for f in filters if f['type']=='tab'])}개")
        
        return filters, search_button
    
    def _extract_standard_filters(self, soup: BeautifulSoup) -> tuple:
        """표준 필터 추출"""
        
        filters = []
        
        # 드롭다운
        selects = soup.find_all('select')
        for select in selects[:10]:
            label = self._find_label(select)
            options = [opt.get_text(strip=True) for opt in select.find_all('option')]
            
            if options:
                filters.append({
                    "label": label,
                    "type": "dropdown",
                    "selector": self._get_selector(select),
                    "options": options
                })
        
        # 텍스트 입력
        text_inputs = soup.find_all('input', type='text')
        for inp in text_inputs[:5]:
            label = self._find_label(inp)
            filters.append({
                "label": label,
                "type": "text_input",
                "selector": self._get_selector(inp)
            })
        
        # 검색 버튼
        search_button = self._find_search_button(soup)
        
        return filters, search_button
    
    def _find_label_sap(self, element: Tag) -> str:
        """SAP 라벨 찾기"""
        
        # 1. 부모 tr > td.urLbl
        parent_tr = element.find_parent('tr')
        if parent_tr:
            label_td = parent_tr.find('td', class_='urLbl')
            if label_td:
                return label_td.get_text(strip=True).rstrip(':')
        
        # 2. 이전 형제 label
        label = element.find_previous('label')
        if label:
            return label.get_text(strip=True).rstrip(':')
        
        # 3. placeholder
        placeholder = element.get('placeholder')
        if placeholder:
            return placeholder
        
        # 4. 이전 텍스트 노드
        prev = element.find_previous_sibling(string=True)
        if prev:
            text = prev.strip().rstrip(':')
            if text and len(text) < 30:
                return text
        
        return "Unknown"
    
    def _find_label(self, element: Tag) -> str:
        """일반 라벨 찾기"""
        
        # 1. <label for="...">
        elem_id = element.get('id')
        if elem_id:
            label = element.find_previous('label', attrs={'for': elem_id})
            if label:
                return label.get_text(strip=True).rstrip(':')
        
        # 2. 부모 label
        parent_label = element.find_parent('label')
        if parent_label:
            return parent_label.get_text(strip=True).rstrip(':')
        
        # 3. 이전 형제
        prev = element.find_previous_sibling(['label', 'span', 'div'])
        if prev:
            text = prev.get_text(strip=True).rstrip(':')
            if text and len(text) < 30:
                return text
        
        # 4. name 속성
        name = element.get('name', '')
        if name:
            return name
        
        return "Unknown"
    
    def _extract_tabs(self, soup: BeautifulSoup) -> List[Dict]:
        """탭 추출"""
        tabs = []
        
        # 탭 컨테이너 찾기
        tab_containers = soup.find_all(class_=lambda x: x and 'tab' in x.lower())
        
        for container in tab_containers[:1]:
            tab_links = container.find_all('a')
            for link in tab_links[:10]:
                text = link.get_text(strip=True)
                if text and len(text) < 50:
                    tabs.append({
                        "label": text,
                        "type": "tab",
                        "selector": self._get_selector(link),
                        "xpath": self._get_xpath(link)
                    })
        
        return tabs
    
    def _find_search_button(self, soup: BeautifulSoup) -> Optional[Dict]:
        """검색 버튼 찾기"""
        
        search_keywords = ['검색', '조회', 'Search', '확인', 'search', 'submit']
        
        # button 태그
        for keyword in search_keywords:
            btn = soup.find('button', string=lambda x: x and keyword in x)
            if btn:
                return {
                    "label": btn.get_text(strip=True),
                    "type": "button",
                    "selector": self._get_selector(btn),
                    "xpath": self._get_xpath(btn)
                }
        
        # input[type=submit]
        for keyword in search_keywords:
            btn = soup.find('input', type='submit', value=lambda x: x and keyword in x)
            if btn:
                return {
                    "label": btn.get('value', 'Submit'),
                    "type": "button",
                    "selector": self._get_selector(btn),
                    "xpath": self._get_xpath(btn)
                }
        
        # input[type=button]
        for keyword in search_keywords:
            btn = soup.find('input', type='button', value=lambda x: x and keyword in x)
            if btn:
                return {
                    "label": btn.get('value', 'Button'),
                    "type": "button",
                    "selector": self._get_selector(btn),
                    "xpath": self._get_xpath(btn)
                }
        
        return None
    
    def _get_selector(self, element: Tag) -> str:
        """CSS selector 생성"""
        if element.get('id'):
            return f"#{element['id']}"
        elif element.get('name'):
            return f"[name='{element['name']}']"
        elif element.get('class'):
            classes = element['class']
            return f".{'.'.join(classes)}"
        else:
            return self._get_xpath(element)
    
    def _get_xpath(self, element: Tag) -> str:
        """XPath 생성"""
        components = []
        child = element
        
        for parent in list(child.parents)[:5]:
            siblings = parent.find_all(child.name, recursive=False)
            if len(siblings) > 1:
                index = siblings.index(child) + 1
                components.append(f"{child.name}[{index}]")
            else:
                components.append(child.name)
            child = parent
        
        return '//' + '/'.join(reversed(components))