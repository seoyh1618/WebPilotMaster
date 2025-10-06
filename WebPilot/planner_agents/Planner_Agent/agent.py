# WebPilot/planner_agents/Planner_Agent/agent.py

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from .prompt import PLANNER_DESCRIPTION, PLANNER_INSTRUCTION, REPLAN_INSTRUCTION
from .state import ExecutionPlan, ExecutionStep, StepParameters, ReplanRequest
from WebPilot.constants.constants import MODEL_O3_MINI, setup_logging
import json
import re
import logging
from typing import Dict, Any
from datetime import datetime
import uuid

# 로깅 설정 적용
setup_logging()
logger = logging.getLogger(__name__)

class PlannerAgentClass:
    """동적 실행 계획 생성 및 재계획 에이전트"""
    
    def __init__(self, model_name: str = MODEL_O3_MINI):
        self.llm = LiteLlm(model=model_name)
        self.agent = Agent(
            name="Planner",
            model=self.llm,
            description=PLANNER_DESCRIPTION,
            instruction=PLANNER_INSTRUCTION
        )
        logger.info("Planner Agent 초기화 완료")
    
    def run(self, input_text: str) -> str:
        """
        AgentTool 인터페이스 호환을 위한 run 메서드
        
        Args:
            input_text: 사용자 질의 또는 재계획 요청 (JSON 형식)
            
        Returns:
            실행 계획 JSON 문자열
        """
        try:
            # 입력이 재계획 요청인지 확인
            if self._is_replan_request(input_text):
                return self._handle_replan_request(input_text)
            else:
                # 일반 질의 - 새 계획 생성
                return self._create_plan(input_text)
        
        except Exception as e:
            logger.error(f"Planner 실행 실패: {e}", exc_info=True)
            return self._create_fallback_plan(input_text)
    
    def _is_replan_request(self, input_text: str) -> bool:
        """재계획 요청인지 확인"""
        try:
            data = json.loads(input_text)
            return "replan" in data or "failed_step" in data
        except:
            return False
    
    def _create_plan(self, query: str) -> str:
        """
        사용자 질의 기반 실행 계획 생성
        
        Args:
            query: 사용자 질의
            
        Returns:
            ExecutionPlan JSON 문자열
        """
        try:
            logger.info(f"실행 계획 생성 시작: {query}")
            
            prompt = f"""
                다음 사용자 질의를 분석하여 실행 계획을 생성하세요:

                질의: {query}

                분석 항목:
                1. 사용자 의도 (intent)
                2. 필요한 에이전트 단계 (steps)
                3. 각 단계의 파라미터 및 의존성

                반드시 JSON 형식으로만 출력하세요.
            """
            
            result = self.agent.run(prompt)
            plan_dict = self._parse_json_response(result.content)
            
            # plan_id 자동 생성
            if "plan_id" not in plan_dict:
                plan_dict["plan_id"] = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            
            # query 설정
            plan_dict["query"] = query
            
            # ExecutionPlan 객체 생성 및 검증
            execution_plan = ExecutionPlan(**plan_dict)
            
            logger.info(f"실행 계획 생성 완료: {len(execution_plan.steps)}개 단계")
            for i, step in enumerate(execution_plan.steps, 1):
                logger.debug(f"  Step {i}: {step.agent}.{step.action} - {step.description}")
            
            # JSON 문자열로 반환
            return json.dumps(execution_plan.dict(), ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"실행 계획 생성 실패: {e}", exc_info=True)
            return self._create_fallback_plan(query)
    
    def _handle_replan_request(self, request_json: str) -> str:
        """
        재계획 요청 처리
        
        Args:
            request_json: 재계획 요청 JSON
            
        Returns:
            수정된 ExecutionPlan JSON 문자열
        """
        try:
            request_data = json.loads(request_json)
            
            original_plan = ExecutionPlan(**request_data["original_plan"])
            failed_step = ExecutionStep(**request_data["failed_step"])
            failure_reason = request_data["failure_reason"]
            collected_data = request_data.get("collected_data", {})
            
            logger.info(f"재계획 시작: Step {failed_step.step_id} 실패 - {failure_reason}")
            
            # 완료된 단계 목록
            completed_steps = [
                f"Step {s.step_id}: {s.agent} - {s.status}"
                for s in original_plan.steps
                if s.status == "completed"
            ]
            
            prompt = REPLAN_INSTRUCTION.format(
                query=original_plan.query,
                completed_steps="\n".join(completed_steps) if completed_steps else "없음",
                failed_step=f"Step {failed_step.step_id}: {failed_step.agent}.{failed_step.action}",
                failure_reason=failure_reason,
                collected_data=json.dumps(collected_data, ensure_ascii=False, indent=2)
            )
            
            result = self.agent.run(prompt)
            replan_dict = self._parse_json_response(result.content)
            
            # 새로운 plan_id 생성
            replan_dict["plan_id"] = f"{original_plan.plan_id}_replan_{datetime.now().strftime('%H%M%S')}"
            replan_dict["query"] = original_plan.query
            
            # 완료된 step 결과 유지
            for step in original_plan.steps:
                if step.status == "completed":
                    matching_steps = [
                        s for s in replan_dict.get("steps", [])
                        if s.get("agent") == step.agent and s.get("action") == step.action
                    ]
                    if matching_steps:
                        matching_steps[0]["status"] = "completed"
                        matching_steps[0]["result"] = step.result
            
            new_plan = ExecutionPlan(**replan_dict)
            
            logger.info(f"재계획 완료: {len(new_plan.steps)}개 단계")
            
            return json.dumps(new_plan.dict(), ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"재계획 실패: {e}", exc_info=True)
            # 원본 계획의 나머지 step만 실행
            return self._create_partial_plan_json(request_data["original_plan"], 
                                                   request_data["failed_step"]["step_id"])
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON 추출"""
        # JSON 코드 블록 추출
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 코드 블록 없이 직접 JSON
            json_str = response.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.debug(f"응답 내용:\n{response}")
            raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {e}")
    
    def _create_fallback_plan(self, query: str) -> str:
        """폴백 실행 계획 생성 (LLM 실패 시)"""
        logger.warning("폴백 계획 생성 중...")
        
        fallback_plan = ExecutionPlan(
            plan_id=f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            query=query,
            intent="search",
            steps=[
                ExecutionStep(
                    step_id=1,
                    agent="domain_classifier",
                    action="classify_domain_priorities",
                    description="도메인 우선순위 분류 (폴백)",
                    params=StepParameters(query=query),
                    dependencies=[]
                )
            ]
        )
        
        return json.dumps(fallback_plan.dict(), ensure_ascii=False, indent=2)
    
    def _create_partial_plan_json(self, original_plan_dict: Dict, failed_step_id: int) -> str:
        """실패한 step 이후 단계만 포함하는 부분 계획 생성"""
        try:
            original_plan = ExecutionPlan(**original_plan_dict)
            
            remaining_steps = [
                step for step in original_plan.steps
                if step.step_id > failed_step_id and step.status == "pending"
            ]
            
            if not remaining_steps:
                # 남은 step이 없으면 폴백 계획 반환
                return self._create_fallback_plan(original_plan.query)
            
            partial_plan = ExecutionPlan(
                plan_id=f"{original_plan.plan_id}_partial",
                query=original_plan.query,
                intent=original_plan.intent,
                steps=remaining_steps,
                current_step_index=0
            )
            
            return json.dumps(partial_plan.dict(), ensure_ascii=False, indent=2)
        
        except Exception as e:
            logger.error(f"부분 계획 생성 실패: {e}")
            return self._create_fallback_plan(original_plan_dict.get("query", ""))
    def _create_alternative_domain_plan(
            self,
            replan_request: ReplanRequest
        ) -> ExecutionPlan:
            """
            Alternative 도메인 시도 계획 생성
            
            Args:
                replan_request: 재계획 요청
                
            Returns:
                ExecutionPlan
            """
            logger.info("Alternative 도메인 시도 계획 생성")
            
            domain_info = replan_request.domain_info
            
            if not domain_info:
                logger.error("domain_info 없음")
                return ExecutionPlan(
                    plan_id=self._generate_plan_id(suffix="_failed"),
                    query=replan_request.original_query,
                    intent="search",
                    steps=[],
                    reasoning="도메인 정보 없음"
                )
            
            # 현재까지 시도한 도메인 확인
            visited_domains = []
            for url in replan_request.visited_urls:
                for domain_uri in [domain_info.get('primary', {}).get('uri')] + \
                                [alt.get('uri') for alt in domain_info.get('alternatives', [])]:
                    if domain_uri and domain_uri in url:
                        visited_domains.append(domain_uri)
                        break
            
            # 아직 시도하지 않은 도메인 찾기
            all_domains = [domain_info.get('primary')] + domain_info.get('alternatives', [])
            
            next_domain = None
            for domain in all_domains:
                if domain and domain.get('uri') not in visited_domains:
                    next_domain = domain
                    break
            
            if not next_domain:
                logger.warning("더 이상 시도할 도메인 없음")
                return ExecutionPlan(
                    plan_id=self._generate_plan_id(suffix="_failed"),
                    query=replan_request.original_query,
                    intent="search",
                    steps=[],
                    reasoning="모든 도메인을 시도했으나 정보를 찾을 수 없습니다."
                )
            
            logger.info(f"다음 도메인 시도: {next_domain.get('domain')} ({next_domain.get('uri')})")
            
            next_step_id = replan_request.current_attempt * 2 + 1
            
            steps = [
                ExecutionStep(
                    step_id=next_step_id,
                    agent="perceiver",
                    action="analyze_webpage",
                    description=f"{next_domain.get('domain')} 도메인 탐색",
                    params={
                        "url": next_domain.get('uri'),
                        "query": replan_request.original_query,
                        "screenshot_required": True,
                        "depth": 0
                    },
                    dependencies=[]
                )
            ]
            
            return ExecutionPlan(
                plan_id=self._generate_plan_id(suffix=f"_alt_domain_{replan_request.current_attempt}"),
                query=replan_request.original_query,
                intent="search",
                steps=steps,
                reasoning=f"현재 도메인({replan_request.current_url})에서 정보를 찾을 수 없어 "
                        f"alternative 도메인({next_domain.get('domain')})을 시도합니다."
            )
    
    def _create_navigation_plan(
        self,
        replan_request: ReplanRequest,
        recommended_action: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Navigation 액션 계획 생성 (드롭다운/파일 처리 포함)
        
        Args:
            replan_request: 재계획 요청
            recommended_action: Perceiver의 추천 액션
            
        Returns:
            ExecutionPlan
        """
        logger.info(f"Navigation 계획 생성: [{recommended_action.get('element_index')}] "
                   f"{recommended_action.get('element_text')}")
        
        # 파일 다운로드 감지
        if recommended_action.get('should_download'):
            return self._create_file_download_plan(replan_request, recommended_action)
        
        # 드롭다운 메뉴 처리
        if recommended_action.get('requires_submenu_selection'):
            return self._create_dropdown_plan(replan_request, recommended_action)
        
        # 일반 클릭 처리
        return self._create_simple_click_plan(replan_request, recommended_action)
    
    def _create_dropdown_plan(
        self,
        replan_request: ReplanRequest,
        recommended_action: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        드롭다운 메뉴 처리 계획 생성
        
        Args:
            replan_request: 재계획 요청
            recommended_action: Perceiver의 추천 (드롭다운 정보 포함)
            
        Returns:
            ExecutionPlan
        """
        logger.info(f"드롭다운 메뉴 처리: {recommended_action.get('element_text')}")
        
        visible_submenus = recommended_action.get('visible_submenus', [])
        recommended_submenu_index = recommended_action.get('recommended_submenu_index')
        
        if not visible_submenus or recommended_submenu_index is None:
            logger.warning("하위 메뉴 정보 없음, 일반 클릭으로 처리")
            return self._create_simple_click_plan(replan_request, recommended_action)
        
        if recommended_submenu_index >= len(visible_submenus):
            logger.warning(f"잘못된 submenu index: {recommended_submenu_index}")
            recommended_submenu_index = 0
        
        submenu = visible_submenus[recommended_submenu_index]
        
        logger.info(f"  메인 메뉴: {recommended_action.get('element_text')}")
        logger.info(f"  하위 메뉴: {submenu.get('text')}")
        
        # Navigation 액션 생성
        actions = [
            {
                "action_type": "hover",
                "coordinates": recommended_action.get('coordinates'),
                "description": f"{recommended_action.get('element_text')} 메뉴에 호버"
            },
            {
                "action_type": "wait",
                "duration": 1,
                "description": "하위 메뉴 표시 대기"
            },
            {
                "action_type": "click",
                "coordinates": submenu.get('coordinates'),
                "description": f"'{submenu.get('text')}' 하위 메뉴 클릭"
            },
            {
                "action_type": "wait",
                "duration": 2,
                "description": "페이지 로딩 대기"
            }
        ]
        
        next_step_id = replan_request.current_attempt * 2 + 1
        
        steps = [
            ExecutionStep(
                step_id=next_step_id,
                agent="navigation_agent",
                action="execute_actions",
                description=f"드롭다운 메뉴 '{recommended_action.get('element_text')}' > '{submenu.get('text')}' 클릭",
                params={
                    "actions": actions,
                    "start_url": None
                },
                dependencies=[]
            ),
            ExecutionStep(
                step_id=next_step_id + 1,
                agent="perceiver",
                action="analyze_webpage",
                description="하위 메뉴 클릭 후 페이지 관찰",
                params={
                    "url": f"{{{{step_{next_step_id}.result.final_url}}}}",
                    "query": replan_request.original_query,
                    "screenshot_required": True,
                    "depth": replan_request.current_attempt
                },
                dependencies=[next_step_id]
            )
        ]
        
        return ExecutionPlan(
            plan_id=self._generate_plan_id(suffix=f"_dropdown_{replan_request.current_attempt}"),
            query=replan_request.original_query,
            intent="search",
            steps=steps,
            reasoning=f"드롭다운 메뉴 '{recommended_action.get('element_text')}'의 "
                     f"하위 메뉴 '{submenu.get('text')}'를 클릭합니다. "
                     f"{recommended_action.get('reasoning', '')}"
        )
    
    def _create_simple_click_plan(
        self,
        replan_request: ReplanRequest,
        recommended_action: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        일반 클릭 계획 생성 (기존 _create_navigation_plan 로직)
        
        Args:
            replan_request: 재계획 요청
            recommended_action: Perceiver의 추천 액션
            
        Returns:
            ExecutionPlan
        """
        logger.info(f"일반 클릭 처리: {recommended_action.get('element_text')}")
        
        # Navigation 액션 생성
        action_type = recommended_action.get('action_type', 'click')
        
        actions = []
        
        # goto vs click
        if action_type == 'goto' and recommended_action.get('href'):
            actions.append({
                "action_type": "goto",
                "url": recommended_action.get('href'),
                "description": f"{recommended_action.get('element_text')} 페이지로 이동"
            })
        else:
            actions.append({
                "action_type": "click",
                "coordinates": recommended_action.get('coordinates'),
                "description": f"{recommended_action.get('element_text')} 클릭"
            })
        
        # 대기
        actions.append({
            "action_type": "wait",
            "duration": 2,
            "description": "페이지 로딩 대기"
        })
        
        # 다음 step_id 계산
        next_step_id = replan_request.current_attempt * 2 + 1
        
        steps = [
            ExecutionStep(
                step_id=next_step_id,
                agent="navigation_agent",
                action="execute_actions",
                description=f"'{recommended_action.get('element_text')}' 액션 실행",
                params={
                    "actions": actions,
                    "start_url": None
                },
                dependencies=[]
            ),
            ExecutionStep(
                step_id=next_step_id + 1,
                agent="perceiver",
                action="analyze_webpage",
                description="액션 후 페이지 관찰",
                params={
                    "url": f"{{{{step_{next_step_id}.result.final_url}}}}",
                    "query": replan_request.original_query,
                    "screenshot_required": True,
                    "depth": replan_request.current_attempt
                },
                dependencies=[next_step_id]
            )
        ]
        
        return ExecutionPlan(
            plan_id=self._generate_plan_id(suffix=f"_replan_{replan_request.current_attempt}"),
            query=replan_request.original_query,
            intent="search",
            steps=steps,
            reasoning=f"Perceiver가 '{recommended_action.get('element_text')}'를 추천했습니다 "
                     f"(confidence: {recommended_action.get('confidence'):.2f}). "
                     f"{recommended_action.get('reasoning', '')}"
        )
    
    def _create_file_download_plan(
        self,
        replan_request: ReplanRequest,
        recommended_action: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        파일 다운로드 계획 생성
        
        Args:
            replan_request: 재계획 요청
            recommended_action: Perceiver의 추천 (파일 정보 포함)
            
        Returns:
            ExecutionPlan
        """
        file_info = recommended_action.get('file_info', {})
        
        if not file_info or not file_info.get('file_url'):
            logger.warning("파일 정보 없음")
            return ExecutionPlan(
                plan_id=self._generate_plan_id(suffix="_no_file"),
                query=replan_request.original_query,
                intent="search",
                steps=[],
                reasoning="파일 정보가 없습니다."
            )
        
        logger.info(f"파일 다운로드 계획 생성: {file_info.get('file_name')}")
        
        next_step_id = replan_request.current_attempt * 2 + 1
        
        # TODO: Document Handler Agent 구현 후 활성화
        # 현재는 일단 정보를 찾았다고 반환
        
        steps = []
        
        # 임시: 파일 URL만 반환
        return ExecutionPlan(
            plan_id=self._generate_plan_id(suffix="_file_found"),
            query=replan_request.original_query,
            intent="search",
            steps=steps,
            reasoning=f"파일을 발견했습니다: {file_info.get('file_name')} ({file_info.get('file_url')}). "
                     f"Document Handler Agent 구현 후 파일 내용을 분석할 예정입니다."
        )
# AgentTool이 사용할 Agent 인스턴스
Planner_Agent = Agent(
    name="Planner",
    model=LiteLlm(model=MODEL_O3_MINI),
    description=PLANNER_DESCRIPTION,
    instruction=PLANNER_INSTRUCTION
)