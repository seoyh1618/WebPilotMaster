# WebPilot/executor_agents/filter_based_page_handler_agent/result_parser.py

from bs4 import BeautifulSoup
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ResultParser:
    """결과 테이블 파싱"""
    
    def parse(self, html: str, page_type: str) -> List[Dict]:
        """결과 파싱"""
        
        soup = BeautifulSoup(html, 'html.parser')
        
        if page_type == "sap":
            return self._parse_sap_results(soup)
        else:
            return self._parse_standard_results(soup)
    
    def _parse_sap_results(self, soup: BeautifulSoup) -> List[Dict]:
        """SAP 결과 파싱"""
        
        results = []
        
        # SAP 테이블 클래스
        table = soup.find('table', class_=lambda x: x and any(
            kw in x for kw in ['urMT', 'urST4', 'sapUiTable']
        ))
        
        if not table:
            table = soup.find('table')
        
        if not table:
            logger.warning("결과 테이블 없음")
            return []
        
        # 헤더 추출
        headers = []
        header_row = table.find('tr')
        if header_row:
            header_cells = header_row.find_all(['th', 'td'])
            headers = [cell.get_text(strip=True) for cell in header_cells]
        
        # 데이터 행
        rows = table.find_all('tr')[1:]  # 헤더 제외
        
        for row in rows[:50]:  # 최대 50개
            cells = row.find_all(['td', 'th'])
            
            if not cells:
                continue
            
            # 열 데이터
            columns = [cell.get_text(strip=True) for cell in cells]
            
            # 딕셔너리 형태
            raw_data = {}
            for i, col in enumerate(columns):
                if i < len(headers):
                    raw_data[headers[i]] = col
                else:
                    raw_data[f"column_{i}"] = col
            
            results.append({
                "columns": columns,
                "raw_data": raw_data
            })
        
        logger.info(f"✓ {len(results)}개 결과 파싱")
        
        return results
    
    def _parse_standard_results(self, soup: BeautifulSoup) -> List[Dict]:
        """표준 결과 파싱"""
        
        results = []
        
        # 결과 테이블 찾기
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            if len(rows) < 2:
                continue
            
            # 헤더
            headers = []
            first_row = rows[0]
            header_cells = first_row.find_all(['th', 'td'])
            headers = [cell.get_text(strip=True) for cell in header_cells]
            
            # 데이터
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                columns = [cell.get_text(strip=True) for cell in cells]
                
                if not columns:
                    continue
                
                raw_data = {}
                for i, col in enumerate(columns):
                    if i < len(headers):
                        raw_data[headers[i]] = col
                    else:
                        raw_data[f"column_{i}"] = col
                
                results.append({
                    "columns": columns,
                    "raw_data": raw_data
                })
        
        logger.info(f"✓ {len(results)}개 결과 파싱")
        
        return results[:50]  # 최대 50개