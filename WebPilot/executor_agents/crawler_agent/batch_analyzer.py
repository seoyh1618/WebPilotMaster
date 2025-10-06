# WebPilot/executor_agents/crawler_agent/batch_analyzer.py

from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
import logging
import json

logger = logging.getLogger(__name__)

class BatchAnalyzer:
    """병렬 분석"""
    
    def __init__(self, perceiver_agent, max_workers: int = 5):
        self.perceiver = perceiver_agent
        self.max_workers = max_workers
    
    def analyze_multiple(
        self,
        items: List[Dict],
        query: str,
        top_k: int = 5
    ) -> List[Dict]:
        """여러 항목 병렬 분석"""
        
        items_to_analyze = items[:top_k]
        
        logger.info(f"배치 분석 시작: {len(items_to_analyze)}개")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self._analyze_single, item, query)
                for item in items_to_analyze
            ]
            
            results = [f.result() for f in futures]
        
        successful = [r for r in results if r['success']]
        
        logger.info(f"✓ 배치 완료: {len(successful)}/{len(items_to_analyze)} 성공")
        
        return results
    
    def _analyze_single(self, item: Dict, query: str) -> Dict:
        """단일 항목 분석"""
        
        url = item['url']
        title = item['title']
        
        try:
            perceiver_input = json.dumps({
                "url": url,
                "query": query,
                "screenshot_required": False,
                "depth": 1
            }, ensure_ascii=False)
            
            result_json = self.perceiver.run(perceiver_input)
            result = json.loads(result_json)
            
            analysis = result.get('analysis', {})
            
            return {
                "url": url,
                "title": title,
                "success": True,
                "information_found": analysis.get('information_found', False),
                "extracted_info": analysis.get('extracted_info', ''),
                "confidence": analysis.get('confidence', 0.0)
            }
            
        except Exception as e:
            logger.error(f"분석 실패 ({title}): {e}")
            return {
                "url": url,
                "title": title,
                "success": False,
                "information_found": False,
                "error_message": str(e)
            }