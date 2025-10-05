# WebPilot/executor_agents/multimodal_perceiver_agent/html_parser.py

from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import logging
import re
from urllib.parse import urljoin
from WebPilot.constants import constants

logger = logging.getLogger(__name__)

class HTMLParserError(Exception):
    """HTML 파싱 오류"""
    pass

class HTMLParser:
    """HTML 구조 분석 및 요소 추출 (드롭다운 지원)"""
    
    def __init__(self):
        self.soup: Optional[BeautifulSoup] = None
        self.base_url: str = ""
        self.max_links = constants.PERCEIVER_MAX_LINKS
        self.max_text_length = constants.PERCEIVER_MAX_TEXT_LENGTH
        self.max_keyword_contexts = constants.PERCEIVER_MAX_KEYWORD_CONTEXTS
    
    def parse(self, html_content: str, base_url: str = "") -> Dict[str, Any]:
        """
        HTML 파싱 및 구조 분석
        
        Args:
            html_content: HTML 문자열
            base_url: 기준 URL (상대 경로 변환용)
            
        Returns:
            구조화된 페이지 정보
            
        Raises:
            HTMLParserError: 파싱 실패 시
        """
        try:
            self.base_url = base_url
            self.soup = BeautifulSoup(html_content, 'html.parser')
            
            # 메타 정보
            title = self._extract_title()
            meta_desc = self._extract_meta_description()
            
            # 주요 요소
            links = self._extract_links()
            buttons = self._extract_buttons()
            forms = self._extract_forms()
            headings = self._extract_headings()
            
            # ⭐ 네비게이션 구조 (드롭다운 포함)
            nav_structure = self._extract_navigation_structure()
            
            # 텍스트 콘텐츠
            main_text = self._extract_main_text()
            
            # 페이지 타입 추측
            page_type = self._guess_page_type(forms, headings, main_text)
            
            return {
                "title": title,
                "meta_description": meta_desc,
                "page_type": page_type,
                "links": links[:self.max_links],
                "buttons": buttons[:10],
                "forms": forms,
                "headings": headings[:15],
                "main_text": main_text[:self.max_text_length],
                "total_links": len(links),
                "total_buttons": len(buttons),
                "has_navigation": self._has_navigation(),
                "has_search": self._has_search_box(),
                "has_login": len(forms) > 0 and self._has_login_form(forms),
                "navigation_structure": nav_structure  # ⭐ 추가
            }
            
        except Exception as e:
            logger.error(f"HTML 파싱 실패: {e}")
            raise HTMLParserError(f"HTML 파싱 실패: {e}")
    
    def _extract_navigation_structure(self) -> List[Dict]:
        """
        네비게이션 메뉴 구조 추출 (드롭다운 포함)
        
        Returns:
            [
                {
                    "text": "정보광장",
                    "href": "/info",
                    "has_submenu": true,
                    "submenus": [
                        {"text": "공지사항", "href": "/notice"},
                        {"text": "FAQ", "href": "/faq"}
                    ]
                }
            ]
        """
        nav_structure = []
        
        # <nav> 태그 찾기
        nav = self.soup.find('nav') or self.soup.find(attrs={'role': 'navigation'})
        
        if not nav:
            # nav 없으면 header 내부 찾기
            header = self.soup.find('header')
            if header:
                # header 내부의 ul.menu, ul.nav 등
                nav = (header.find('ul', class_=re.compile(r'menu|nav', re.I)) or 
                       header.find('ul') or
                       header.find('div', class_=re.compile(r'menu|nav', re.I)))
        
        if not nav:
            logger.warning("네비게이션 구조를 찾을 수 없습니다")
            return []
        
        logger.info("네비게이션 구조 추출 중...")
        
        # 최상위 메뉴 항목 찾기
        # 일반적으로 nav > ul > li 구조
        top_level_items = []
        
        # 방법 1: nav 바로 아래 ul의 직계 li들
        direct_ul = nav.find('ul', recursive=False)
        if direct_ul:
            top_level_items = direct_ul.find_all('li', recursive=False)
        
        # 방법 2: nav 내부의 모든 li 중 부모가 nav에 가까운 것들
        if not top_level_items:
            all_lis = nav.find_all('li')
            # depth가 가장 얕은 li들만
            if all_lis:
                min_depth = min(len(list(li.parents)) for li in all_lis)
                top_level_items = [li for li in all_lis if len(list(li.parents)) == min_depth]
        
        logger.info(f"최상위 메뉴 항목: {len(top_level_items)}개")
        
        for item in top_level_items[:15]:  # 최대 15개
            try:
                menu_data = self._parse_menu_item(item)
                if menu_data:
                    nav_structure.append(menu_data)
            except Exception as e:
                logger.warning(f"메뉴 항목 파싱 실패: {e}")
                continue
        
        logger.info(f"네비게이션 구조 추출 완료: {len(nav_structure)}개 메뉴")
        
        return nav_structure
    
    def _parse_menu_item(self, item) -> Optional[Dict]:
        """메뉴 항목 파싱"""
        # 메뉴 텍스트와 링크
        main_link = item.find('a', recursive=False) or item.find('a')
        
        if not main_link:
            return None
        
        menu_text = main_link.get_text(strip=True)
        menu_href = main_link.get('href', '')
        
        if not menu_text:
            return None
        
        menu_data = {
            'text': menu_text,
            'href': self._make_absolute_url(menu_href),
            'has_submenu': False,
            'submenus': []
        }
        
        # 하위 메뉴 찾기
        # 방법 1: 직계 자식 ul
        submenu_container = item.find('ul', recursive=False)
        
        # 방법 2: 형제 ul (일부 구조에서는 li > a + ul)
        if not submenu_container:
            submenu_container = main_link.find_next_sibling('ul')
        
        # 방법 3: div.submenu, div.dropdown 등
        if not submenu_container:
            submenu_container = item.find('div', class_=re.compile(r'sub|dropdown|mega', re.I))
            if submenu_container:
                submenu_container = submenu_container.find('ul')
        
        if submenu_container:
            submenu_links = submenu_container.find_all('a')[:15]
            
            if submenu_links:
                menu_data['has_submenu'] = True
                
                for sub_link in submenu_links:
                    sub_text = sub_link.get_text(strip=True)
                    sub_href = sub_link.get('href', '')
                    
                    if sub_text:
                        menu_data['submenus'].append({
                            'text': sub_text,
                            'href': self._make_absolute_url(sub_href)
                        })
                
                logger.debug(f"드롭다운 메뉴 발견: {menu_text} ({len(menu_data['submenus'])}개 하위)")
        
        return menu_data
    
    def _make_absolute_url(self, url: str) -> str:
        """상대 URL을 절대 URL로 변환"""
        if not url or url.startswith(('#', 'javascript:')):
            return ''
        
        if self.base_url:
            return urljoin(self.base_url, url)
        
        return url
    
    def _extract_title(self) -> str:
        """페이지 제목 추출"""
        title = self.soup.find('title')
        if title:
            return title.get_text(strip=True)
        h1 = self.soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        return ""
    
    def _extract_meta_description(self) -> str:
        """메타 설명 추출"""
        meta = self.soup.find('meta', attrs={'name': 'description'})
        if meta:
            return meta.get('content', '')
        og_desc = self.soup.find('meta', attrs={'property': 'og:description'})
        if og_desc:
            return og_desc.get('content', '')
        return ""
    
    def _extract_links(self) -> List[Dict[str, str]]:
        """링크 추출 (절대 URL)"""
        links = []
        seen_urls = set()
        
        for a in self.soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a.get('href', '')
            
            if not text or href.startswith(('#', 'javascript:')):
                continue
            
            # 절대 URL 변환
            href = self._make_absolute_url(href)
            
            if href in seen_urls:
                continue
            
            seen_urls.add(href)
            links.append({
                "text": text[:100],
                "href": href,
                "title": a.get('title', '')[:50]
            })
        
        return links
    
    def _extract_buttons(self) -> List[Dict[str, str]]:
        """버튼 추출"""
        buttons = []
        
        for btn in self.soup.find_all('button'):
            text = btn.get_text(strip=True)
            if text:
                buttons.append({
                    "text": text[:50],
                    "type": btn.get('type', 'button'),
                    "class": ' '.join(btn.get('class', []))[:50]
                })
        
        for inp in self.soup.find_all('input', attrs={'type': ['submit', 'button']}):
            value = inp.get('value', '')
            if value:
                buttons.append({
                    "text": value[:50],
                    "type": inp.get('type', 'button'),
                    "class": ' '.join(inp.get('class', []))[:50]
                })
        
        for elem in self.soup.find_all(attrs={'role': 'button'}):
            text = elem.get_text(strip=True)
            if text and text not in [b['text'] for b in buttons]:
                buttons.append({
                    "text": text[:50],
                    "type": "role-button",
                    "class": ' '.join(elem.get('class', []))[:50]
                })
        
        return buttons
    
    def _extract_forms(self) -> List[Dict[str, Any]]:
        """폼 추출"""
        forms = []
        
        for form in self.soup.find_all('form'):
            inputs = []
            
            for inp in form.find_all(['input', 'textarea', 'select']):
                input_type = inp.get('type', inp.name)
                input_name = inp.get('name', '')
                input_placeholder = inp.get('placeholder', '')
                input_id = inp.get('id', '')
                
                if input_name or input_id:
                    inputs.append({
                        "type": input_type,
                        "name": input_name,
                        "placeholder": input_placeholder,
                        "id": input_id
                    })
            
            if inputs:
                forms.append({
                    "action": form.get('action', ''),
                    "method": form.get('method', 'get').lower(),
                    "inputs": inputs[:10]
                })
        
        return forms
    
    def _extract_headings(self) -> List[Dict[str, str]]:
        """헤딩 추출"""
        headings = []
        
        for level in range(1, 7):
            for h in self.soup.find_all(f'h{level}'):
                text = h.get_text(strip=True)
                if text:
                    headings.append({
                        "level": level,
                        "text": text[:100]
                    })
        
        return headings
    
    def _extract_main_text(self) -> str:
        """본문 텍스트 추출"""
        for tag in self.soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        main_content = self.soup.find('main') or self.soup.find('article') or self.soup.body
        
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
        else:
            text = self.soup.get_text(separator=' ', strip=True)
        
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def _guess_page_type(self, forms: List, headings: List, text: str) -> str:
        """페이지 타입 추측"""
        text_lower = text.lower()
        
        if forms and any(any(inp['type'] == 'password' for inp in form['inputs']) for form in forms):
            return "login_page"
        
        if forms and len(forms[0].get('inputs', [])) > 2:
            return "form_page"
        
        if any(h['text'] for h in headings if '목록' in h['text'] or 'list' in h['text'].lower()):
            return "list_page"
        
        if '공지사항' in text or '게시판' in text:
            return "list_page"
        
        if any(h['text'] for h in headings if '상세' in h['text'] or 'detail' in h['text'].lower()):
            return "detail_page"
        
        if 'home' in text_lower or 'main' in text_lower or '메인' in text:
            return "main_page"
        
        return "unknown"
    
    def _has_navigation(self) -> bool:
        """네비게이션 메뉴 존재 여부"""
        if self.soup.find('nav'):
            return True
        if self.soup.find(attrs={'role': 'navigation'}):
            return True
        return self.soup.find(class_=re.compile(r'menu|nav', re.I)) is not None
    
    def _has_search_box(self) -> bool:
        """검색창 존재 여부"""
        if self.soup.find('input', attrs={'type': 'search'}):
            return True
        search_by_name = self.soup.find('input', attrs={'name': re.compile(r'search', re.I)})
        search_by_id = self.soup.find('input', attrs={'id': re.compile(r'search', re.I)})
        return search_by_name is not None or search_by_id is not None
    
    def _has_login_form(self, forms: List) -> bool:
        """로그인 폼 존재 여부"""
        for form in forms:
            inputs = form.get('inputs', [])
            if any(inp['type'] == 'password' for inp in inputs):
                return True
            
            has_username = any(
                any(keyword in inp.get('name', '').lower() for keyword in ['user', 'id', 'email'])
                for inp in inputs
            )
            has_password = any('pass' in inp.get('name', '').lower() for inp in inputs)
            
            if has_username and has_password:
                return True
        
        return False
    
    def search_keywords(self, keywords: List[str]) -> Dict[str, List[str]]:
        """키워드 검색"""
        results = {}
        text = self.soup.get_text()
        
        for keyword in keywords:
            matches = []
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            
            for match in pattern.finditer(text):
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].strip()
                context = re.sub(r'\s+', ' ', context)
                matches.append(context)
                
                if len(matches) >= self.max_keyword_contexts:
                    break
            
            if matches:
                results[keyword] = matches
        
        return results