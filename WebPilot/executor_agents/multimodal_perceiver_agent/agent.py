# WebPilot/executor_agents/multimodal_perceiver_agent/agent.py

from __future__ import annotations

from typing import Any, Dict, List
from dotenv import load_dotenv

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.models.lite_llm import LiteLlm

from WebPilot.executor_agents.multimodal_perceiver_agent.prompt import INSTRUCTION, DESCRIPTION
from WebPilot.constants.constants import MODEL_O3_MINI

load_dotenv()


def _receive_domain_info(
    primary_domain: str,
    primary_uri: str,
    alternatives: List[Dict[str, Any]],
    user_query: str,
    tool_context: Any  # ADK will inject context automatically
) -> Dict[str, Any]:
    """
    도메인 분류 결과를 전달받아 출력하는 핸들러
    """
    print("\n" + "=" * 70)
    print("✅ Multimodal Perceiver Agent가 받은 정보:")
    print("=" * 70)
    print(f"📍 Primary Domain: {primary_domain}")
    print(f"🔗 Primary URI: {primary_uri}")
    print(f"💬 User Query: {user_query}")
    print(f"\n📋 Alternatives ({len(alternatives)}개):")

    for i, alt in enumerate(alternatives, 1):
        # alt가 str일 경우 get 메서드가 없으므로, dict 타입일 때만 get 사용
        if isinstance(alt, dict):
            print(f"\n  [{i}] {alt.get('domain', 'N/A')}")
            print(f"      URI: {alt.get('uri', 'N/A')}")
            print(f"      Score: {alt.get('score', 0)}")
            print(f"      Priority: {alt.get('priority', 'N/A')}")
            print(f"      Confidence: {alt.get('confidence', 'N/A')}")
            if alt.get('condition'):
                print(f"      조건: {alt['condition']}")
            if alt.get('reasoning'):
                print(f"      사유: {alt['reasoning']}")
        else:
            # str 등 dict가 아닌 타입이면 문자열로 출력
            print(f"\n  [{i}] {str(alt)}")

    print("=" * 70 + "\n")

    # 도메인 정보 세션 상태에 저장
    tool_context.state["received_primary"] = {
        "domain": primary_domain,
        "uri": primary_uri,
    }
    tool_context.state["received_alternatives_count"] = len(alternatives)

    # 분석 결과 반환
    return {
        "status": "received_and_analyzed",
        "primary": {"domain": primary_domain, "uri": primary_uri},
        "alternatives_count": len(alternatives),
        "next_action": f"{primary_uri}로 이동하여 '{user_query}' 관련 정보 탐색 필요",
        "message": f"✅ {primary_domain} 도메인 정보를 성공적으로 수신하고 분석했습니다."
    }


# FunctionTool로 래핑 (parameters 포함)
receive_domain_info_tool = FunctionTool(
    func=_receive_domain_info
)

# Agent 생성
Multimodal_Perceiver_Agent = Agent(
    name="Multimodal_Perceiver_Agent",
    model=LiteLlm(model=MODEL_O3_MINI),
    description=DESCRIPTION,
    instruction=INSTRUCTION,
    tools=[receive_domain_info_tool],
    output_key="Multimodal_Perceiver_Output",
)
