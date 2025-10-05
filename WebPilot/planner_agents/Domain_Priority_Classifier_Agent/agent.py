from __future__ import annotations
from google.adk.tools import ToolContext

from typing import Any, Dict, List
from pathlib import Path
from dotenv import load_dotenv
import logging

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

from WebPilot.constants.constants import MODEL_O3_MINI
from WebPilot.planner_agents.Domain_Priority_Classifier_Agent.prompt import INSTRUCTION, DESCRIPTION
from WebPilot.planner_agents.Domain_Priority_Classifier_Agent.functions import classify_domain_priorities
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class DomainInfo(BaseModel):
    domain: str
    uri: str
    score: float
    priority: Literal["critical","high","medium","low"]
    confidence: Literal["high","medium","low"]
    reasoning: str
    condition: Optional[str] = ""

class SelectionInfo(BaseModel):
    """선택 정보 (metadata 내부)"""
    primary_count: int = 1
    alternatives_count: int = 0
    total_candidates: int = 0
    filtered_out: int = 0
    selected_count: int = 0
    selection_rule: str = "1순위 무조건 + 2순위 이상 최소 1개"

class DomainMetadata(BaseModel):
    """메타데이터"""
    total_time: float = 0.0
    selection_info: SelectionInfo

class DomainPriorityResult(BaseModel):
    primary: DomainInfo
    alternatives: List[DomainInfo]
    reason: str
    metadata: DomainMetadata  # ⭐ 구조화된 타입

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

YAML_PATH = Path(__file__).resolve().parents[2] / "config" / "domains.yaml"

load_dotenv()

if not YAML_PATH.exists():
    logger.error(f"domains.yaml 파일을 찾을 수 없습니다: {YAML_PATH}")
    raise FileNotFoundError(f"domains.yaml이 없습니다: {YAML_PATH}")

_llm_client_cache = None

def get_llm_client() -> LiteLlm:
    """LLM 클라이언트 팩토리"""
    global _llm_client_cache
    if _llm_client_cache is None:
        _llm_client_cache = LiteLlm(model=MODEL_O3_MINI)
        logger.info(f"LLM 클라이언트 초기화: {MODEL_O3_MINI}")
    return _llm_client_cache

def _classify_handler(query: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    도메인 우선순위 분류 핸들러
    """
    if not query or not query.strip():
        return {
            "primary": None,
            "alternatives": [],
            "reason": "빈 쿼리",
            "metadata": {
                "total_time": 0.0,
                "selection_info": {
                    "primary_count": 0,
                    "alternatives_count": 0,
                    "total_candidates": 0,
                    "filtered_out": 0,
                    "selected_count": 0,
                    "selection_rule": ""
                }
            }
        }
    
    try:
        logger.info(f"분류 시작: {query[:50]}...")
        llm_client = get_llm_client()
        result = classify_domain_priorities(query=query, llm_client=llm_client)
        
        # ⭐ metadata 검증 및 보정
        if 'metadata' not in result or not result['metadata']:
            logger.warning("metadata 누락, 자동 생성")
            result['metadata'] = {
                "total_time": 0.0,
                "selection_info": {
                    "primary_count": 1 if result.get('primary') else 0,
                    "alternatives_count": len(result.get('alternatives', [])),
                    "total_candidates": 1 + len(result.get('alternatives', [])),
                    "filtered_out": 0,
                    "selected_count": 1 + len(result.get('alternatives', [])),
                    "selection_rule": "1순위 무조건 + 2순위 이상 최소 1개"
                }
            }
        
        # selection_info 검증
        if 'selection_info' not in result['metadata']:
            logger.warning("selection_info 누락, 자동 생성")
            result['metadata']['selection_info'] = {
                "primary_count": 1 if result.get('primary') else 0,
                "alternatives_count": len(result.get('alternatives', [])),
                "total_candidates": 1 + len(result.get('alternatives', [])),
                "filtered_out": 0,
                "selected_count": 1 + len(result.get('alternatives', [])),
                "selection_rule": "1순위 무조건 + 2순위 이상 최소 1개"
            }
        
        primary_domain = result.get("primary", {}).get("domain", "None") if result.get("primary") else "None"
        alt_count = len(result.get("alternatives", []))
        
        tool_context.state["Domain_Priority_Classifier_Agent_Output"] = result
        tool_context.state["classification_time"] = result["metadata"].get("total_time", 0.0)
        
        logger.info(f"분류 완료: {primary_domain} (+{alt_count}개 대안)")
        return result
        
    except Exception as e:
        logger.error(f"분류 오류: {str(e)}", exc_info=True)
        return {
            "primary": None,
            "alternatives": [],
            "reason": f"오류: {str(e)}",
            "metadata": {
                "total_time": 0.0,
                "selection_info": {
                    "primary_count": 0,
                    "alternatives_count": 0,
                    "total_candidates": 0,
                    "filtered_out": 0,
                    "selected_count": 0,
                    "selection_rule": ""
                }
            }
        }

_agent_cache = None

def get_domain_priority_classifier_agent() -> Agent:
    """Agent 인스턴스 팩토리"""
    global _agent_cache
    if _agent_cache is None:
        _agent_cache = Agent(
            name="Domain_Priority_Classifier_Agent",
            model=get_llm_client(),
            description=DESCRIPTION,
            instruction=INSTRUCTION,
            tools=[FunctionTool(_classify_handler)],
            output_schema=DomainPriorityResult,         
            output_key="Domain_Priority_Classifier_Agent_Output"   
        )
        logger.info("Domain_Priority_Classifier_Agent 초기화 완료")
    return _agent_cache

Domain_Priority_Classifier_Agent = get_domain_priority_classifier_agent()

def test_classification(query: str) -> None:
    """테스트 헬퍼"""
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print(f"{'='*70}\n")
    
    result = _classify_handler(query)
    
    # Primary
    if result.get('primary'):
        primary = result['primary']
        print(f"✓ Primary:")
        print(f"  Domain: {primary['domain']}")
        print(f"  URL: {primary['uri']}")
        print(f"  Score: {primary['score']} | Priority: {primary['priority']} | Confidence: {primary['confidence']}")
        print(f"  Reasoning: {primary['reasoning']}")
        if primary.get('condition'):
            print(f"  Condition: {primary['condition']}")
        if primary.get('fallback_reason'):
            print(f"  ⚠️ Fallback: {primary['fallback_reason']}")
        print()
    
    # Alternatives
    if result.get('alternatives'):
        print(f"→ Alternatives ({len(result['alternatives'])}개):")
        for i, alt in enumerate(result['alternatives'], 1):
            print(f"  [{i}] {alt['domain']}: {alt['uri']}")
            print(f"      Score: {alt['score']} | Priority: {alt['priority']} | Confidence: {alt['confidence']}")
            print(f"      Reasoning: {alt['reasoning']}")
            if alt.get('condition'):
                print(f"      Condition: {alt['condition']}")
        print()
    
    # Metadata
    metadata = result.get("metadata", {})
    if metadata:
        selection_info = metadata.get("selection_info", {})
        print(f"Metadata:")
        print(f"  Time: {metadata.get('total_time', 0)}s")
        print(f"  Selected: {selection_info.get('selected_count', 0)}/{selection_info.get('total_candidates', 0)}")
        print(f"  Filtered: {selection_info.get('filtered_out', 0)}개")
    
    print(f"\n{'='*70}\n")

def batch_test(queries: List[str]) -> None:
    """배치 테스트"""
    print(f"\n{'='*70}")
    print(f"배치 테스트: {len(queries)}개")
    print(f"{'='*70}\n")
    
    results = []
    for i, query in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] {query}")
        result = _classify_handler(query)
        
        primary = result.get("primary")
        if primary:
            primary_name = primary.get("domain", "N/A")
            primary_uri = primary.get("uri", "N/A")
            primary_score = primary.get("score", 0)
            alt_count = len(result.get("alternatives", []))
            
            print(f"  ✓ {primary_name}: {primary_uri} (score: {primary_score})")
            if alt_count > 0:
                print(f"    +{alt_count}개 대안")
        else:
            print(f"  ✗ 분류 실패")
        print()
        
        results.append({
            "query": query,
            "primary": primary.get("domain") if primary else None,
            "alternatives_count": len(result.get("alternatives", []))
        })
    
    print(f"{'='*70}")
    print(f"완료: 성공 {sum(1 for r in results if r['primary'])}/{len(results)}개")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    test_queries = [
        "등록금 일정",
        "재직자 야간 MBA",
        "창업 벤처",
        "교원 자격증",
        "논문 심사",
        "정보보호대학원 공지사항",
        "빅데이터 분석 공부"
    ]
    
    batch_test(test_queries)