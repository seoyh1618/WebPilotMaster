from google.adk.agents import Agent
from google.adk.tools import agent_tool
from google.adk.tools import FunctionTool
from google.genai import types

from WebPilot.executor_agents.navigation_agent.prompt import INSTRUCTION, DESCRIPTION
from WebPilot.constants.constants import MODEL_GEMINI_2_5_FLASH
from google.adk.models.lite_llm import LiteLlm

import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Optional, Dict, Any, Literal

from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHOT_ROOT = PROJECT_ROOT / "artifacts" / "screenshots"


def build_shot_path(url: str, domain_label: str, hint: str, strategy: str | None = None) -> Path:
    """
    지정한 규칙으로 스크린샷 경로를 생성합니다.
    <PROJECT_ROOT>/artifacts/screenshots/<YYYYMMDD>/<도메인>/<도메인슬러그>/<HHMMSS>_<strategy>_<hint>.png
    """
    now = datetime.now()
    date_str = now.strftime("%Y%m%d") 

    host = urlparse(url).hostname or "unknown"
    host_slug = re.sub(r"[^a-zA-Z0-9]+", "-", host).strip("-").lower() or "unknown"

    filename = f"{now.strftime('%H%M%S')}_{(strategy or 'tag')}_{hint}.png"
    target_dir = SHOT_ROOT / date_str / (domain_label or "unknown") / host_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / filename
    
class PlaywrightRuntime:
    """
    아주 기본적인 런타임입니다.
    - 브라우저 1개만 띄우고, 요청 시 컨텍스트/페이지를 만들어 제공합니다.
    - 에러 메시지와 주석은 모두 한국어로 작성합니다.
    """
    def __init__(self) -> None:
        self._pw = None
        self._browser: Optional[Browser] = None

    async def ensure_started(self, headless: bool = True) -> None:
        """Playwright와 브라우저를 시작합니다. 이미 시작됐다면 아무 것도 하지 않습니다."""
        if self._browser:
            return
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=headless)

    async def shutdown(self) -> None:
        """브라우저와 Playwright를 종료합니다."""
        try:
            if self._browser:
                await self._browser.close()
        finally:
            if self._pw:
                await self._pw.stop()
        self._browser = None
        self._pw = None

    async def new_session(self) -> tuple[BrowserContext, Page]:
        """새 컨텍스트/페이지를 생성합니다. (세션 역할)
        - 고립된 쿠키/스토리지 상태를 원하면 컨텍스트를 새로 만듭니다.
        """
        assert self._browser is not None, "브라우저가 시작되어야 합니다. ensure_started()를 먼저 호출하세요."
        ctx: BrowserContext = await self._browser.new_context()
        page: Page = await ctx.new_page()
        return ctx, page

async def open_url_and_wait(rt: PlaywrightRuntime,
                            url: str,
                            strategy: Literal["domcontentloaded", "load", "networkidle"] = "networkidle",
                            extra_wait_ms: int = 0) -> Dict[str, Any]:
    """
    지정한 URL을 새 또는 기존 브라우저 탭에서 열고, 동일 세션에서 안정화(strategy)에 도달할 때까지 대기합니다.
    Args:
      url: 이동할 절대 URL입니다(예: 'https://example.com'). 잘못된 형식이거나 네트워크 오류가 발생하면 오류로 처리합니다.
      strategy: 대기 전략입니다. "domcontentloaded" | "load" | "networkidle" 중 하나를 선택합니다.
      extra_wait_ms: 안정화 후 추가로 대기할 시간(ms). 느린 하이드레이션/지연 로딩을 흡수하려면 사용합니다.
    Returns:
      dict: 반환 형식은 다음과 같습니다(코드 기준 형식).
        {
          "status": "success" | "error",
          # success인 경우
          "ready_state": "loading" | "interactive" | "complete",
          "wait_strategy": "domcontentloaded" | "load" | "networkidle",
          "waited_ms": int,
          "current_url": str,
          "title": str,
          # error인 경우
          "error_message"?: str
        }
    """
    try:
        # 1) 런타임 시작 보장
        await rt.ensure_started()

        # 2) 새 세션(컨텍스트/페이지) 생성
        ctx, page = await rt.new_session()
        try:
            # 3) URL로 이동하면서 지정 전략까지 대기
            await page.goto(url, wait_until=strategy)

            # 4) 문서 readyState 확인 + 필요 시 추가 대기
            ready_state = await page.evaluate("() => document.readyState")
            if extra_wait_ms > 0:
                await asyncio.sleep(extra_wait_ms / 1000.0)

            # 5) 결과 반환
            return {
                "status": "success",
                "ready_state": ready_state,
                "wait_strategy": strategy,
                "waited_ms": max(0, int(extra_wait_ms)),
                "current_url": page.url,
                "title": await page.title(),
            }
        finally:
            # 6) 페이지/컨텍스트 정리(이 단계는 매 호출 단위 세션 사용)
            try:
                await page.close()
            except Exception:
                pass
            try:
                await ctx.close()
            except Exception:
                pass
    except Exception as e:
        # 모든 오류는 한국어 메시지로 반환합니다.
        return {"status": "error", "error_message": f"URL 오픈 및 안정화 대기 중 오류가 발생했습니다: {e}"}

async def _smoke_test():
    rt = PlaywrightRuntime()
    result = await open_url_and_wait(rt, url="https://naver.com")
    print(result)
    await rt.shutdown()


if __name__ == "__main__":
    asyncio.run(_smoke_test())

"""
# 임시 주석 
root_agent = Agent(
    name="Language_Translator_Agent",
    model=MODEL_GEMINI_2_5_FLASH,
    description=DESCRIPTION,
    instruction=INSTRUCTION,
    #tools=[agent_tool.AgentTool(agent=agent_search)],
    #sub_agents=[test_case_generator_agent],
    output_key="Language_Translator_output",
)
"""
