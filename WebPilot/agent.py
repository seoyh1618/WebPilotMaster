# WebPilot/root_agent.py

from google.adk.tools.agent_tool import AgentTool
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv
import logging
import json
from typing import Dict, Any, Optional

from WebPilot.prompt import ORCHESTRATOR_DESCRIPTION, ORCHESTRATOR_INSTRUCTION
from WebPilot.constants.constants import MODEL_O3_MINI

# Agents
from WebPilot.planner_agents.Planner_Agent.agent import Planner_Agent
from WebPilot.planner_agents.Domain_Priority_Classifier_Agent.agent import Domain_Priority_Classifier_Agent
from WebPilot.executor_agents.multimodal_perceiver_agent.agent import Multimodal_Perceiver_Agent
from WebPilot.executor_agents.navigation_agent.agent import Navigation_Agent

load_dotenv()
logger = logging.getLogger(__name__)

# LLM 클라이언트 초기화
LLM_CLIENT = LiteLlm(model=MODEL_O3_MINI)

# Agent Tools 생성
planner_tool = AgentTool(agent=Planner_Agent)
domain_classifier_tool = AgentTool(agent=Domain_Priority_Classifier_Agent)
perceiver_tool = AgentTool(agent=Multimodal_Perceiver_Agent)
navigation_tool = AgentTool(agent=Navigation_Agent)

# TODO: 향후 추가 예정
# document_handler_tool = AgentTool(agent=Document_Handler_Agent)
# answer_creation_tool = AgentTool(agent=Answer_Creation_Agent)

# Orchestrator Agent 생성
root_agent = Agent(
    name="WebPilot_Orchestrator",
    model=LLM_CLIENT,
    description=ORCHESTRATOR_DESCRIPTION,
    instruction=ORCHESTRATOR_INSTRUCTION,
    tools=[
        planner_tool,
        domain_classifier_tool,
        perceiver_tool,
        navigation_tool,
    ],
    output_key="orchestrator_result"
)

logger.info("="*80)
logger.info("WebPilot Orchestrator Agent 초기화 완료")
logger.info(f"등록된 도구: {len(root_agent.tools)}개")
logger.info("  - Planner: 실행 계획 생성 및 재계획")
logger.info("  - Domain Classifier: 도메인 우선순위 분류")
logger.info("  - Perceiver: 웹페이지 관찰 및 액션 추천")
logger.info("  - Navigator: 웹 액션 실행")
logger.info("="*80)


# ============================================
# Orchestrator 실행 로직 (추가)
# ============================================

class OrchestratorRunner:
    """Orchestrator 실행 및 상태 관리"""
    
    def __init__(self):
        self.state = {
            "query": "",
            "execution_plan": None,
            "step_results": {},
            "visited_urls": [],
            "current_url": "",
            "attempt_count": 0,
            "max_attempts": 5,
            "domain_info": None
        }
    
    def run(self, query: str) -> Dict[str, Any]:
        """
        사용자 질의 실행
        
        Args:
            query: 사용자 질의
            
        Returns:
            최종 결과
        """
        logger.info("="*80)
        logger.info("WebPilot 실행 시작")
        logger.info(f"질의: {query}")
        logger.info("="*80)
        
        self.state["query"] = query
        
        try:
            # Step 1: 초기 계획 생성
            logger.info("\n[Step 1] 초기 계획 생성")
            plan = self._create_initial_plan(query)
            
            if not plan or not plan.get("steps"):
                return self._create_error_result("초기 계획 생성 실패")
            
            self.state["execution_plan"] = plan
            
            # Step 2: 계획 실행
            logger.info("\n[Step 2] 계획 실행 시작")
            result = self._execute_plan(plan)
            
            return result
            
        except Exception as e:
            logger.error(f"Orchestrator 실행 실패: {e}", exc_info=True)
            return self._create_error_result(str(e))
    
    def _create_initial_plan(self, query: str) -> Optional[Dict]:
        """초기 계획 생성"""
        try:
            planner_input = json.dumps({"query": query})
            planner_output = planner_tool.agent.run(planner_input)
            
            output_dict = json.loads(planner_output)
            plan = output_dict.get("plan")
            
            logger.info(f"  ✓ 계획 생성 완료: {len(plan.get('steps', []))}개 step")
            
            return plan
            
        except Exception as e:
            logger.error(f"  ✗ 계획 생성 실패: {e}")
            return None
    
    def _execute_plan(self, plan: Dict) -> Dict[str, Any]:
        """계획 실행"""
        steps = plan.get("steps", [])
        
        for step in steps:
            step_id = step["step_id"]
            agent_name = step["agent"]
            
            logger.info(f"\n  [Step {step_id}] {step['description']}")
            logger.info(f"    Agent: {agent_name}")
            
            # Dependencies 확인
            if not self._check_dependencies(step):
                logger.error(f"    ✗ Dependencies 미완료")
                continue
            
            # 파라미터 템플릿 치환
            params = self._substitute_params(step["params"])
            
            # Agent 실행
            result = self._execute_agent(agent_name, params)
            
            if not result:
                logger.error(f"    ✗ Agent 실행 실패")
                continue
            
            # 결과 저장
            self.state["step_results"][step_id] = result
            
            # Agent별 후처리
            if agent_name == "domain_classifier":
                self._handle_domain_classifier_result(result)
            
            elif agent_name == "perceiver":
                if self._handle_perceiver_result(result):
                    # 정보 발견, 종료
                    return self._create_success_result(result)
                else:
                    # 정보 없음, 재계획
                    replan_result = self._replan()
                    if replan_result:
                        return replan_result
            
            elif agent_name == "navigation_agent":
                self._handle_navigation_result(result)
        
        # 모든 step 완료했지만 정보 못 찾음
        return self._create_error_result("정보를 찾을 수 없습니다")
    
    def _check_dependencies(self, step: Dict) -> bool:
        """Dependencies 확인"""
        dependencies = step.get("dependencies", [])
        
        for dep_id in dependencies:
            if dep_id not in self.state["step_results"]:
                return False
        
        return True
    
    def _substitute_params(self, params: Dict) -> Dict:
        """파라미터 템플릿 치환"""
        import re
        
        params_str = json.dumps(params)
        
        # {{step_N.result.key}} 패턴 찾기
        pattern = r'\{\{step_(\d+)\.result\.([^\}]+)\}\}'
        
        def replace_template(match):
            step_id = int(match.group(1))
            key_path = match.group(2)
            
            if step_id not in self.state["step_results"]:
                logger.warning(f"      템플릿 치환 실패: step_{step_id} 결과 없음")
                return match.group(0)
            
            # 중첩된 키 접근
            value = self.state["step_results"][step_id]
            for key in key_path.split('.'):
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    logger.warning(f"      템플릿 치환 실패: {key_path}")
                    return match.group(0)
            
            return str(value) if value is not None else match.group(0)
        
        params_str = re.sub(pattern, replace_template, params_str)
        
        return json.loads(params_str)
    
    def _execute_agent(self, agent_name: str, params: Dict) -> Optional[Dict]:
        """Agent 실행"""
        try:
            agent_input = json.dumps(params, ensure_ascii=False)
            
            if agent_name == "domain_classifier":
                output = domain_classifier_tool.agent.run(agent_input)
            
            elif agent_name == "perceiver":
                output = perceiver_tool.agent.run(agent_input)
            
            elif agent_name == "navigation_agent":
                output = navigation_tool.agent.run(agent_input)
            
            else:
                logger.error(f"      알 수 없는 agent: {agent_name}")
                return None
            
            result = json.loads(output)
            
            logger.info(f"    ✓ 실행 완료")
            
            return result
            
        except Exception as e:
            logger.error(f"    ✗ 실행 실패: {e}")
            return None
    
    def _handle_domain_classifier_result(self, result: Dict):
        """Domain Classifier 결과 처리"""
        result_data = result.get("result", {})
        primary = result_data.get("primary")
        alternatives = result_data.get("alternatives", [])
        
        if primary:
            logger.info(f"      선택된 도메인: {primary.get('domain')} ({primary.get('uri')})")
            logger.info(f"      Score: {primary.get('score')}, Priority: {primary.get('priority')}")
            logger.info(f"      Alternative 도메인: {len(alternatives)}개")
            
            # 전체 도메인 정보 저장 (순차 탐색용)
            self.state["domain_info"] = result_data
            self.state["current_url"] = primary.get('uri')
            self.state["current_domain_index"] = 0  # primary부터 시작
            self.state["all_domains"] = [primary] + alternatives
    
    def _handle_perceiver_result(self, result: Dict) -> bool:
        """
        Perceiver 결과 처리
        
        Returns:
            True: 정보 발견 (종료)
            False: 정보 없음 (재계획 필요)
        """
        analysis = result.get("analysis", {})
        information_found = analysis.get("information_found", False)
        
        if information_found:
            logger.info(f"      ✓ 정보 발견!")
            extracted_info = analysis.get("extracted_info", "")
            logger.info(f"      내용: {extracted_info[:100]}...")
            return True
        
        else:
            logger.info(f"      정보 없음")
            
            recommended_action = analysis.get("recommended_action")
            
            if recommended_action and recommended_action.get("should_click"):
                confidence = recommended_action.get("confidence", 0)
                element_text = recommended_action.get("element_text", "")
                
                logger.info(f"      추천: {element_text} (confidence: {confidence:.2f})")
            else:
                logger.info(f"      추천 없음")
            
            return False
    
    def _handle_navigation_result(self, result: Dict):
        """Navigation 결과 처리"""
        final_url = result.get("final_url", "")
        success = result.get("success", False)
        
        if success:
            logger.info(f"      ✓ Navigation 성공")
            logger.info(f"      최종 URL: {final_url}")
            
            self.state["current_url"] = final_url
            self.state["visited_urls"].append(final_url)
        else:
            logger.error(f"      ✗ Navigation 실패")
    
    def _replan(self) -> Optional[Dict[str, Any]]:
        """재계획"""
        self.state["attempt_count"] += 1
        
        logger.info(f"\n[재계획] 시도 {self.state['attempt_count']}/{self.state['max_attempts']}")
        
        # 최대 시도 횟수 확인
        if self.state["attempt_count"] >= self.state["max_attempts"]:
            logger.warning("  최대 시도 횟수 초과")
            return self._create_error_result("최대 시도 횟수를 초과했습니다")
        
        # 최근 Perceiver 결과 찾기
        last_perceiver_result = None
        for step_id in sorted(self.state["step_results"].keys(), reverse=True):
            result = self.state["step_results"][step_id]
            if "analysis" in result:
                last_perceiver_result = result
                break
        
        if not last_perceiver_result:
            logger.error("  Perceiver 결과 없음")
            return self._create_error_result("Perceiver 결과 없음")
        
        # 재계획 요청 생성
        replan_request = {
            "replan_request": {
                "replan": True,
                "original_query": self.state["query"],
                "current_attempt": self.state["attempt_count"],
                "max_attempts": self.state["max_attempts"],
                "perceiver_result": last_perceiver_result,
                "visited_urls": self.state["visited_urls"],
                "current_url": self.state["current_url"],
                "domain_info": self.state.get("domain_info")  # ⭐ 전체 도메인 정보 전달
            }
        }
        
        # Planner 재호출
        try:
            planner_input = json.dumps(replan_request, ensure_ascii=False)
            planner_output = planner_tool.agent.run(planner_input)
            
            output_dict = json.loads(planner_output)
            new_plan = output_dict.get("plan")
            
            if not new_plan or not new_plan.get("steps"):
                logger.warning("  재계획 생성 실패 또는 steps 없음 (종료)")
                return self._create_error_result(new_plan.get("reasoning", "정보를 찾을 수 없습니다"))
            
            logger.info(f"  ✓ 재계획 생성 완료: {len(new_plan['steps'])}개 step")
            
            # 새 계획 실행
            return self._execute_plan(new_plan)
            
        except Exception as e:
            logger.error(f"  ✗ 재계획 실패: {e}")
            return self._create_error_result(f"재계획 실패: {e}") 
    def _create_success_result(self, perceiver_result: Dict) -> Dict[str, Any]:
        """성공 결과 생성"""
        analysis = perceiver_result.get("analysis", {})
        
        return {
            "status": "success",
            "answer": analysis.get("extracted_info", ""),
            "confidence": analysis.get("confidence", 0.0),
            "source_url": self.state["current_url"],
            "attempts": self.state["attempt_count"],
            "visited_urls": self.state["visited_urls"]
        }
    
    def _create_error_result(self, message: str) -> Dict[str, Any]:
        """에러 결과 생성"""
        return {
            "status": "error",
            "error_message": message,
            "attempts": self.state["attempt_count"],
            "visited_urls": self.state["visited_urls"]
        }

    def _handle_perceiver_result(self, result: Dict) -> bool:
        """
        Perceiver 결과 처리
        
        Returns:
            True: 정보 발견 또는 파일 발견 (종료)
            False: 정보 없음 (재계획 필요)
        """
        analysis = result.get("analysis", {})
        information_found = analysis.get("information_found", False)
        
        if information_found:
            logger.info(f"      ✓ 정보 발견!")
            extracted_info = analysis.get("extracted_info", "")
            logger.info(f"      내용: {extracted_info[:100]}...")
            return True
        
        else:
            logger.info(f"      정보 없음")
            
            recommended_action = analysis.get("recommended_action")
            
            if not recommended_action:
                logger.info(f"      추천 없음")
                return False
            
            # 파일 다운로드 감지
            if recommended_action.get("should_download"):
                file_info = recommended_action.get("file_info", {})
                logger.info(f"      📎 파일 발견: {file_info.get('file_name')}")
                logger.info(f"      URL: {file_info.get('file_url')}")
                
                # TODO: Document Handler로 파일 처리
                # 현재는 일단 파일을 찾았다고 간주하고 종료
                logger.warning("      Document Handler 미구현, 파일 URL만 반환")
                
                # 임시로 파일 URL을 정보로 저장
                self.state["found_file"] = file_info
                return True  # 파일을 찾았으니 일단 종료
            
            # 일반 클릭 추천
            if recommended_action.get("should_click"):
                confidence = recommended_action.get("confidence", 0)
                element_text = recommended_action.get("element_text", "")
                
                logger.info(f"      추천: {element_text} (confidence: {confidence:.2f})")
                
                # 드롭다운 감지
                if recommended_action.get("requires_submenu_selection"):
                    visible_submenus = recommended_action.get("visible_submenus", [])
                    recommended_submenu = recommended_action.get("recommended_submenu_index")
                    
                    if visible_submenus and recommended_submenu is not None:
                        submenu = visible_submenus[recommended_submenu]
                        logger.info(f"      드롭다운: {element_text} > {submenu.get('text')}")
            
            return False
    
    def _create_success_result(self, perceiver_result: Dict) -> Dict[str, Any]:
        """성공 결과 생성 (파일 지원)"""
        analysis = perceiver_result.get("analysis", {})
        
        # 파일을 찾은 경우
        if self.state.get("found_file"):
            file_info = self.state["found_file"]
            return {
                "status": "success",
                "answer": f"관련 파일을 찾았습니다: {file_info.get('file_name')}",
                "file_url": file_info.get('file_url'),
                "file_type": file_info.get('file_type'),
                "confidence": file_info.get('confidence', 0.0),
                "source_url": self.state["current_url"],
                "attempts": self.state["attempt_count"],
                "visited_urls": self.state["visited_urls"],
                "note": "Document Handler 구현 후 파일 내용을 분석할 예정입니다."
            }
        
        # 일반적인 정보 발견
        return {
            "status": "success",
            "answer": analysis.get("extracted_info", ""),
            "confidence": analysis.get("confidence", 0.0),
            "source_url": self.state["current_url"],
            "attempts": self.state["attempt_count"],
            "visited_urls": self.state["visited_urls"]
        }

# ============================================
# 전역 Orchestrator Runner 인스턴스
# ============================================

orchestrator_runner = OrchestratorRunner()


# ============================================
# 간편 실행 함수
# ============================================

def run_webpilot(query: str) -> Dict[str, Any]:
    """
    WebPilot 실행
    
    Args:
        query: 사용자 질의
        
    Returns:
        실행 결과
    """
    runner = OrchestratorRunner()
    return runner.run(query)


# ============================================
# 테스트 코드
# ============================================

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 테스트 실행
    test_query = "일반대학원 사물함 신청 방법 알려줘"
    
    print("\n" + "="*80)
    print(f"WebPilot 테스트: {test_query}")
    print("="*80 + "\n")
    
    result = run_webpilot(test_query)
    
    print("\n" + "="*80)
    print("최종 결과:")
    print("="*80)
    print(json.dumps(result, ensure_ascii=False, indent=2))