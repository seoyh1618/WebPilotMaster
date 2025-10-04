from google.adk.tools.agent_tool import AgentTool
from google.adk.agents import Agent
from google.adk.tools import google_search
from WebPilot.prompt import INSTRUCTION,DESCRIPTION
from WebPilot.constants.constants import MODEL_GEMINI_2_5_FLASH,MODEL_O3_MINI
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv
from WebPilot.planner_agents.Domain_Priority_Classifier_Agent.agent import Domain_Priority_Classifier_Agent
from WebPilot.executor_agents.multimodal_perceiver_agent.agent import (
    Multimodal_Perceiver_Agent,
)
load_dotenv()
LLM_CLIENT = LiteLlm(model=MODEL_O3_MINI)


domain_classifier_tool = AgentTool(
    agent=Domain_Priority_Classifier_Agent
)

perceiver_tool = AgentTool(
    agent=Multimodal_Perceiver_Agent
)

root_agent = Agent(
    name="WebPilot_Root_Orchestrator",
    model=LLM_CLIENT,
    description=DESCRIPTION,   # ← 프롬프트 템플릿 사용
    instruction=INSTRUCTION,   # ← 프롬프트 템플릿 사용
    tools=[domain_classifier_tool, perceiver_tool],
    output_key="WebPilot_Root_Output",
)
