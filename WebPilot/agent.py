# WebPilot/root_agent.py

from google.adk.agents import Agent 
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm
from WebPilot.constants import constants
from WebPilot.prompt import ORCHESTRATOR_DESCRIPTION, ORCHESTRATOR_INSTRUCTION
import json
import logging

logger = logging.getLogger(__name__)

# 기존 에이전트
from WebPilot.planner_agents.Planner_Agent.agent import Planner_Agent, PlannerAgentClass
from WebPilot.planner_agents.Domain_Priority_Classifier_Agent.agent import Domain_Priority_Classifier_Agent, DomainPriorityClassifierAgentClass
from WebPilot.executor_agents.multimodal_perceiver_agent.agent import Multimodal_Perceiver_Agent, MultilmodalPerceiverAgentClass
from WebPilot.executor_agents.navigation_agent.agent import Navigation_Agent, NavigationAgentClass
from WebPilot.executor_agents.document_handler_agent.agent import Document_Handler_Agent, DocumentHandlerAgentClass
from WebPilot.executor_agents.answer_creation_agent.agent import Answer_Creation_Agent, AnswerCreationAgentClass

# ⭐ 새 에이전트
from WebPilot.executor_agents.crawler_agent.agent import Crawler_Agent, CrawlerAgentClass
from WebPilot.executor_agents.filter_based_page_handler_agent.agent import (
    Filter_Based_Page_Handler_Agent,
    FilterBasedPageHandlerAgentClass
)

# AgentTool 래퍼
class WebPilotAgentTool(AgentTool):
    def __init__(self, agent: Agent):
        super().__init__(agent=agent)

# Tool 생성
planner_tool = WebPilotAgentTool(agent=Planner_Agent)
domain_classifier_tool = WebPilotAgentTool(agent=Domain_Priority_Classifier_Agent)
perceiver_tool = WebPilotAgentTool(agent=Multimodal_Perceiver_Agent)
navigation_tool = WebPilotAgentTool(agent=Navigation_Agent)
document_handler_tool = WebPilotAgentTool(agent=Document_Handler_Agent)
answer_creation_tool = WebPilotAgentTool(agent=Answer_Creation_Agent)

# ⭐ 새 Tool
crawler_tool = WebPilotAgentTool(agent=Crawler_Agent)
filter_handler_tool = WebPilotAgentTool(agent=Filter_Based_Page_Handler_Agent)

# LLM 클라이언트
LLM_CLIENT = LiteLlm(model=constants.MODEL_O3_MINI)

# Orchestrator Agent
root_agent = Agent(
    name="WebPilot_Orchestrator",
    model=LLM_CLIENT,
    description=ORCHESTRATOR_DESCRIPTION,
    instruction=ORCHESTRATOR_INSTRUCTION,
    tools=[
        planner_tool,
        domain_classifier_tool,
        perceiver_tool,
        crawler_tool,                    # ⭐ 추가
        filter_handler_tool,             # ⭐ 추가
        navigation_tool,
        document_handler_tool,
        answer_creation_tool,
    ],
    output_key="orchestrator_result"
)

# Runner 클래스
class OrchestratorRunner:
    """Orchestrator 실행 클래스"""
    
    def __init__(self):
        # 기존 에이전트
        self.planner = PlannerAgentClass()
        self.domain_classifier = DomainPriorityClassifierAgentClass()
        self.perceiver = MultilmodalPerceiverAgentClass()
        self.navigation = NavigationAgentClass()
        self.document_handler = DocumentHandlerAgentClass()
        self.answer_creation = AnswerCreationAgentClass()
        
        # ⭐ 새 에이전트
        self.crawler = CrawlerAgentClass()
        self.filter_handler = FilterBasedPageHandlerAgentClass()
        
        # 상태
        self.state = {
            "query": "",
            "execution_plan": None,
            "step_results": {},
            "visited_urls": [],
            "current_url": "",
            "collected_information": [],
            "attempt_count": 0,
            "max_attempts": 5,
            "replan_count": 0,
            "max_replan": 3
        }
        
        logger.info("Orchestrator Runner 초기화 완료")
    
    def run(self, query: str) -> dict:
        """메인 실행"""
        
        logger.info(f"="*80)
        logger.info(f"사용자 질의: {query}")
        logger.info(f"="*80)
        
        self.state["query"] = query
        
        try:
            # 1. 초기 계획 생성
            plan = self._generate_initial_plan(query)
            
            if not plan:
                return {
                    "status": "error",
                    "error_message": "초기 계획 생성 실패"
                }
            
            # 2. 계획 실행
            result = self._execute_plan(plan)
            
            return result
            
        except Exception as e:
            logger.error(f"Orchestrator 실행 실패: {e}", exc_info=True)
            return {
                "status": "error",
                "error_message": str(e)
            }
    
    def _generate_initial_plan(self, query: str) -> dict:
        """초기 계획 생성"""
        
        logger.info("초기 계획 생성 중...")
        
        try:
            planner_input = json.dumps({"query": query}, ensure_ascii=False)
            plan_json = self.planner.run(planner_input)
            plan = json.loads(plan_json)
            
            self.state["execution_plan"] = plan
            
            logger.info(f"✓ 초기 계획 생성: {len(plan.get('steps', []))}개 단계")
            
            return plan
            
        except Exception as e:
            logger.error(f"초기 계획 생성 실패: {e}")
            return None
    
    def _execute_plan(self, plan: dict) -> dict:
        """계획 실행"""
        
        steps = plan.get("steps", [])
        
        for step in steps:
            step_id = step["step_id"]
            agent_name = step["agent"]
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Step {step_id}: {agent_name}")
            logger.info(f"{'='*60}")
            
            # Dependencies 확인
            if not self._check_dependencies(step):
                logger.warning(f"Step {step_id}: Dependencies 미완료, 스킵")
                continue
            
            # 파라미터 치환
            params = self._substitute_params(step["params"])
            
            # 에이전트 실행
            result = self._execute_agent(agent_name, params)
            
            # 결과 저장
            self.state["step_results"][f"step_{step_id}"] = result
            step["result"] = result
            step["status"] = "completed"
            
            # 결과 분석 및 재계획
            should_replan, replan_reason = self._analyze_result(agent_name, result)
            
            if should_replan:
                logger.info(f"재계획 트리거: {replan_reason}")
                
                new_plan = self._replan(replan_reason, result)
                
                if new_plan and new_plan.get("steps"):
                    # 새 계획 실행
                    return self._execute_plan(new_plan)
                else:
                    # 재계획 실패, 수집된 정보로 답변
                    if self.state["collected_information"]:
                        return self._force_answer_creation()
                    else:
                        return {
                            "status": "error",
                            "error_message": "재계획 실패 및 수집된 정보 없음"
                        }
            
            # Answer Creation이면 종료
            if agent_name == "answer_creation":
                return {
                    "status": "success",
                    "answer": result.get("answer", ""),
                    "sources": result.get("sources", []),
                    "attempts": self.state["attempt_count"],
                    "replan_count": self.state["replan_count"]
                }
        
        # 모든 step 완료했는데 답변 없으면
        if self.state["collected_information"]:
            return self._force_answer_creation()
        else:
            return {
                "status": "error",
                "error_message": "계획 완료했으나 답변 생성 안됨"
            }
    
    def _execute_agent(self, agent_name: str, params: dict):
        """에이전트 실행"""
        
        agent_input = json.dumps(params, ensure_ascii=False)
        
        try:
            if agent_name == "planner":
                output = self.planner.run(agent_input)
            
            elif agent_name == "domain_classifier":
                output = self.domain_classifier.run(agent_input)
            
            elif agent_name == "perceiver":
                output = self.perceiver.run(agent_input)
            
            # ⭐ 새 에이전트
            elif agent_name == "crawler":
                output = self.crawler.run(agent_input)
            
            elif agent_name == "filter_based_page_handler":
                output = self.filter_handler.run(agent_input)
            
            elif agent_name == "navigation_agent":
                output = self.navigation.run(agent_input)
            
            elif agent_name == "document_handler":
                output = self.document_handler.run(agent_input)
            
            elif agent_name == "answer_creation":
                output = self.answer_creation.run(agent_input)
            
            else:
                raise ValueError(f"Unknown agent: {agent_name}")
            
            result = json.loads(output)
            
            logger.info(f"✓ {agent_name} 실행 완료")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ {agent_name} 실행 실패: {e}")
            return {"success": False, "error_message": str(e)}
    
    def _analyze_result(self, agent_name: str, result: dict) -> tuple:
        """결과 분석하여 재계획 필요 여부 판단"""
        
        should_replan = False
        reason = ""
        
        if agent_name == "perceiver":
            analysis = result.get("analysis", {})
            page_type = analysis.get("page_type", "")
            information_found = analysis.get("information_found", False)
            
            # 리스트 페이지 감지
            if page_type == "list_page":
                should_replan = True
                reason = "list_page_detected"
            
            # 필터 페이지 감지
            elif page_type == "filter_page":
                should_replan = True
                reason = "filter_page_detected"
            
            # 정보 없음
            elif not information_found:
                should_replan = True
                reason = "no_information"
        
        elif agent_name == "crawler":
            # Crawler 결과에서 정보 수집
            most_relevant = result.get("most_relevant_analysis")
            
            if most_relevant and most_relevant.get("information_found"):
                self.state["collected_information"].append({
                    "source": "crawler",
                    "content": most_relevant.get("extracted_info", ""),
                    "confidence": most_relevant.get("confidence", 0.0)
                })
        
        elif agent_name == "filter_based_page_handler":
            # FilterHandler 결과에서 정보 수집
            if result.get("results_found"):
                self.state["collected_information"].append({
                    "source": "filter_handler",
                    "result_rows": result.get("result_rows", []),
                    "total_results": result.get("total_results", 0)
                })
            
            # 필터 페이지 아니면 재처리
            elif not result.get("filter_info", {}).get("is_filter_page"):
                should_replan = True
                reason = "not_filter_page"
        
        elif agent_name == "navigation_agent":
            # SAP 페이지로 이동했는지 확인
            final_url = result.get("final_url", "")
            
            if "sap" in final_url.lower():
                should_replan = True
                reason = "sap_page_detected"
            
            # URL 저장
            if final_url:
                self.state["current_url"] = final_url
                if final_url not in self.state["visited_urls"]:
                    self.state["visited_urls"].append(final_url)
        
        return should_replan, reason
    
    def _replan(self, reason: str, last_result: dict) -> dict:
        """재계획"""
        
        self.state["replan_count"] += 1
        
        if self.state["replan_count"] > self.state["max_replan"]:
            logger.warning("최대 재계획 횟수 초과")
            return None
        
        logger.info(f"재계획 {self.state['replan_count']}회: {reason}")
        
        replan_request = {
            "replan": True,
            "original_query": self.state["query"],
            "reason": reason,
            "last_result": last_result,
            "current_url": self.state["current_url"],
            "visited_urls": self.state["visited_urls"],
            "collected_information": self.state["collected_information"]
        }
        
        try:
            planner_input = json.dumps(replan_request, ensure_ascii=False)
            plan_json = self.planner.run(planner_input)
            new_plan = json.loads(plan_json)
            
            logger.info(f"✓ 재계획 완료: {len(new_plan.get('steps', []))}개 단계")
            
            return new_plan
            
        except Exception as e:
            logger.error(f"재계획 실패: {e}")
            return None
    
    def _force_answer_creation(self) -> dict:
        """수집된 정보로 강제 답변 생성"""
        
        logger.info("수집된 정보로 강제 답변 생성")
        
        try:
            answer_input = {
                "query": self.state["query"],
                "collected_information": self.state["collected_information"],
                "trigger_final_answer": True
            }
            
            answer_json = self.answer_creation.run(json.dumps(answer_input, ensure_ascii=False))
            answer_result = json.loads(answer_json)
            
            return {
                "status": "partial_success",
                "answer": answer_result.get("answer", ""),
                "sources": answer_result.get("sources", []),
                "note": "일부 정보만 수집됨"
            }
            
        except Exception as e:
            logger.error(f"강제 답변 생성 실패: {e}")
            return {
                "status": "error",
                "error_message": "답변 생성 실패"
            }
    
    def _check_dependencies(self, step: dict) -> bool:
        """Dependencies 확인"""
        deps = step.get("dependencies", [])
        
        for dep_id in deps:
            step_key = f"step_{dep_id}"
            if step_key not in self.state["step_results"]:
                return False
        
        return True
    
    def _substitute_params(self, params: dict) -> dict:
        """파라미터 템플릿 치환"""
        
        def substitute_value(value):
            if isinstance(value, str) and "{{" in value and "}}" in value:
                # {{step_N.result.key}} 형식
                import re
                pattern = r'\{\{([^}]+)\}\}'
                matches = re.findall(pattern, value)
                
                for match in matches:
                    parts = match.split('.')
                    
                    if parts[0].startswith("step_"):
                        step_key = parts[0]
                        result = self.state["step_results"].get(step_key, {})
                        
                        # 나머지 경로 탐색
                        for part in parts[1:]:
                            if isinstance(result, dict):
                                result = result.get(part, "")
                            else:
                                result = ""
                                break
                        
                        value = value.replace(f"{{{{{match}}}}}", str(result))
            
            elif isinstance(value, dict):
                return {k: substitute_value(v) for k, v in value.items()}
            
            elif isinstance(value, list):
                return [substitute_value(item) for item in value]
            
            return value
        
        return substitute_value(params)


# 전역 인스턴스
orchestrator_runner = OrchestratorRunner()

def run_webpilot(query: str) -> dict:
    """WebPilot 실행 함수"""
    return orchestrator_runner.run(query)