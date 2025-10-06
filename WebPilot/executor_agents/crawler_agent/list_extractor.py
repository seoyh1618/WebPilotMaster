# WebPilot/executor_agents/crawler_agent/list_extractor.py

from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional
import logging
from urllib.parse import urljoin
import re

logger = logging.getLogger(__name__)

class ListExtractor:
    """HTML에서 리스트 항목 추출"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def is_list_page(self, soup: BeautifulSoup) -> bool:
        """리스트 페이지 여부 판단"""
        
        # 전략 1: table 기반 게시판
        tables = soup.find_all('table', class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['board', 'list', 'notice', 'bbs', 'table']
        ))
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) >= 3:  # 최소 3개 행
                logger.info(f"✓ 리스트 페이지 감지: table ({len(rows)}개 행)")
                return True
        
        # 전략 2: ul/ol 기반
        lists = soup.find_all(['ul', 'ol'], class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['board', 'list', 'notice', 'post', 'item']
        ))
        
        for lst in lists:
            items = lst.find_all('li', recursive=False)
            if len(items) >= 3:
                logger.info(f"✓ 리스트 페이지 감지: list ({len(items)}개 항목)")
                return True
        
        # 전략 3: 반복되는 article/div 패턴
        articles = soup.find_all('article')
        if len(articles) >= 3:
            logger.info(f"✓ 리스트 페이지 감지: articles ({len(articles)}개)")
            return True
        
        # 전략 4: 같은 클래스의 div가 반복
        all_divs = soup.find_all('div', class_=True)
        class_counts = {}
        for div in all_divs:
            classes = ' '.join(div.get('class', []))
            if classes:
                class_counts[classes] = class_counts.get(classes, 0) + 1
        
        for classes, count in class_counts.items():
            if count >= 5 and any(keyword in classes.lower() for keyword in ['item', 'card', 'post']):
                logger.info(f"✓ 리스트 페이지 감지: 반복 div ({count}개)")
                return True
        
        return False
    
    def extract_items(self, soup: BeautifulSoup, max_items: int = 50) -> List[Dict]:
        """모든 리스트 항목 추출"""
        
        items = []
        
        # 전략 1: table
        items.extend(self._extract_from_tables(soup))
        
        # 전략 2: ul/ol
        items.extend(self._extract_from_lists(soup))
        
        # 전략 3: article
        items.extend(self._extract_from_articles(soup))
        
        # 전략 4: div 카드
        items.extend(self._extract_from_cards(soup))
        
        # 중복 제거
        unique_items = self._deduplicate(items)
        
        logger.info(f"총 {len(unique_items)}개 항목 추출")
        
        return unique_items[:max_items]
    
    def _extract_from_tables(self, soup: BeautifulSoup) -> List[Dict]:
        """table에서 추출"""
        items = []
        
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')[1:]  # 헤더 제외
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                
                # 링크 찾기
                link = row.find('a')
                if not link:
                    continue
                
                title = link.get_text(strip=True)
                href = link.get('href', '')
                
                if not title or len(title) < 3:
                    continue
                
                # 날짜 찾기
                date = None
                for cell in cells:
                    text = cell.get_text(strip=True)
                    if self._is_date(text):
                        date = text
                        break
                
                # 작성자 찾기
                author = None
                author_cell = row.find('td', class_=lambda x: x and 'author' in x.lower())
                if author_cell:
                    author = author_cell.get_text(strip=True)
                
                items.append({
                    'title': title,
                    'url': urljoin(self.base_url, href),
                    'date': date,
                    'author': author,
                    'source_type': 'table'
                })
        
        logger.info(f"  - table: {len(items)}개")
        return items
    
    def _extract_from_lists(self, soup: BeautifulSoup) -> List[Dict]:
        """ul/ol에서 추출"""
        items = []
        
        lists = soup.find_all(['ul', 'ol'])
        
        for lst in lists:
            list_items = lst.find_all('li', recursive=False)
            
            for li in list_items:
                link = li.find('a')
                if not link:
                    continue
                
                title = link.get_text(strip=True)
                href = link.get('href', '')
                
                if not title or len(title) < 3:
                    continue
                
                # 날짜
                date = None
                date_elem = li.find(class_=lambda x: x and any(
                    kw in x.lower() for kw in ['date', 'time', 'day']
                ))
                if date_elem:
                    date = date_elem.get_text(strip=True)
                
                # 미리보기
                preview = None
                preview_elem = li.find(class_=lambda x: x and any(
                    kw in x.lower() for kw in ['preview', 'desc', 'summary', 'content']
                ))
                if preview_elem:
                    preview = preview_elem.get_text(strip=True)[:200]
                
                items.append({
                    'title': title,
                    'url': urljoin(self.base_url, href),
                    'date': date,
                    'preview': preview,
                    'source_type': 'list'
                })
        
        logger.info(f"  - list: {len(items)}개")
        return items
    
    def _extract_from_articles(self, soup: BeautifulSoup) -> List[Dict]:
        """article에서 추출"""
        items = []
        
        articles = soup.find_all('article')
        
        for article in articles:
            link = article.find('a')
            if not link:
                continue
            
            # 제목 (h1-h6 우선)
            title_elem = article.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if not title_elem:
                title_elem = link
            
            title = title_elem.get_text(strip=True)
            href = link.get('href', '')
            
            if not title or len(title) < 3:
                continue
            
            # 날짜
            date = None
            time_elem = article.find('time')
            if time_elem:
                date = time_elem.get('datetime') or time_elem.get_text(strip=True)
            
            # 미리보기
            preview = None
            p_elem = article.find('p')
            if p_elem:
                preview = p_elem.get_text(strip=True)[:200]
            
            items.append({
                'title': title,
                'url': urljoin(self.base_url, href),
                'date': date,
                'preview': preview,
                'source_type': 'article'
            })
        
        logger.info(f"  - article: {len(items)}개")
        return items
    
    def _extract_from_cards(self, soup: BeautifulSoup) -> List[Dict]:
        """div 카드에서 추출"""
        items = []
        
        # 카드형 컨테이너
        cards = soup.find_all('div', class_=lambda x: x and any(
            kw in x.lower() for kw in ['card', 'item', 'post', 'entry']
        ))
        
        for card in cards:
            link = card.find('a')
            if not link:
                continue
            
            title = link.get_text(strip=True)
            href = link.get('href', '')
            
            if not title or len(title) < 3:
                continue
            
            items.append({
                'title': title,
                'url': urljoin(self.base_url, href),
                'source_type': 'card'
            })
        
        logger.info(f"  - card: {len(items)}개")
        return items
    
    def _deduplicate(self, items: List[Dict]) -> List[Dict]:
        """URL 기준 중복 제거"""
        seen = set()
        unique = []
        
        for item in items:
            url = item.get('url')
            if url and url not in seen:
                seen.add(url)
                unique.append(item)
        
        return unique
    
    def _is_date(self, text: str) -> bool:
        """날짜 형식인지 확인"""
        date_patterns = [
            r'\d{4}[-./]\d{1,2}[-./]\d{1,2}',
            r'\d{4}\.\d{1,2}\.\d{1,2}',
            r'\d{2}[-./]\d{1,2}[-./]\d{1,2}',
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, text):
                return True
        
        return False
    
    def extract_pagination(self, soup: BeautifulSoup) -> Dict:
        """페이지네이션 정보"""
        
        info = {
            'has_pagination': False,
            'current_page': 1,
            'total_pages': None,
            'next_page_url': None,
            'next_page_selector': None
        }
        
        # 페이지네이션 컨테이너
        pagination = soup.find(class_=lambda x: x and 'paginat' in x.lower())
        
        if not pagination:
            pagination = soup.find('div', class_=lambda x: x and any(
                kw in x.lower() for kw in ['paging', 'page', 'nav']
            ))
        
        if not pagination:
            return info
        
        info['has_pagination'] = True
        
        # 현재 페이지
        current = pagination.find(class_=lambda x: x and any(
            kw in x.lower() for kw in ['active', 'current', 'on', 'selected']
        ))
        
        if current:
            try:
                page_num = current.get_text(strip=True)
                info['current_page'] = int(re.search(r'\d+', page_num).group())
            except:
                pass
        
        # 다음 페이지
        next_btn = pagination.find('a', class_=lambda x: x and 'next' in x.lower())
        if not next_btn:
            next_btn = pagination.find('a', string=lambda x: x and any(
                kw in x for kw in ['다음', '>', 'Next', 'next']
            ))
        
        if next_btn:
            href = next_btn.get('href')
            if href:
                info['next_page_url'] = urljoin(self.base_url, href)
            
            # selector
            if next_btn.get('id'):
                info['next_page_selector'] = f"#{next_btn['id']}"
            elif next_btn.get('class'):
                info['next_page_selector'] = f".{'.'.join(next_btn['class'])}"
        
        # 전체 페이지
        page_links = pagination.find_all('a')
        page_numbers = []
        for link in page_links:
            text = link.get_text(strip=True)
            if text.isdigit():
                page_numbers.append(int(text))
        
        if page_numbers:
            info['total_pages'] = max(page_numbers)
        
        logger.info(f"페이지네이션: {info['current_page']}/{info['total_pages']}")
        
        return info