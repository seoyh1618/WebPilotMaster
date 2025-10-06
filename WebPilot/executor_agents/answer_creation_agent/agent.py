
# WebPilot/executor_agents/answer_creation_agent/agent.py

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .prompt import (
    ANSWER_CREATION_DESCRIPTION,
    ANSWER_CREATION_INSTRUCTION,
    create_answer_prompt
)
from .state import AnswerInput, AnswerOutput, SourceInfo
from WebPilot.constants import constants
import json
import logging
import time

logger = logging.getLogger(__name__)

class AnswerCreationAgentClass:
    """Answer Creation Agent 구현"""
    
    def __init__(self, model_name: str = constants.MODEL_O3_MINI):
        self.llm = LiteLlm(model=model_name)
        logger.info("Answer Creation Agent 초기화 완료")
    
    def run(self, input_text: str) -> str:
        """AgentTool 인터페이스 호환 메서드"""
        start_time = time.time()
        
        try:
            # 입력 파싱
            input_data = json.loads(input_text)
            answer_input = AnswerInput(**input_data)
            
            logger.info(f"답변 생성 시작: {answer_input.query}")
            logger.info(f"수집된 정보: {len(answer_input.collected_information)}개")
            
            # 정보가 없으면 실패
            if not answer_input.collected_information:
                raise Exception("수집된 정보가 없습니다")
            
            # LLM으로 답변 생성
            prompt = create_answer_prompt(
                answer_input.query,
                answer_input.collected_information,
                [s.dict() for s in answer_input.sources]
            )
            
            response = self.llm.generate(prompt)
            
            # JSON 파싱
            result = json.loads(response)
            
            # SourceInfo 객체 변환
            sources_used = [
                SourceInfo(**src)
                for src in result.get('sources_used', [])
            ]
            
            # 출력 생성
            output = AnswerOutput(
                success=True,
                answer=result.get('answer', ''),
                confidence=result.get('confidence', 0.0),
                sources_used=sources_used,
                additional_notes=result.get('additional_notes', '')
            )
            
            logger.info(f"✓ 답변 생성 완료 (confidence: {output.confidence:.2f})")
            
            return json.dumps(output.dict(), ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Answer Creation 실패: {e}", exc_info=True)
            
            error_output = AnswerOutput(
                success=False,
                error_message=str(e)
            )
            
            return json.dumps(error_output.dict(), ensure_ascii=False, indent=2)


# AgentTool이 사용할 Agent 인스턴스
Answer_Creation_Agent = Agent(
    name="AnswerCreationAgent",
    model=LiteLlm(model=constants.MODEL_O3_MINI),
    description=ANSWER_CREATION_DESCRIPTION,
    instruction=ANSWER_CREATION_INSTRUCTION
)