# WebPilot/constants/constants.py

import os
import logging
import sys 

# ============================================
# ADK Web 환경 감지
# ============================================
IS_ADK_WEB = any([
    'ADK_WEB' in os.environ,
    'GOOGLE_ADK' in os.environ,
    'K_SERVICE' in os.environ,  # Google Cloud Run
    'FUNCTION_TARGET' in os.environ,  # Google Cloud Functions
    'DEPLOYMENT_ENV' in os.environ and os.environ['DEPLOYMENT_ENV'] == 'adk',
])

# LLM Models
MODEL_GEMINI_2_5_PRO = "gemini-2.5-pro-preview-03-25"
MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash-preview-09-2025"
MODEL_O3_MINI = "gpt-4o"  # LLM DOM 분석용
MODEL_GPT_4_1 = "gpt-4o"
MODEL_CLAUDE_SONNET = "anthropic/claude-3-5-sonnet-20240620"
MODEL_GPT_4O = "gpt-4o"  # Vision용

# Resource Selector 설정
MAX_CRAWL_DEPTH = int(os.getenv("MAX_CRAWL_DEPTH", "2"))
MAX_URLS_PER_DOMAIN = int(os.getenv("MAX_URLS_PER_DOMAIN", "100"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.6"))
TOP_K_URLS = int(os.getenv("TOP_K_URLS", "3"))

# Embedding 설정
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))
EMBEDDING_CACHE_TTL = int(os.getenv("EMBEDDING_CACHE_TTL", "300"))  # 5분

# Playwright 설정
PLAYWRIGHT_BROWSER = os.getenv("PLAYWRIGHT_BROWSER", "chromium")
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
PLAYWRIGHT_TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "10000"))

# ============================================
# Multimodal Perceiver 설정
# ============================================

# Viewport 설정
PERCEIVER_VIEWPORT_WIDTH = int(os.getenv("PERCEIVER_VIEWPORT_WIDTH", "1280"))
PERCEIVER_VIEWPORT_HEIGHT = int(os.getenv("PERCEIVER_VIEWPORT_HEIGHT", "720"))
PERCEIVER_PAGE_TIMEOUT = int(os.getenv("PERCEIVER_PAGE_TIMEOUT", "15000"))  # 15초
PERCEIVER_WAIT_AFTER_LOAD = int(os.getenv("PERCEIVER_WAIT_AFTER_LOAD", "2"))  # 2초

# VLM 설정
PERCEIVER_VLM_MODEL = os.getenv("PERCEIVER_VLM_MODEL", "gpt-4o")
PERCEIVER_VLM_MAX_TOKENS = int(os.getenv("PERCEIVER_VLM_MAX_TOKENS", "2000"))
PERCEIVER_VLM_TEMPERATURE = float(os.getenv("PERCEIVER_VLM_TEMPERATURE", "0.1"))

# 재시도 설정
PERCEIVER_MAX_RETRIES = int(os.getenv("PERCEIVER_MAX_RETRIES", "3"))
PERCEIVER_RETRY_DELAY = int(os.getenv("PERCEIVER_RETRY_DELAY", "2"))  # 초

# 분석 설정
PERCEIVER_MIN_CONFIDENCE = float(os.getenv("PERCEIVER_MIN_CONFIDENCE", "0.7"))
PERCEIVER_MAX_VISIBLE_ELEMENTS = int(os.getenv("PERCEIVER_MAX_VISIBLE_ELEMENTS", "10"))
PERCEIVER_MAX_KEYWORD_CONTEXTS = int(os.getenv("PERCEIVER_MAX_KEYWORD_CONTEXTS", "3"))

# HTML 파서 설정
PERCEIVER_MAX_LINKS = int(os.getenv("PERCEIVER_MAX_LINKS", "30"))
PERCEIVER_MAX_TEXT_LENGTH = int(os.getenv("PERCEIVER_MAX_TEXT_LENGTH", "2000"))

# 스크린샷 저장 (ADK Web에서는 자동 비활성화)
_save_screenshots_env = os.getenv("PERCEIVER_SAVE_SCREENSHOTS", "true").lower() == "true"
PERCEIVER_SAVE_SCREENSHOTS = _save_screenshots_env and not IS_ADK_WEB  # ADK Web에서는 False
PERCEIVER_SCREENSHOT_DIR = os.getenv("PERCEIVER_SCREENSHOT_DIR", "./WebPilot/artifacts/screenshots")

# ============================================
# 로깅 설정
# ============================================

def setup_logging():
    """
    ADK Web 환경에 맞는 중앙집중식 로깅 설정
    """
    log_level = os.getenv("WEBPILOT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    # 상세 포맷: [레벨][파일:라인][함수][모듈] 메시지
    log_format = '[%(levelname)s] [%(filename)s:%(lineno)d] [%(funcName)s] [%(name)s] %(message)s'

    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True
    )

    webpilot_modules = [
        'WebPilot',
        'WebPilot.agent',
        'WebPilot.constants',
        'WebPilot.planner_agents',
        'WebPilot.planner_agents.Planner_Agent',
        'WebPilot.planner_agents.Planner_Agent.agent',
        'WebPilot.planner_agents.Domain_Priority_Classifier_Agent',
        'WebPilot.planner_agents.Domain_Priority_Classifier_Agent.agent',
        'WebPilot.planner_agents.Domain_Priority_Classifier_Agent.functions',
        'WebPilot.executor_agents',
        'WebPilot.executor_agents.multimodal_perceiver_agent',
        'WebPilot.executor_agents.multimodal_perceiver_agent.agent',
        'WebPilot.executor_agents.multimodal_perceiver_agent.vision_analyzer',
        'WebPilot.executor_agents.multimodal_perceiver_agent.dom_analyzer',
        'WebPilot.executor_agents.multimodal_perceiver_agent.html_parser',
        'WebPilot.executor_agents.multimodal_perceiver_agent.screenshot',
        'WebPilot.executor_agents.multimodal_perceiver_agent.response_validator',
        'WebPilot.executor_agents.navigation_agent',
        'WebPilot.executor_agents.navigation_agent.agent',
        'WebPilot.executor_agents.navigation_agent.playwright_executor',
        'WebPilot.executor_agents.resource_selector_agent',
        'WebPilot.executor_agents.resource_selector_agent.agent',
        'WebPilot.executor_agents.resource_selector_agent.crawler',
        'WebPilot.executor_agents.resource_selector_agent.embedder',
        'WebPilot.executor_agents.resource_selector_agent.selector',
        'WebPilot.executor_agents.resource_selector_agent.cache'
    ]

    for module_name in webpilot_modules:
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(level)
        # 중복 방지: 기존 핸들러 제거 후 단일 핸들러 부착
        for h in module_logger.handlers[:]:
            module_logger.removeHandler(h)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(log_format))
        module_logger.addHandler(handler)
        # 외부 루트 재구성 영향 차단
        module_logger.propagate = False

    logger = logging.getLogger(__name__)
    logger.info("="*80)
    logger.info("WebPilot 로깅 설정 완료")
    logger.info(f"로깅 레벨: {log_level}")
    logger.info(f"ADK Web 환경: {IS_ADK_WEB}")
    logger.info(f"스크린샷 저장: {PERCEIVER_SAVE_SCREENSHOTS}")
    logger.info(f"설정된 모듈: {len(webpilot_modules)}개")
    logger.info("="*80)

# 모듈 import 시 자동 적용
setup_logging()