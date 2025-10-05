# WebPilot/constants/constants.py

import os 

# LLM Models
MODEL_GEMINI_2_5_PRO = "gemini-2.5-pro-preview-03-25"
MODEL_GEMINI_2_5_FLASH = "gemini-2.5-flash-preview-09-2025"
MODEL_O3_MINI = "openai/o3-mini"
MODEL_GPT_4_1 = "openai/gpt-4.1"
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

# 스크린샷 저장 (디버깅용)
PERCEIVER_SAVE_SCREENSHOTS = os.getenv("PERCEIVER_SAVE_SCREENSHOTS", "true").lower() == "true"  # 기본값 true로 변경
PERCEIVER_SCREENSHOT_DIR = os.getenv("PERCEIVER_SCREENSHOT_DIR", "./WebPilot/artifacts/screenshots")  # 경로 변경