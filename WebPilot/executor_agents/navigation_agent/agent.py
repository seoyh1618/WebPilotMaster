
# WebPilot/executor_agents/navigation_agent/agent.py

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .prompt import NAVIGATION_DESCRIPTION, NAVIGATION_INSTRUCTION
from .state import NavigationInput, NavigationOutput, NavigationResult
from .playwright_executor import execute_actions_sync, PlaywrightExecutorError
from WebPilot.constants import constants
import json
import logging
import time

logger = logging.getLogger(__name__)

class NavigationAgentClass:
    """Navigation Agent 구현 (명령 실행자)"""
    
    def __init__(self, model_name: str = constants.MODEL_O3_MINI):
        self.llm = LiteLlm(model=model_name)
        self.agent = Agent(
            name="NavigationAgent",
            model=self.llm,
            description=NAVIGATION_DESCRIPTION,
            instruction=NAVIGATION_INSTRUCTION
        )
        logger.info("Navigation Agent 초기화 완료")
    
    def run(self, input_text: str) -> str:
        """
        AgentTool 인터페이스 호환 메서드
        
        Args:
            input_text: JSON 형식 입력
            
        Returns:
            JSON 형식 출력
        """
        start_time = time.time()
        
        try:
            # 입력 파싱
            input_data = json.loads(input_text)
            nav_input = NavigationInput(**input_data)
            
            logger.info(f"Navigation 실행 시작: {len(nav_input.actions)}개 액션")
            
            # Playwright 실행
            results = execute_actions_sync(
                actions=nav_input.actions,
                start_url=nav_input.start_url
            )
            
            # 결과 생성
            success = all(r.success for r in results)
            final_url = results[-1].current_url if results else ""
            
            output = NavigationOutput(
                results=results,
                final_url=final_url,
                total_execution_time=time.time() - start_time,
                success=success,
                error_message=None if success else "일부 액션 실패"
            )
            
            logger.info(f"Navigation 완료: 성공={success}, 최종 URL={final_url}")
            
            return json.dumps(output.dict(), ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Navigation 실행 실패: {e}", exc_info=True)
            
            # 에러 응답
            error_output = NavigationOutput(
                results=[],
                final_url="",
                total_execution_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
            
            return json.dumps(error_output.dict(), ensure_ascii=False, indent=2)


# AgentTool이 사용할 Agent 인스턴스
Navigation_Agent = Agent(
    name="NavigationAgent",
    model=LiteLlm(model=constants.MODEL_O3_MINI),
    description=NAVIGATION_DESCRIPTION,
    instruction=NAVIGATION_INSTRUCTION
)