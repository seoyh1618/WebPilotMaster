from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools import agent_tool

from WebPilot.prompt import INSTRUCTION
from WebPilot.constants.constants import MODEL_GEMINI_2_5_FLASH
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv

load_dotenv()

#agent_search = Agent(
#    name="google_search_agent",
#    model=MODEL_GEMINI_2_5_FLASH,
#    description="An agent that performs Google searches.",
#    instruction="Perform a Google search.",
#    tools=[google_search]
#)

root_agent = Agent(
    name="Language_Translator_Agent",
    model=MODEL_GEMINI_2_5_FLASH,
    description="한국어 입력을 자연스럽고 정확한 영어로 번역하는 에이전트입니다. 원문의 의미·톤·형식을 최대한 유지하며, 번역을 수행합니다.",
    instruction=INSTRUCTION,
    #tools=[agent_tool.AgentTool(agent=agent_search)],
    #sub_agents=[test_case_generator_agent],
    output_key="Language_Translator_output",
)